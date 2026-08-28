import os
from typing import Optional

class Direction:
    FORWARD: "Direction"
    BACKWARD: "Direction"
    def __int__(self) -> int: ...

class TranslationResult:
    output: str
    emphasis: Optional[list[tuple[str, int, int]]]
    # output_positions[i] is the index in `output` of the cell that the input
    # character at index i translated to. One entry per input character.
    output_positions: Optional[list[int]]
    # input_positions[j] is the index in the input text of the character that
    # `output[j]` came from. One entry per output cell.
    input_positions: Optional[list[int]]
    # The position of the `cursor_pos=` argument translated into `output`, or
    # None when no cursor was passed. Equals len(output) for a cursor past the
    # end of the input.
    cursor_pos: Optional[int]

class Translator:
    def __init__(
        self,
        tables: list[str | os.PathLike],
        direction: Direction = ...,
    ) -> None: ...
    @staticmethod
    def from_table_source(
        table: str,
        direction: Direction = ...,
    ) -> "Translator": ...
    def translate(self, text: str) -> str: ...
    def translate_with_options(
        self,
        text: str,
        *,
        mode: int = ...,
        emphasis: Optional[list[tuple[str, int, int]]] = ...,
        cursor_pos: Optional[int] = ...,
    ) -> TranslationResult: ...

class LouisError(Exception): ...

class TableParseError(LouisError):
    errors: list[str]

class TranslationError(LouisError): ...

__version__: str
