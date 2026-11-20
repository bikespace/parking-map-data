from typing import Literal, TypedDict, NotRequired

TTSYear = Literal[1986, 1991, 1996, 2001, 2006, 2011, 2016, 2022]
TTSMetric = Literal["household", "person", "trip", "transit"]


class CodeLookupBase(TypedDict):
    type: Literal["direct", "range"]
    description: str
    notes: NotRequired[str]
    years_valid: NotRequired[list[TTSYear]]


class CodeLookupDirect(CodeLookupBase):
    type: Literal["direct"]
    code: str | int


class CodeLookupRange(CodeLookupBase):
    type: Literal["range"]
    code_min: int
    code_max: int


type CodeLookup = CodeLookupDirect | CodeLookupRange
