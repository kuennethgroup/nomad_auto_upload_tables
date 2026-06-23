"""
Schema for the "guess then correct" tabular-upload workflow.

A :class:`TabularGuess` entry is created automatically (by
``parsers.tabular_guess.TabularGuessParser``) when an Excel/CSV file is
uploaded. It holds one :class:`GuessedColumn` per spreadsheet column with the
heuristic guess for that column's name/type/unit/ontology category, exposed
as ELN-editable quantities so the user can correct them in NOMAD's normal
entry editor. Ticking ``confirm_schema`` and saving builds the structured
``rows`` from the (corrected) mapping.
"""

from nomad.datamodel.data import ArchiveSection, EntryData
from nomad.datamodel.metainfo.annotations import ELNAnnotation, ELNComponentEnum
from nomad.metainfo import MEnum, Quantity, SchemaPackage, SubSection

from nomad_auto_upload_tables.guessing import CATEGORIES, QUANTITY_TYPES

m_package = SchemaPackage()


class GuessedColumn(ArchiveSection):
    """One spreadsheet column together with the heuristic guess for its
    semantic meaning, type and unit, and the user's corrections to it."""

    header = Quantity(type=str, description='Original column header text.')
    sample_values = Quantity(
        type=str, description='A few example values from this column, for review.'
    )
    n_rows = Quantity(type=int, description='Number of non-empty cells in this column.')
    n_missing = Quantity(type=int, description='Number of empty/missing cells in this column.')
    confidence = Quantity(type=float, description='Heuristic confidence in this guess (0-1).')

    guessed_name = Quantity(
        type=str,
        description='Proposed quantity name for this column.',
        a_eln=ELNAnnotation(component=ELNComponentEnum.StringEditQuantity),
    )
    guessed_type = Quantity(
        type=MEnum(QUANTITY_TYPES),
        description='Proposed data type for this column.',
        a_eln=ELNAnnotation(component=ELNComponentEnum.EnumEditQuantity),
    )
    guessed_unit = Quantity(
        type=str,
        description='Pint-compatible unit string parsed from the header, if any.',
        a_eln=ELNAnnotation(component=ELNComponentEnum.StringEditQuantity),
    )
    category = Quantity(
        type=MEnum(CATEGORIES),
        description='Proposed ontology category for this column.',
        a_eln=ELNAnnotation(component=ELNComponentEnum.EnumEditQuantity),
    )
    include = Quantity(
        type=bool,
        default=True,
        description='Whether to include this column when building the structured data.',
        a_eln=ELNAnnotation(component=ELNComponentEnum.BoolEditQuantity),
    )


class GuessedProperty(ArchiveSection):
    """One column's value within a single structured data row."""

    name = Quantity(type=str)
    value = Quantity(type=str)
    unit = Quantity(type=str)
    category = Quantity(type=str)


class GuessedRow(ArchiveSection):
    """The structured data for a single source spreadsheet row."""

    properties = SubSection(section=GuessedProperty.m_def, repeats=True)


class TabularGuess(EntryData):
    """Entry created automatically when an Excel/CSV file is uploaded. Holds
    the heuristically guessed table structure for the user to review and
    correct, and (once confirmed) the resulting structured data."""

    data_file = Quantity(
        type=str,
        description='The uploaded spreadsheet file this entry was guessed from.',
        a_eln=ELNAnnotation(component=ELNComponentEnum.FileEditQuantity),
    )
    sheet_name = Quantity(type=str, description='Sheet name used, for multi-sheet workbooks.')
    n_rows = Quantity(type=int, description='Number of data rows detected in the file.')
    ai_assisted = Quantity(
        type=bool,
        default=False,
        description=(
            'Whether the column guesses below came from the configured AI '
            'endpoint, as opposed to the local heuristic fallback.'
        ),
    )

    confirm_schema = Quantity(
        type=bool,
        default=False,
        description=(
            'Tick once the guessed column mapping below has been reviewed and '
            'corrected. Saving will (re)build the structured data below from '
            'this mapping.'
        ),
        a_eln=ELNAnnotation(component=ELNComponentEnum.BoolEditQuantity),
    )

    columns = SubSection(section=GuessedColumn.m_def, repeats=True)
    rows = SubSection(section=GuessedRow.m_def, repeats=True)

    def normalize(self, archive, logger):
        super().normalize(archive, logger)

        if not (self.confirm_schema and self.columns and self.data_file):
            return

        from nomad_auto_upload_tables.tabular_guess_build import build_structured_rows

        try:
            self.rows = build_structured_rows(self, archive)
        except Exception as e:  # noqa: BLE001 - report to the user via the processing log
            logger.error('Failed to build structured data from confirmed schema', exc_info=e)


m_package.__init_metainfo__()
