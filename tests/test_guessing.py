from pathlib import Path

from nomad_auto_upload_tables.guessing import (
    clean_name,
    coerce_value,
    guess_category,
    guess_columns,
    guess_type,
    guess_unit,
    read_table,
)

DATA_DIR = Path(__file__).parent / 'data'


def test_read_table_csv():
    df, sheet_name = read_table(DATA_DIR / 'sample.csv')
    assert sheet_name is None
    assert list(df.columns) == [
        'Sample ID',
        'Temperature (K)',
        'Pressure [Pa]',
        'Synthesis Date',
        'Notes',
    ]
    assert len(df) == 3


def test_guess_unit_parses_parenthesized_and_bracketed_units():
    assert guess_unit('Temperature (K)') == 'K'
    assert guess_unit('Pressure [Pa]') == 'Pa'
    assert guess_unit('Notes') is None
    assert guess_unit('Made up unit (frobnicate)') is None


def test_guess_category_matches_keywords():
    assert guess_category('Sample ID')[0] == 'sample_id'
    assert guess_category('Temperature (K)')[0] == 'temperature'
    assert guess_category('Pressure [Pa]')[0] == 'pressure'
    category, confidence = guess_category('Some unrelated header')
    assert category == 'other'
    assert confidence < 0.5


def test_clean_name_strips_unit_and_snake_cases():
    assert clean_name('Temperature (K)') == 'temperature'
    assert clean_name('Pressure [Pa]') == 'pressure'
    assert clean_name('Sample ID') == 'sample_id'


def test_guess_type_for_numeric_and_string_columns():
    df, _ = read_table(DATA_DIR / 'sample.csv')
    assert guess_type(df['Temperature (K)']) == 'float'
    assert guess_type(df['Sample ID']) == 'string'


def test_guess_type_for_datetime_like_strings():
    df, _ = read_table(DATA_DIR / 'sample.csv')
    assert guess_type(df['Synthesis Date']) == 'datetime'


def test_read_table_xlsx_picks_up_sheet_name():
    df, sheet_name = read_table(DATA_DIR / 'sample.xlsx')
    assert sheet_name == 'Measurements'
    assert len(df) == 3


def test_guess_columns_end_to_end():
    df, _ = read_table(DATA_DIR / 'sample.csv')
    columns = {c.header: c for c in guess_columns(df)}

    temp = columns['Temperature (K)']
    assert temp.guessed_name == 'temperature'
    assert temp.guessed_type == 'float'
    assert temp.guessed_unit == 'K'
    assert temp.category == 'temperature'
    assert temp.n_missing == 0

    notes = columns['Notes']
    assert notes.n_missing == 1
    assert notes.category == 'other'


def test_coerce_value_handles_missing_and_types():
    assert coerce_value(float('nan'), 'float') is None
    assert coerce_value('3.5', 'float') == 3.5
    assert coerce_value('7', 'integer') == 7
    assert coerce_value('S001', 'string') == 'S001'
