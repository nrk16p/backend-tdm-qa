# app/schemas.py
from pydantic import BaseModel
from typing import Optional

class TicketUpdate(BaseModel):
    load_id: str
    start_datetime: Optional[str] = None
    origin_datetime: Optional[str] = None
    start_recive_datetime: Optional[str] = None
    end_recive_datetime: Optional[str] = None
    intransit_datetime: Optional[str] = None
    desination_datetime: Optional[str] = None
    start_unload_datetime: Optional[str] = None
    end_unload_datetime: Optional[str] = None
    complete_datetime: Optional[str] = None
