from sqlalchemy import Column, String, Integer, Date
from .database import Base

# ── User Model ───────────────────────────────────────
class User(Base):
    __tablename__ = "userdata"
    __table_args__ = {'schema': 'fleetdata'}  # 👈 ระบุ schema ชัดเจน

    username = Column(String, primary_key=True, index=True)
    hashed_password = Column("password", String)  # 👈 map จาก column password จริงใน DB
    role = Column(String)

# ── Job Model ────────────────────────────────────────
class Job(Base):
    __tablename__ = "jobdata"
    __table_args__ = {"schema": "fleetdata"}

    load_id = Column(String, primary_key=True, index=True)
    date_plan = Column(Date)
    h_plate = Column(String)
    t_plate = Column(String)
    fuel_type = Column(String)
    height = Column(String)
    weight = Column(String)
    driver_name = Column(String)
    phone = Column(String)
    status = Column(String)
    remark = Column(String)
    locat_recive = Column(String)
    date_recive = Column(Date)
    locat_deliver = Column(String)
    date_deliver = Column(Date)
    pallet_type = Column(String)
    pallet_plan = Column(Integer)
    unload_cost = Column(String)
    
class Ticket(Base):
    __tablename__ = "ticketdata"
    __table_args__ = {"schema": "fleetdata"}

    load_id = Column(String, primary_key=True, index=True)
    start_datetime = Column(String)
    origin_datetime = Column(String)
    start_recive_datetime = Column(String)
    end_recive_datetime = Column(String)
    intransit_datetime = Column(String)
    desination_datetime = Column(String)
    start_unload_datetime = Column(String)
    end_unload_datetime = Column(String)
    complete_datetime = Column(String)
    
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

# Palletdata table
class Palletdata(Base):
    __tablename__ = "palletdata"
    id = Column(Integer, primary_key=True, autoincrement=True)
    load_id = Column(String(100), nullable=False)
    tranfer_pallet = Column(Integer)
    change_pallet = Column(Integer)
    drop_pallet = Column(Integer)
    return_pallet = Column(Integer)
    borrow_customer_pallet = Column(Integer)
    return_customer_pallet = Column(Integer)
    start_unload_datetime = Column(Integer)
    end_unload_datetime = Column(Integer)
    complete_datetime = Column(Integer)