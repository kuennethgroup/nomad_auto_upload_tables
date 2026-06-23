from nomad.parsing import MatchingParser

from nomad_auto_upload_tables.schema_packages.tabular_guess import GuessedColumn, TabularGuess
from nomad_auto_upload_tables.tabular_guess_build import build_initial_guess


class TabularGuessParser(MatchingParser):
    """Matches uploaded .xlsx/.xls/.csv files and creates a `TabularGuess`
    entry with a heuristically guessed column mapping for the user to
    review in the entry editor.

    If the entry has already been confirmed (``confirm_schema`` ticked) this
    is a no-op, so that an explicit upload reprocessing does not clobber the
    user's corrections with a fresh guess.
    """

    def __init__(self, *, api_key=None, model=None, base_url=None, **kwargs):
        # `MatchingParser.__init__` takes `**kwargs` but discards anything it
        # doesn't recognize, so the AI-endpoint config from the entry point
        # (see `parsers.TabularGuessParserEntryPoint`) has to be captured here
        # explicitly rather than relying on it being stored automatically.
        super().__init__(**kwargs)
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    def parse(self, mainfile, archive, logger=None, child_archives=None):
        if archive.data is not None and getattr(archive.data, 'confirm_schema', False):
            return

        data_file = archive.metadata.mainfile if archive.metadata else mainfile.rsplit('/', 1)[-1]

        sheet_name, n_rows, columns, ai_assisted = build_initial_guess(
            mainfile,
            api_key=self.api_key,
            model=self.model,
            base_url=self.base_url,
            logger=logger,
        )

        archive.data = TabularGuess(
            data_file=data_file,
            sheet_name=sheet_name,
            n_rows=n_rows,
            ai_assisted=ai_assisted,
            columns=[GuessedColumn(**column) for column in columns],
        )
