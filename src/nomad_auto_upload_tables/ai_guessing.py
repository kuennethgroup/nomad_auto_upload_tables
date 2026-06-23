"""
AI-assisted column-semantics guessing, via any OpenAI-compatible chat
completions endpoint (e.g. GWDG's SAIA, https://chat-ai.academiccloud.de/v1,
or OpenAI itself). The endpoint, API key and model are all supplied by the
caller (see `parsers.tabular_guess.TabularGuessParserEntryPoint`) -- this
module has no notion of a "default" provider.

Kept free of any `nomad` import, like `guessing.py`, and used the same way:
on success it returns column guesses in the same shape `guessing.guess_columns`
expects via its `ai_guesses` argument; on any failure it returns `None` so the
caller can fall back to the local heuristics instead.
"""

from __future__ import annotations

import json
import re

import pandas as pd

from nomad_auto_upload_tables.guessing import CATEGORIES, MAX_SAMPLE_VALUES, QUANTITY_TYPES

SYSTEM_PROMPT = (
    'You are a data analyst structuring a materials-science spreadsheet. '
    'You are given a JSON list of columns, each with its header text, pandas '
    'dtype, and a few example values. For each column, propose:\n'
    '- "guessed_name": a short snake_case quantity name\n'
    f'- "guessed_type": one of {QUANTITY_TYPES}\n'
    '- "guessed_unit": a pint-compatible unit string (e.g. "K", "Pa", "m/s"), '
    'or "" if the column has no physical unit\n'
    f'- "category": one of {CATEGORIES}\n'
    '- "confidence": your confidence in this guess, a number between 0 and 1\n'
    'Respond with ONLY a JSON array of objects, one per input column, each '
    'including the original "header" plus the five keys above. No prose, no '
    'markdown code fences.'
)

JSON_ARRAY_RE = re.compile(r'\[.*\]', re.DOTALL)


def _column_summary(df: pd.DataFrame) -> list[dict]:
    summary = []
    for header in df.columns:
        series = df[header]
        sample = series.dropna().unique()[:MAX_SAMPLE_VALUES]
        summary.append(
            {
                'header': str(header),
                'dtype': str(series.dtype),
                'sample_values': [str(v) for v in sample],
            }
        )
    return summary


def guess_with_ai(
    df: pd.DataFrame,
    api_key: str,
    model: str,
    base_url: str,
    logger=None,
) -> dict[str, dict] | None:
    """Ask the configured chat completions endpoint to guess each column's
    semantics. Returns a mapping from header to a guess dict (matching the
    keys `guessing.guess_columns` expects), or `None` if the request or its
    response could not be used."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': json.dumps(_column_summary(df))},
            ],
        )
        content = response.choices[0].message.content
    except Exception:
        if logger:
            logger.warning('AI column guessing request failed', exc_info=True)
        return None

    guesses = _parse_response(content, expected_headers=set(df.columns.astype(str)))
    if guesses is None and logger:
        logger.warning('AI column guessing returned an unusable response: %s', content)
    return guesses


def _parse_response(content: str, expected_headers: set[str]) -> dict[str, dict] | None:
    match = JSON_ARRAY_RE.search(content or '')
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    guesses = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        header = item.get('header')
        if header not in expected_headers:
            continue
        guessed_type = item.get('guessed_type')
        category = item.get('category')
        try:
            confidence = float(item.get('confidence', 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        guesses[header] = {
            'guessed_name': str(item.get('guessed_name') or ''),
            'guessed_type': guessed_type if guessed_type in QUANTITY_TYPES else 'string',
            'guessed_unit': str(item.get('guessed_unit') or ''),
            'category': category if category in CATEGORIES else 'other',
            'confidence': confidence,
        }
    return guesses or None
