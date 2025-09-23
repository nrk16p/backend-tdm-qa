from sqlalchemy import Column, String, Integer, Date, DateTime
from .database import Base

class User(Base):
    __tablename__ = "userdata"
    __table_args__ = {'schema': 'fleetdata'}  # 👈 schema

    username = Column(String, primary_key=True, index=True)
    hashed_password = Column("password", String)  # map DB column
    role = Column(String)

    # New fields for tracking login
    latlng_current = Column(String, nullable=True)
    timestamp_login = Column(DateTime(timezone=True), nullable=True)



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
    date_recive = Column(DateTime)
    locat_deliver = Column(String)
    date_deliver = Column(DateTime)
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
    latlng_recive = Column(String)
    latlng_deliver = Column(String)

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
    start_latlng= Column(String)
    origin_latlng= Column(String)
    start_recive_latlng= Column(String)
    end_recive_latlng= Column(String)
    intransit_latlng= Column(String)
    desination_latlng= Column(String)
    start_unload_latlng= Column(String)
    end_unload_latlng= Column(String)
    complete_latlng= Column(String)
    docs_submitted_datetime= Column(String)
    docs_returned_datetime= Column(String)
    
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
    

class PalletLog(Base):
    __tablename__ = "palletlog"
    __table_args__ = {"schema": "fleetdata"}

    # composite primary key to make SQLAlchemy happy
    timestamp = Column(DateTime, primary_key=True, index=True)
    driver_name = Column(String, primary_key=True, index=True)
    t_plate = Column(String, primary_key=True, index=True)

    pallet_current = Column(Integer)              # int2 in PG maps fine to Integer
    pallet_type = Column(String, nullable=False)
    pallet_qty = Column(Integer, nullable=False)  # int2
    pallet_location = Column(String, nullable=False)
    pallet_remark = Column(String)                # nullable
    
class VLatestPalletLog(Base):
    __tablename__ = "v_latest_palletlog"   # your view
    __table_args__ = {"schema": "fleetdata"}

    timestamp = Column(DateTime)
    t_plate = Column(String, primary_key=True)   # each t_plate has 1 latest row
    pallet_current = Column(Integer)