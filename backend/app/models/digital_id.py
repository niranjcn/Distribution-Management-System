from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class DigitalIdCreate(BaseModel):
    user_id: str
    digital_id: Optional[str] = None
    broadband_id: Optional[str] = None


class DigitalIdUpdate(BaseModel):
    digital_id: Optional[str] = None
    broadband_id: Optional[str] = None


class DigitalIdResponse(BaseModel):
    id: str
    user_id: str
    user_id_hash: str
    digital_id: Optional[str] = None
    broadband_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
