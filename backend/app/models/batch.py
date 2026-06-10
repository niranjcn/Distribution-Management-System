from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class BatchBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None


class BatchCreate(BatchBase):
    pass


class BatchUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None


class Batch(BatchBase):
    id: str = Field(..., alias="_id")
    batch_id: str  # Unique identifier like BATCH-2026-0001
    created_by: str
    created_by_name: str
    created_at: datetime
    updated_at: datetime
    device_count: int = 0
    
    class Config:
        populate_by_name = True
        from_attributes = True


class BatchResponse(BaseModel):
    id: str
    batch_id: str
    name: str
    description: Optional[str] = None
    created_by: str
    created_by_name: str
    created_at: datetime
    updated_at: datetime
    device_count: int
