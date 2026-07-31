from pydantic import BaseModel
from typing import Optional


class DigitalIdentityCreate(BaseModel):
    user_id: int
    digital_id: Optional[str] = None
    broadband_id: Optional[str] = None
    is_primary: bool = False


class DigitalIdentityResponse(BaseModel):
    id: int
    user_id: int
    digital_id: Optional[str] = None
    broadband_id: Optional[str] = None
    is_primary: bool = False
    created_at: str
