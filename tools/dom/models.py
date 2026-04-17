from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class ResultBase:
    def to_dict(self) -> dict:
        return asdict(self)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in type(self).__annotations__:
            setattr(self, key, value)
        else:
            msg = f"{key} is not a valid field of {self.__class__.__name__}"
            raise KeyError(msg)

    def __getitem__(self, key: str) -> Any:
        if key in type(self).__annotations__:
            return getattr(self, key)
        msg = f"{key} is not a valid field of {self.__class__.__name__}"
        raise KeyError(msg)


@dataclass
class DSFRResult(ResultBase):
    header_brand: bool = False
    version: str | None = None
    components: dict = field(default_factory=dict)


@dataclass
class A11YResult(ResultBase):
    url: str | None = None
    mention: str | None = None
    in_dsfr_footer: bool = False
    skip_links: bool = False
    cited_law: bool = False
    rgaa_version: str | None = None
    rgaa_percentage: float | None = None
    rgaa_update_date: date | None = None


@dataclass
class GDPRResult(ResultBase):
    ml_url: str | None = None
    ml_mention: str | None = None
    ml_matches: list[str] = field(default_factory=list)
    ml_missing: list[str] = field(default_factory=list)
    pc_url: str | None = None
    pc_mention: str | None = None
    pc_matches: list[str] = field(default_factory=list)
    pc_missing: list[str] = field(default_factory=list)
    cgu_url: str | None = None
    cgu_mention: str | None = None
    cgu_matches: list[str] = field(default_factory=list)
    cgu_missing: list[str] = field(default_factory=list)


@dataclass
class TrackingResult(ResultBase):
    available: bool = False
    tools: list[str] = field(default_factory=list)
    has_tac: bool = False
    has_orejime: bool = False
    date: datetime | None = None
