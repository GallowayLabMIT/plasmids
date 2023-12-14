from typing import List, Tuple, Optional
import datetime
from pydantic import BaseModel, validator # type: ignore

class Plasmid(BaseModel):
    pKG: int
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
    attachment_filenames: List[str] = []
    technical_details: List[str]
    warnings: List[Tuple[str,str]] = []
    errors: List[Tuple[str,str]] = []

    @validator('date_stored', pre=True)
    def parse_quartzy_date(cls, value: str) -> datetime.date:
        try:
            return datetime.datetime.strptime(
                value,
                r'%Y-%m-%d',
            ).date()
        except ValueError:
            pass
        try:
            return datetime.datetime.strptime(
                value,
                r'%Y-%m-%dT%H:%M:%S.%fZ'
            ).date()
        except ValueError:
            pass
        try:
            return datetime.datetime.strptime(
                value,
                r'%m/%d/%Y'
            ).date()
        except ValueError:
            pass
        raise ValueError(f"Can't process given Quartzy date: {value}")

class User(BaseModel):
    first_name: str
    last_name: str
    full_name: str
    id: str
