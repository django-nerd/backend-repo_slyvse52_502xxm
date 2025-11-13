from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Record(BaseModel):
    village: Optional[str] = None
    crop: Optional[str] = None
    area: Optional[float] = Field(default=None, description="Area cultivated (hectares)")
    temperature: Optional[float] = None
    rainfall: Optional[float] = None
    soil: Optional[str] = None
    season: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: Optional[datetime] = None

class GroundwaterEvent(BaseModel):
    village: str
    usage_liters: float
    leak_detected: bool = False
    noted_at: Optional[datetime] = None
