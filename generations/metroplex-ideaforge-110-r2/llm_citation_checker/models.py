from pydantic import BaseModel
from typing import Optional


class Fact(BaseModel):
    fact: str
    source: str


class Statement(BaseModel):
    text: str
    verified: bool = False
    citation: Optional[str] = None
