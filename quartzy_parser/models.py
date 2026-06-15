"""Definitions of Pydantic modules."""

import datetime
from typing import List, Optional, Tuple

from pydantic import BaseModel, HttpUrl, validator  # type: ignore


class Attachment(BaseModel):
    """Represents a Quartzy file attachment, like a DNA map."""

    uuid: str
    file_name: str
    url: HttpUrl


class Feature(BaseModel):
    """Represents a DNA sequence feature, optionally translated."""

    name: str
    type: str
    sequence: str
    translation: Optional[str] = None


class Plasmid(BaseModel):
    """Represents all relevant plasmid metadata."""

    pKG: int
    uid: str
    filename: str
    q_item_name: str
    name: str
    species: str
    resistances: List[str]
    plasmid_type: List[str]
    date_stored: datetime.date
    vendor: Optional[str]
    alt_name: str
    owner_id: str
    attachments: List[Attachment] = []
    technical_details: List[str]
    warnings: List[Tuple[str, str]] = []
    errors: List[Tuple[str, str]] = []

    @validator("date_stored", pre=True)
    def parse_quartzy_date(cls, value: str) -> datetime.date:
        """Parse one of the multiple allowable Quartzy timestamps."""
        try:
            return datetime.datetime.strptime(
                value,
                r"%Y-%m-%d",
            ).date()
        except ValueError:
            pass
        try:
            return datetime.datetime.strptime(value, r"%Y-%m-%dT%H:%M:%S.%fZ").date()
        except ValueError:
            pass
        try:
            return datetime.datetime.strptime(value, r"%m/%d/%Y").date()
        except ValueError:
            pass
        raise ValueError(f"Can't process given Quartzy date: {value}")


class User(BaseModel):
    """Represents a Quartzy user profile."""

    first_name: str
    last_name: str
    full_name: str
    id: str
