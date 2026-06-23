"""
Glue between the pure-pandas heuristics in :mod:`guessing` and the NOMAD
archive/metainfo objects defined in :mod:`schema_packages.tabular_guess`.

Kept as a separate top-level module (rather than living in either
``parsers`` or ``schema_packages``) so both can import it without a circular
import.
"""

from __future__ import annotations

import dataclasses

import pandas as pd

from nomad_auto_upload_tables.guessing import coerce_value, guess_columns, read_table


def build_initial_guess(
    path: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    logger=None,
) -> tuple[str | None, int, list[dict], bool]:
    """Read a spreadsheet on disk and return
    ``(sheet_name, n_rows, columns, ai_assisted)`` where ``columns`` is a list
    of dicts suitable for ``GuessedColumn(**d)``.

    If ``api_key`` and ``model`` are set, column semantics are guessed by an
    AI chat completions call (see ``ai_guessing.guess_with_ai``); on any
    failure (or if not configured) this falls back to the local heuristics in
    ``guessing.py``, and ``ai_assisted`` is ``False``.
    """
    df, sheet_name = read_table(path)

    ai_guesses = None
    if api_key and model:
        from nomad_auto_upload_tables.ai_guessing import guess_with_ai

        ai_guesses = guess_with_ai(df, api_key=api_key, model=model, base_url=base_url, logger=logger)

    columns = [dataclasses.asdict(c) for c in guess_columns(df, ai_guesses=ai_guesses)]
    return sheet_name, len(df), columns, ai_guesses is not None


def build_structured_rows(entry, archive) -> list:
    """Re-read ``entry``'s data file and build ``GuessedRow``/``GuessedProperty``
    instances from the (possibly user-corrected) column mapping in
    ``entry.columns``."""
    from nomad_auto_upload_tables.schema_packages.tabular_guess import (
        GuessedProperty,
        GuessedRow,
    )

    with archive.m_context.raw_file(entry.data_file) as f:
        if entry.data_file.lower().endswith(('.xlsx', '.xls')):
            df = pd.read_excel(f, sheet_name=entry.sheet_name or 0)
        else:
            df = pd.read_csv(f)

    included = [column for column in entry.columns if column.include]
    rows = []
    for _, row in df.iterrows():
        properties = []
        for column in included:
            value = coerce_value(row[column.header], column.guessed_type)
            properties.append(
                GuessedProperty(
                    name=column.guessed_name,
                    value=value if value is None else str(value),
                    unit=column.guessed_unit or None,
                    category=column.category,
                )
            )
        rows.append(GuessedRow(properties=properties))
    return rows
