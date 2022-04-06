from typing import List
import datetime
from pydantic import BaseModel, validator

class Plasmid(BaseModel):
    pKG: int
    name: str
    species: str
    resistances: List[str]
    plasmid_type: List[str]
    date_stored: datetime.date
    alt_name: str

    @validator('date_stored', pre=True)
    def parse_quartzy_date(cls, value):
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


