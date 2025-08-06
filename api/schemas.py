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
        


from pydantic import BaseModel, model_validator
from typing import Optional
from datetime import date, datetime

class JobUpdateSchema(BaseModel):
    load_id: str
    date_plan: date
    h_plate: str
    t_plate: str
    driver_name: str
    status: str
    locat_recive: str
    date_recive: date
    locat_deliver: str
    date_deliver: date
    pallet_type: str
    pallet_plan: int
    created_by: str
    created_at: date

    # Optional fields
    fuel_type: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    phone: Optional[str] = None
    remark: Optional[str] = None
    unload_cost: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None

    @model_validator(mode="after")
    def no_empty_required(self):
        required_fields = [
            'load_id', 'date_plan', 'h_plate', 't_plate', 'driver_name', 'status',
            'locat_recive', 'date_recive', 'locat_deliver', 'date_deliver',
            'pallet_type', 'pallet_plan', 'created_by', 'created_at'
        ]
        for field in required_fields:
            v = getattr(self, field)
            if v is None or (isinstance(v, str) and v.strip() == ""):
                raise ValueError(f"{field} is required and cannot be empty")
        return self
    
class JobSchemaPut(BaseModel): 
    load_id: Optional[str] = None
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
        
class JobUpdateSchemaCreate(BaseModel):
    load_id:  Optional[str] = None
    date_plan: date
    h_plate: str
    t_plate: str
    driver_name: str
    status: str
    locat_recive: str
    date_recive: str
    locat_deliver: str
    date_deliver: str
    pallet_type: str
    pallet_plan: int
    created_by: str
    created_at: date

    # Optional fields
    fuel_type: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    phone: Optional[str] = None
    remark: Optional[str] = None
    unload_cost: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None

    @model_validator(mode="after")
    def no_empty_required(self):
        required_fields = [
             'date_plan', 'h_plate', 't_plate', 'driver_name', 'status',
            'locat_recive', 'date_recive', 'locat_deliver', 'date_deliver',
            'pallet_type', 'pallet_plan', 'created_by', 'created_at'
        ]
        for field in required_fields:
            v = getattr(self, field)
            if v is None or (isinstance(v, str) and v.strip() == ""):
                raise ValueError(f"{field} is required and cannot be empty")
        return self