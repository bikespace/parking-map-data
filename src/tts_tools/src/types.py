from pathlib import Path
from typing import Literal, NotRequired, TypedDict

TTSYear = Literal[1986, 1991, 1996, 2001, 2006, 2011, 2016, 2022]
TTSMetric = Literal["household", "person", "trip", "transit"]

CrossTabType = Literal["csv", "col"]


class TTSGeometry(TypedDict):
    file: Path
    key: str


class CodeLookupBase(TypedDict):
    type: Literal["direct", "range", "range_direct"]
    notes: NotRequired[str]
    years_valid: NotRequired[list[TTSYear]]


class CodeLookupDirect(CodeLookupBase):
    type: Literal["direct"]
    code: str | int
    description: str


class CodeLookupRange(CodeLookupBase):
    type: Literal["range"]
    code_min: int
    code_max: int


class CodeLookupRangeDirect(CodeLookupBase):
    type: Literal["range_direct"]
    code_min: int
    code_max: int
    code: int
    description: str


type CodeLookup = CodeLookupDirect | CodeLookupRange | CodeLookupRangeDirect
