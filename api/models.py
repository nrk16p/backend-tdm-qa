from sqlalchemy import Column, String, Integer, Date, DateTime
from .database import Base

# ── User Model ───────────────────────────────────────
class User(Base):
    __tablename__ = "userdata"
    __table_args__ = {'schema': 'fleetdata'}  # 👈 ระบุ schema ชัดเจน

    username = Column(String, primary_key=True, index=True)
    hashed_password = Column("password", String)  # 👈 map จาก column password จริงใน DB
    role = Column(String)



from sqlalchemy.dialects.postgresql import UUID

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
    newdate_recive = Column(DateTime)
    newdate_deliver = Column(DateTime)
    locat_deliver = Column(String)
    date_deliver = Column(Date)
    pallet_type = Column(String)
    pallet_plan = Column(Integer)
    unload_cost = Column(String)
    created_by = Column(String(100))
    created_at = Column(DateTime)
    updated_by = Column(String(100))
    updated_at = Column(DateTime)
    job_type = Column(String)
    ldt = Column(String)
    damage_detail = Column(String)
    roll_trip = Column(Integer)

    # DB-generated columns (don’t set these on insert)
    group_key = Column(String)                 # keep if you still have it
    group_key_uuid = Column(UUID(as_uuid=True), index=True)
       
    
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
    
# Palletdata table
class Palletdata(Base):
    __tablename__ = "palletdata"
    __table_args__ = {"schema": "fleetdata"}

    load_id = Column(String, primary_key=True, index=True)
    tranfer_pallet = Column(Integer)
    change_pallet = Column(Integer)
    drop_pallet = Column(Integer)
    return_pallet = Column(Integer)
    borrow_customer_pallet = Column(Integer)
    return_customer_pallet = Column(Integer)
    

