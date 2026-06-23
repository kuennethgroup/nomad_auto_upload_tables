from contextlib import contextmanager
from pathlib import Path

from nomad_auto_upload_tables.parsers.tabular_guess import TabularGuessParser
from nomad_auto_upload_tables.schema_packages.tabular_guess import TabularGuess
from nomad_auto_upload_tables.tabular_guess_build import build_structured_rows

DATA_DIR = Path(__file__).parent / 'data'


class FakeContext:
    """Stands in for `archive.m_context`, resolving `data_file` directly
    against the test data directory instead of an actual NOMAD upload."""

    @contextmanager
    def raw_file(self, path, *args, **kwargs):
        with open(DATA_DIR / path, 'rb') as f:
            yield f


class FakeArchive:
    def __init__(self, data):
        self.data = data
        self.m_context = FakeContext()


def test_parser_builds_initial_guess_for_all_columns():
    archive = FakeArchive(data=None)
    archive.metadata = None

    TabularGuessParser().parse(str(DATA_DIR / 'sample.csv'), archive)

    assert isinstance(archive.data, TabularGuess)
    assert archive.data.n_rows == 3
    assert {c.header for c in archive.data.columns} == {
        'Sample ID',
        'Temperature (K)',
        'Pressure [Pa]',
        'Synthesis Date',
        'Notes',
    }
    assert archive.data.confirm_schema is False


def test_reparsing_a_confirmed_entry_is_a_no_op():
    entry = TabularGuess(data_file='sample.csv', confirm_schema=True, columns=[])
    archive = FakeArchive(data=entry)
    archive.metadata = None

    TabularGuessParser().parse(str(DATA_DIR / 'sample.csv'), archive)

    assert archive.data is entry


def test_build_structured_rows_uses_corrected_mapping():
    archive = FakeArchive(data=None)
    archive.metadata = None
    TabularGuessParser().parse(str(DATA_DIR / 'sample.csv'), archive)

    entry = archive.data
    # Simulate the user correcting a guess and excluding a column.
    by_header = {c.header: c for c in entry.columns}
    by_header['Notes'].include = False
    by_header['Sample ID'].guessed_name = 'sample_identifier'

    rows = build_structured_rows(entry, archive)

    assert len(rows) == 3
    first_row_names = {p.name for p in rows[0].properties}
    assert first_row_names == {'sample_identifier', 'temperature', 'pressure', 'synthesis_date'}

    temperature_property = next(p for p in rows[0].properties if p.name == 'temperature')
    assert temperature_property.value == '300.5'
    assert temperature_property.unit == 'K'
    assert temperature_property.category == 'temperature'


def test_parser_uses_ai_guess_when_configured(monkeypatch):
    def fake_guess_with_ai(df, api_key, model, base_url, logger=None):
        return {header: {
            'guessed_name': 'ai_name',
            'guessed_type': 'string',
            'guessed_unit': '',
            'category': 'measurement_result',
            'confidence': 0.99,
        } for header in df.columns.astype(str)}

    monkeypatch.setattr('nomad_auto_upload_tables.ai_guessing.guess_with_ai', fake_guess_with_ai)

    archive = FakeArchive(data=None)
    archive.metadata = None
    parser = TabularGuessParser(api_key='sk-test', model='some-model')
    parser.parse(str(DATA_DIR / 'sample.csv'), archive)

    assert archive.data.ai_assisted is True
    assert all(c.category == 'measurement_result' for c in archive.data.columns)


def test_parser_falls_back_to_heuristics_when_ai_fails(monkeypatch):
    def failing_guess_with_ai(df, api_key, model, base_url, logger=None):
        return None

    monkeypatch.setattr('nomad_auto_upload_tables.ai_guessing.guess_with_ai', failing_guess_with_ai)

    archive = FakeArchive(data=None)
    archive.metadata = None
    parser = TabularGuessParser(api_key='sk-test', model='some-model')
    parser.parse(str(DATA_DIR / 'sample.csv'), archive)

    assert archive.data.ai_assisted is False
    by_header = {c.header: c for c in archive.data.columns}
    assert by_header['Temperature (K)'].category == 'temperature'


def test_parser_skips_ai_when_not_configured(monkeypatch):
    def unexpected_call(*args, **kwargs):
        raise AssertionError('guess_with_ai should not be called without api_key/model')

    monkeypatch.setattr('nomad_auto_upload_tables.ai_guessing.guess_with_ai', unexpected_call)

    archive = FakeArchive(data=None)
    archive.metadata = None
    TabularGuessParser().parse(str(DATA_DIR / 'sample.csv'), archive)

    assert archive.data.ai_assisted is False
