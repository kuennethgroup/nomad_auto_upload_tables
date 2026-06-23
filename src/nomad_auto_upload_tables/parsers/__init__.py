from nomad.config.models.plugins import ParserEntryPoint
from pydantic import Field


class TabularGuessParserEntryPoint(ParserEntryPoint):
    api_key: str | None = Field(
        default=None,
        description=(
            'API key for the OpenAI-compatible chat completions endpoint used to '
            'guess column semantics. Set this (and `model`) via nomad.yaml under '
            'plugins.entry_points.options to enable AI-assisted guessing; without '
            'it, the parser falls back to local heuristics.'
        ),
    )
    model: str | None = Field(
        default=None,
        description='Model name to request from the chat completions endpoint, e.g. "meta-llama-3.1-8b-instruct".',
    )
    base_url: str = Field(
        default='https://chat-ai.academiccloud.de/v1',
        description='Base URL of the OpenAI-compatible chat completions endpoint (default: GWDG SAIA).',
    )

    def load(self):
        from nomad_auto_upload_tables.parsers.tabular_guess import TabularGuessParser

        return TabularGuessParser(**self.dict())


tabular_guess_parser = TabularGuessParserEntryPoint(
    name='TabularGuessParser',
    description=(
        'Matches uploaded .xlsx/.xls/.csv files and creates an entry with a '
        'guessed table schema for the user to review and correct. Column '
        'semantics are guessed by an AI chat completions endpoint if '
        '`api_key`/`model` are configured, otherwise by local heuristics.'
    ),
    mainfile_name_re=r'.*\.(xlsx|xls|csv)$',
)
