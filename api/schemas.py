# app/schemas.py
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

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


class PalletDataUpdate(BaseModel):
    load_id: str
    tranfer_pallet: Optional[int] = None
    change_pallet: Optional[int] = None
    drop_pallet: Optional[int] = None
    return_pallet: Optional[int] = None
    borrow_customer_pallet: Optional[int] = None
    return_customer_pallet: Optional[int] = None


class JobSchema(BaseModel): 
    load_id: str
    date_plan: Optional[date] = None
    h_plate: Optional[str] = None
    t_plate: Optional[str] = None
    fuel_type: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    driver_name: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    remark: Optional[str] = None
    locat_recive: Optional[str] = None
    date_recive: Optional[date] = None
    locat_deliver: Optional[str] = None
    date_deliver: Optional[date] = None
    pallet_type: Optional[str] = None
    pallet_plan: Optional[int] = None
    unload_cost: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

class JobUpdateSchema(BaseModel):
    date_plan: Optional[date] = None
    h_plate: Optional[str] = None
    t_plate: Optional[str] = None
    fuel_type: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    driver_name: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    remark: Optional[str] = None
    locat_recive: Optional[str] = None
    date_recive: Optional[date] = None
    locat_deliver: Optional[str] = None
    date_deliver: Optional[date] = None
    pallet_type: Optional[str] = None
    pallet_plan: Optional[int] = None
    unload_cost: Optional[str] = None
    # ไม่ต้องมี load_id ใน update schema

    class Config:
        orm_mode = True
