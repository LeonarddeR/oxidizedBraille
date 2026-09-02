import os
from collections.abc import Sequence

class Direction:
    FORWARD: Direction
    BACKWARD: Direction
    def __int__(self) -> int: ...

class TranslationResult:
    output: str
    emphasis: list[tuple[str, int, int]] | None
    # output_positions[i] is the index in `output` of the cell that the input
    # character at index i translated to. One entry per input character.
    output_positions: list[int] | None
    # input_positions[j] is the index in the input text of the character that
    # `output[j]` came from. One entry per output cell.
    input_positions: list[int] | None
    # The position of the `cursor_pos=` argument translated into `output`, or
    # None when no cursor was passed. Equals len(output) for a cursor past the
    # end of the input.
    cursor_pos: int | None

class Translator:
    def __init__(
        self,
        tables: Sequence[str | os.PathLike],
        direction: Direction = ...,
        *,
        # Directories searched, in order, for each table name and every
        # `include`. None reads LOUIS_TABLE_PATH (`.` when unset). Nothing else
        # is searched: a table's own directory only when listed, and an
        # absolute table name resolves against any non-empty search path.
        search_path: Sequence[str | os.PathLike] | None = ...,
    ) -> None: ...
    @staticmethod
    def from_table_source(
        table: str,
        direction: Direction = ...,
    ) -> Translator: ...
    def translate(self, text: str) -> str: ...
    def translate_with_options(
        self,
        text: str,
        *,
        mode: int = ...,
        emphasis: list[tuple[str, int, int]] | None = ...,
        cursor_pos: int | None = ...,
    ) -> TranslationResult: ...

class LouisError(Exception): ...

class TableParseError(LouisError):
    errors: list[str]

class TranslationError(LouisError): ...

__version__: str
