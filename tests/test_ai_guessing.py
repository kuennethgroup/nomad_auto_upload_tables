import json

import pandas as pd

from nomad_auto_upload_tables.ai_guessing import _parse_response, guess_with_ai

DF = pd.DataFrame(
    {
        'Sample ID': ['S001', 'S002'],
        'Temperature (K)': [300.5, 310.2],
    }
)

VALID_RESPONSE = json.dumps(
    [
        {
            'header': 'Sample ID',
            'guessed_name': 'sample_identifier',
            'guessed_type': 'string',
            'guessed_unit': '',
            'category': 'sample_id',
            'confidence': 0.95,
        },
        {
            'header': 'Temperature (K)',
            'guessed_name': 'temperature',
            'guessed_type': 'float',
            'guessed_unit': 'K',
            'category': 'temperature',
            'confidence': 0.9,
        },
    ]
)


def test_parse_response_extracts_valid_json_array():
    guesses = _parse_response(VALID_RESPONSE, expected_headers={'Sample ID', 'Temperature (K)'})
    assert guesses['Temperature (K)']['guessed_unit'] == 'K'
    assert guesses['Temperature (K)']['category'] == 'temperature'
    assert guesses['Sample ID']['guessed_name'] == 'sample_identifier'


def test_parse_response_strips_markdown_code_fences():
    fenced = f'```json\n{VALID_RESPONSE}\n```'
    guesses = _parse_response(fenced, expected_headers={'Sample ID', 'Temperature (K)'})
    assert guesses is not None
    assert set(guesses) == {'Sample ID', 'Temperature (K)'}


def test_parse_response_ignores_unexpected_headers():
    guesses = _parse_response(VALID_RESPONSE, expected_headers={'Sample ID'})
    assert set(guesses) == {'Sample ID'}


def test_parse_response_rejects_invalid_type_and_category():
    response = json.dumps(
        [
            {
                'header': 'Sample ID',
                'guessed_name': 'x',
                'guessed_type': 'not-a-real-type',
                'guessed_unit': '',
                'category': 'not-a-real-category',
                'confidence': 'not-a-number',
            }
        ]
    )
    guesses = _parse_response(response, expected_headers={'Sample ID'})
    assert guesses['Sample ID']['guessed_type'] == 'string'
    assert guesses['Sample ID']['category'] == 'other'
    assert guesses['Sample ID']['confidence'] == 0.5


def test_parse_response_returns_none_for_garbage():
    assert _parse_response('not json at all', expected_headers={'Sample ID'}) is None
    assert _parse_response('', expected_headers={'Sample ID'}) is None


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return type('Resp', (), {'choices': [_FakeChoice(self._content)]})()


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class FakeOpenAI:
    """Stands in for `openai.OpenAI`, returning a fixed chat completion."""

    response_content = VALID_RESPONSE

    def __init__(self, api_key=None, base_url=None):
        self.api_key = api_key
        self.base_url = base_url
        self.chat = _FakeChat(self.response_content)


def test_guess_with_ai_returns_parsed_guesses(monkeypatch):
    monkeypatch.setattr('openai.OpenAI', FakeOpenAI)
    guesses = guess_with_ai(DF, api_key='sk-test', model='some-model', base_url='https://example.invalid/v1')
    assert guesses['Temperature (K)']['category'] == 'temperature'


def test_guess_with_ai_returns_none_on_request_failure(monkeypatch):
    class RaisingOpenAI:
        def __init__(self, **kwargs):
            raise RuntimeError('network is down')

    monkeypatch.setattr('openai.OpenAI', RaisingOpenAI)
    assert guess_with_ai(DF, api_key='sk-test', model='some-model', base_url='https://example.invalid/v1') is None
