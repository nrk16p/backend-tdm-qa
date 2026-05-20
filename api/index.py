from fastapi import FastAPI, Depends, HTTPException, Body, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime
from sqlalchemy import desc
from fastapi.responses import JSONResponse
from typing import Optional
from . import models, auth, database
from .database import SessionLocal
from .schemas import TicketUpdate , PalletDataUpdate , JobSchema , JobUpdateSchema , JobSchemaPut , JobUpdateSchemaCreate , RegisterRequest , ChangePasswordRequest , PalletLogRead , LatestPalletLogRead , UserSchema , VehicleCurrentDataOut , VehicleCurrentDataCreate
from fastapi import Header, HTTPException, status
from datetime import datetime
from typing import List
from .auth import hash_password
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import hashlib

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="TDM Backend API",
    description="API สำหรับ TDM Fleet Management",
    version="2.2.4",    # << ใส่ version ที่ต้องการ
    contact={
        "name": "Plug",
        "email": "narongkorn.a@menatransport.co.th",
    }
)
@app.get("/")
def root():
    return {"message": "backend-tdm"}

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Login ---
API_SECRET_KEY = "=E=QY]!{PjD53Mq"

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key"
        )

@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    latlng_current: str | None = Header(default=None)  # optional header
):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    # Generate timestamp at login
    timestamp_login = datetime.now(ZoneInfo("Asia/Bangkok"))

    # ✅ Update user record in DB
    user.latlng_current = latlng_current
    user.timestamp_login = timestamp_login
    db.add(user)
    db.commit()
    db.refresh(user)  # make sure updated fields are available in this session

    # Token payload
    token_data = {
        "sub": user.username,
        "role": user.role,
        "timestamp_login": timestamp_login.isoformat()
    }
    if latlng_current:
        token_data["latlng_current"] = latlng_current

    # Create JWT
    access_token = auth.create_access_token(data=token_data)

    # Response
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "latlng_current": latlng_current,
        "timestamp_login": timestamp_login.isoformat()
    }
@app.post("/register")
def register(
    data: RegisterRequest = Body(...),
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key)  # <<< ต้องใช้ API KEY ทุกครั้ง
):
    # เช็ค duplicate
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    # Hash password
    hashed = hash_password(data.password)
    user = models.User(username=data.username, hashed_password=hashed, role=data.role)
    db.add(user)
    db.commit()
    return {"message": f"User '{data.username}' registered successfully!"}

@app.post("/users/reset-password")
def change_password(
    data: ChangePasswordRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # ตรวจสอบว่า user ที่จะเปลี่ยนเป็นของตัวเอง หรือถ้าเป็น admin เปลี่ยนให้คนอื่นได้
    if current_user.role != "admin" and current_user.username != data.user:
        raise HTTPException(status_code=403, detail="Not authorized to change this password")

    # หา user ใน DB
    user = db.query(models.User).filter(models.User.username == data.user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ตรวจสอบ old_password (ถ้าไม่ใช่ admin)
    if current_user.role != "admin":
        if not auth.verify_password(data.old_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Old password is incorrect")

    # update password ใหม่
    user.hashed_password = hash_password(data.new_password)
    db.commit()

    return {"message": f"Password for '{data.user}' changed successfully"}

from zoneinfo import ZoneInfo
from datetime import datetime

@app.get("/user")
def get_users(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    users = db.query(models.User).filter(models.User.role == "user").all()
    result = []

    for user in users:
        ts = user.timestamp_login
        if ts:
            if ts.tzinfo is None:
                # ✅ Interpret naive DB timestamp as Asia/Bangkok (not UTC)
                ts_bkk = datetime(
                    ts.year, ts.month, ts.day,
                    ts.hour, ts.minute, ts.second, ts.microsecond,
                    tzinfo=ZoneInfo("Asia/Bangkok")
                )
            else:
                # If already tz-aware, convert properly
                ts_bkk = ts.astimezone(ZoneInfo("Asia/Bangkok"))

            result.append({
                "username": user.username,
                "role": user.role,
                "latlng_current": user.latlng_current,
                "timestamp_login": ts_bkk.isoformat()  # Bangkok tz
            })
        else:
            result.append({
                "username": user.username,
                "role": user.role,
                "latlng_current": user.latlng_current,
                "timestamp_login": user.timestamp_login,

                "timestamp_login": None
            })

    return {"users": result}


@app.get("/jobs")
def get_jobs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),

    load_id: Optional[List[str]] = Query(None),
    h_plate: Optional[List[str]] = Query(None),
    t_plate: Optional[List[str]] = Query(None),
    locat_recive: Optional[List[str]] = Query(None),
    date_recive: Optional[List[str]] = Query(None),
    locat_deliver: Optional[List[str]] = Query(None),
    date_deliver: Optional[List[str]] = Query(None),
    driver_name: Optional[List[str]] = Query(None),
    status: Optional[List[str]] = Query(None),
    date_plan_start: Optional[date] = Query(None),
    date_plan_end: Optional[date] = Query(None),
):
    query = db.query(models.Job)

    # === 1. Filter by role ===
    if current_user.role != "admin":
        query = query.filter(models.Job.driver_name == current_user.username)

    # === 2. Filter date_plan ===
    if date_plan_start:
        query = query.filter(models.Job.date_plan >= date_plan_start)
    if date_plan_end:
        query = query.filter(models.Job.date_plan <= date_plan_end)

    # === 3. Default 7-day window for non-admins ===
    if current_user.role != "admin" and not date_plan_start and not date_plan_end:
        today_date = date.today()
        start_date = today_date - timedelta(days=7)
        end_date = today_date + timedelta(days=7)
        query = query.filter(
            models.Job.date_recive >= start_date,
            models.Job.date_recive <= end_date
        )

    # === 4. Field filters ===
    if load_id:
        query = query.filter(models.Job.load_id.in_(load_id))
    if h_plate:
        query = query.filter(models.Job.h_plate.in_(h_plate))
    if t_plate:
        query = query.filter(models.Job.t_plate.in_(t_plate))
    if locat_recive:
        query = query.filter(models.Job.locat_recive.in_(locat_recive))
    if date_recive:
        query = query.filter(models.Job.date_recive.in_(date_recive))
    if locat_deliver:
        query = query.filter(models.Job.locat_deliver.in_(locat_deliver))
    if date_deliver:
        query = query.filter(models.Job.date_deliver.in_(date_deliver))
    if driver_name:
        query = query.filter(models.Job.driver_name.in_(driver_name))
    if status:
        query = query.filter(
            func.lower(func.trim(models.Job.status)).in_(
                [s.strip().lower() for s in status]
            )
        )

    jobs = query.all()

    # === Sorting ===
    sorted_jobs = sorted(
        jobs,
        key=lambda job: (
            0 if job.status not in ["พร้อมรับงาน", "จัดส่งแล้ว (POD)"] else 1,
            0 if job.date_plan == date.today() else 1,
            -job.date_plan.toordinal() if job.date_plan else 0
        )
    )

    # === Lookup all drivers ===
    driver_names = {job.driver_name for job in sorted_jobs if job.driver_name}
    users = db.query(models.User).filter(models.User.username.in_(driver_names)).all()
    user_map = {u.username: u for u in users}

    # === Lookup all tickets ===
    load_ids = {job.load_id for job in sorted_jobs if job.load_id}
    tickets = db.query(models.Ticket).filter(models.Ticket.load_id.in_(load_ids)).all()
    ticket_map = {t.load_id: t for t in tickets}
    
    # === Lookup all dw_jobdata ===
    dw_jobs = db.query(models.DWJobData).filter(models.DWJobData.load_id.in_(load_ids)).all()
    dw_map = {d.load_id: d for d in dw_jobs}
    
    h_plates = {job.h_plate for job in sorted_jobs if job.h_plate}
    vehicles = (
        db.query(models.VehicleCurrentData)
        .filter(models.VehicleCurrentData.plate_master.in_(h_plates))
        .all()
    )
    vehicle_map = {v.plate_master: v for v in vehicles}
    
    job_dicts = []
    for job in sorted_jobs:
        job_dict = job.__dict__.copy()

        # Add driver info
        driver = user_map.get(job.driver_name)
        job_dict["driver_info"] = {
            "latlng_current": driver.latlng_current if driver else None,
            "timestamp_login": (
                driver.timestamp_login.astimezone(ZoneInfo("Asia/Bangkok")).isoformat()
                if driver and driver.timestamp_login else None
            )
        }

        # Add ticket info
        ticket = ticket_map.get(job.load_id)
        job_dict["ticket_info"] = {
            "start_datetime": ticket.start_datetime if ticket else None,
            "origin_datetime": ticket.origin_datetime if ticket else None,
            "start_recive_datetime": ticket.start_recive_datetime if ticket else None,
            "end_recive_datetime": ticket.end_recive_datetime if ticket else None,
            "intransit_datetime": ticket.intransit_datetime if ticket else None,
            "desination_datetime": ticket.desination_datetime if ticket else None,
            "start_unload_datetime": ticket.start_unload_datetime if ticket else None,
            "end_unload_datetime": ticket.end_unload_datetime if ticket else None,
            "complete_datetime": ticket.complete_datetime if ticket else None,
            "docs_submitted_datetime": ticket.docs_submitted_datetime if ticket else None,
            "docs_returned_datetime": ticket.docs_returned_datetime if ticket else None,

            # ---- latlng fields ----
            "start_latlng": ticket.start_latlng if ticket else None,
            "origin_latlng": ticket.origin_latlng if ticket else None,
            "start_recive_latlng": ticket.start_recive_latlng if ticket else None,
            "end_recive_latlng": ticket.end_recive_latlng if ticket else None,
            "intransit_latlng": ticket.intransit_latlng if ticket else None,
            "desination_latlng": ticket.desination_latlng if ticket else None,
            "start_unload_latlng": ticket.start_unload_latlng if ticket else None,
            "end_unload_latlng": ticket.end_unload_latlng if ticket else None,
            "complete_latlng": ticket.complete_latlng if ticket else None,
            "docs_submitted_latlng": ticket.docs_submitted_latlng if ticket else None,
            "docs_returned_latlng": ticket.docs_returned_latlng if ticket else None,
        }
        # DWJobData info
        dw = dw_map.get(job.load_id)
        job_dict["dw_jobdata_info"] = {

            "client_kpi_origin": dw.client_kpi_origin if dw else None,
            "client_kpi_destination": dw.client_kpi_destination if dw else None,

        }
        
            # ---- Vehicle Info (NEW) ----
        vehicle = vehicle_map.get(job.h_plate)
        job_dict["vehicle_info"] = {
            "gps_vendor": vehicle.gps_vendor if vehicle else None,
            "gps_id": vehicle.gps_id if vehicle else None,
            "current_latlng": vehicle.current_latlng if vehicle else None,
            "status": vehicle.status if vehicle else None,
            "gps_updated_at": (
                vehicle.gps_updated_at.isoformat()
                if vehicle and vehicle.gps_updated_at else None
            ),
        }
        job_dicts.append(job_dict)

    return {
        "role": current_user.role,
        "jobs": job_dicts,
    }
    
ALLOWED_GROUP_FIELDS = {
    "start_datetime",
    "origin_datetime",
    "start_recive_datetime",
    "end_recive_datetime",
}



def _is_group_wide_update(update_fields: dict) -> bool:
    """
    เงื่อนไข “อัปเดตทั้งกลุ่ม” = ทุกคีย์ที่อัปเดตต้องอยู่ใน ALLOWED_GROUP_FIELDS
    และมีอย่างน้อย 1 คีย์
    """
    return (
        len(update_fields) > 0 and
        all(k in ALLOWED_GROUP_FIELDS for k in update_fields.keys())
    )

def compute_status(ticket):
    # เช็คสถานะจากล่าสุด -> ย้อนหลัง
    if ticket.complete_datetime:        return "จัดส่งแล้ว (POD)"
    if ticket.end_unload_datetime:      return "ลงสินค้าเสร็จ"
    if ticket.start_unload_datetime:    return "เริ่มลงสินค้า"
    if ticket.desination_datetime:      return "ถึงปลายทาง"   # ชื่อฟิลด์สะกดตามโมเดลเดิม
    if ticket.intransit_datetime:       return "เริ่มขนส่ง"
    if ticket.end_recive_datetime:      return "ขึ้นสินค้าเสร็จ"
    if ticket.start_recive_datetime:    return "เริ่มขึ้นสินค้า"
    if ticket.origin_datetime:          return "ถึงต้นทาง"
    if ticket.start_datetime:           return "รับงาน"
    return "พร้อมรับงาน"

def compute_status_neo(ticket):
    # เช็คสถานะจากล่าสุด -> ย้อนหลัง
    if ticket.complete_datetime:        return "จัดส่งแล้ว (POD)"
    if ticket.docs_returned_datetime:   return "ได้รับเอกสารคืน"
    if ticket.end_unload_datetime:      return "ลงสินค้าเสร็จ"
    if ticket.start_unload_datetime:    return "เริ่มลงสินค้า"
    if ticket.docs_submitted_datetime:  return "ยื่นเอกสาร"
    if ticket.desination_datetime:      return "ถึงปลายทาง"   # ชื่อฟิลด์สะกดตามโมเดลเดิม
    if ticket.intransit_datetime:       return "เริ่มขนส่ง"
    if ticket.end_recive_datetime:      return "ขึ้นสินค้าเสร็จ"
    if ticket.start_recive_datetime:    return "เริ่มขึ้นสินค้า"
    if ticket.origin_datetime:          return "ถึงต้นทาง"
    if ticket.start_datetime:           return "รับงาน"
    return "พร้อมรับงาน"

def compute_status(ticket):
    # เช็คสถานะจากล่าสุด -> ย้อนหลัง
    if ticket.complete_datetime:        return "จัดส่งแล้ว (POD)"
    if ticket.end_unload_datetime:      return "ลงสินค้าเสร็จ"
    if ticket.start_unload_datetime:    return "เริ่มลงสินค้า"
    if ticket.desination_datetime:      return "ถึงปลายทาง"   # ชื่อฟิลด์สะกดตามโมเดลเดิม
    if ticket.intransit_datetime:       return "เริ่มขนส่ง"
    if ticket.end_recive_datetime:      return "ขึ้นสินค้าเสร็จ"
    if ticket.start_recive_datetime:    return "เริ่มขึ้นสินค้า"
    if ticket.origin_datetime:          return "ถึงต้นทาง"
    if ticket.start_datetime:           return "รับงาน"
    return "พร้อมรับงาน"


def compute_status_neo(ticket):
    # เช็คสถานะจากล่าสุด -> ย้อนหลัง
    if ticket.complete_datetime:        return "จัดส่งแล้ว (POD)"
    if ticket.docs_returned_datetime:   return "ได้รับเอกสารคืน"
    if ticket.end_unload_datetime:      return "ลงสินค้าเสร็จ"
    if ticket.start_unload_datetime:    return "เริ่มลงสินค้า"
    if ticket.docs_submitted_datetime:  return "ยื่นเอกสาร"
    if ticket.desination_datetime:      return "ถึงปลายทาง"   # ชื่อฟิลด์สะกดตามโมเดลเดิม
    if ticket.intransit_datetime:       return "เริ่มขนส่ง"
    if ticket.end_recive_datetime:      return "ขึ้นสินค้าเสร็จ"
    if ticket.start_recive_datetime:    return "เริ่มขึ้นสินค้า"
    if ticket.origin_datetime:          return "ถึงต้นทาง"
    if ticket.start_datetime:           return "รับงาน"
    return "พร้อมรับงาน"


# 🗺️ Mapping locat_recive → compute function
STATUS_FUNC_MAP = {
    "บริษัท นีโอ แฟคทอรี่ จำกัด": compute_status_neo,
    # สามารถเพิ่ม mapping บริษัทอื่นได้ที่นี่
}


@app.post("/job-tickets")
def create_or_update_ticket(
    data: TicketUpdate = Body(...),
    apply_to_group: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    anchor = db.query(models.Job).filter(models.Job.load_id == data.load_id).first()
    if not anchor:
        raise HTTPException(status_code=404, detail="load_id not found in jobdata")

    # สร้าง dict ฟิลด์ที่จะอัปเดต (ไม่รวม load_id) และทำความสะอาดค่าว่าง
    def _clean_value(v):
        # Convert empty string → None
        if v == "" or v is None:
            return None
        return v

    raw_update_fields = {
        k: _clean_value(v)
        for k, v in data.dict(exclude_unset=True).items()
        if k != "load_id"
    }
    update_fields = raw_update_fields

    # ตัดสินใจว่าจะอัปเดตทั้งกลุ่มหรือไม่
    group_mode = (
        apply_to_group
        and getattr(anchor, "group_key", None)
        and _is_group_wide_update(update_fields)
    )

    if group_mode:
        group_load_ids = [
            r[0]
            for r in db.query(models.Job.load_id)
                      .filter(models.Job.group_key == anchor.group_key)
                      .all()
        ]
    else:
        group_load_ids = [data.load_id]

    affected = []
    try:
        for lid in group_load_ids:
            ticket = db.query(models.Ticket).filter(models.Ticket.load_id == lid).first()
            job = db.query(models.Job).filter(models.Job.load_id == lid).first()

            if ticket:
                for f, val in update_fields.items():
                    setattr(ticket, f, val)
            else:
                payload = {**update_fields, "load_id": lid}
                ticket = models.Ticket(**payload)
                db.add(ticket)

            db.flush()  # ให้ ticket ได้ค่าล่าสุดก่อนคำนวณสถานะ

            # --- เลือกฟังก์ชันสถานะตามบริษัท ---
            if job and job.locat_recive in STATUS_FUNC_MAP:
                status_func = STATUS_FUNC_MAP[job.locat_recive]
            else:
                status_func = compute_status

            status = status_func(ticket)

            if job and status:
                job.status = status

            affected.append({"load_id": lid, "status": status})

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "message": "✅ Tickets updated" if len(affected) > 1 else "✅ Ticket updated",
        "apply_to_group": bool(group_mode),
        "group_size": len(affected),
        "affected": affected,
    }
@app.get("/job-tickets")
def get_job_tickets(
    load_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if not load_id:
        raise HTTPException(status_code=400, detail="Missing load_id")

    job = db.query(models.Job).filter(models.Job.load_id == load_id).first()
    if not job:
        return {"message": f"No job found with load_id = {load_id}"}

    ticket = db.query(models.Ticket).filter(models.Ticket.load_id == load_id).first()
    pallet = db.query(models.Palletdata).filter(models.Palletdata.load_id == load_id).first()  # << เพิ่มตรงนี้

    job_dict = job.__dict__.copy()
    job_dict["ticket"] = ticket.__dict__ if ticket else None
    job_dict["palletdata"] = pallet.__dict__ if pallet else None   # << เพิ่มตรงนี้

    return job_dict



@app.post("/palletdata")
def create_or_update_palletdata(
    data: PalletDataUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # ตรวจสอบว่ามี job นี้หรือไม่ (optionally)
    job = db.query(models.Job).filter(models.Job.load_id == data.load_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="load_id not found in jobdata")

    # ค้นหา palletdata ที่มี load_id นี้
    pallet = db.query(models.Palletdata).filter(models.Palletdata.load_id == data.load_id).first()

    if pallet:
        # update
        for field, value in data.dict(exclude_unset=True).items():
            if field != "load_id":
                setattr(pallet, field, value)
        db.commit()
        db.refresh(pallet)
        message = "✅ Palletdata updated"
    else:
        # create
        new_pallet = models.Palletdata(**data.dict())
        db.add(new_pallet)
        db.commit()
        db.refresh(new_pallet)
        pallet = new_pallet
        message = "✅ Palletdata created"

    return {
        "message": message,
        "palletdata": pallet.__dict__,
    }
def model_to_dict(obj):
    if not obj:
        return None
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
 
from sqlalchemy import func

@app.post("/jobs")
def create_job(
    data: JobUpdateSchemaCreate = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    now = datetime.now()

    # 1. สร้างรหัส load_id ใหม่อัตโนมัติ
    # สมมุติว่า date_plan ส่งมาเป็น date/datetime ใน data
    if not data.date_plan:
        raise HTTPException(status_code=400, detail="date_plan is required")

    # YYMMDD (เช่น 250806)
    yymmdd = data.date_plan.strftime("%y%m%d")
    
    # Query หาจำนวน job ของวันเดียวกันนี้
    jobs_count = db.query(func.count(models.Job.load_id)) \
        .filter(models.Job.date_plan == data.date_plan).scalar()
    # รันนัมเบอร์ใหม่ (+1 เพราะเริ่มจาก 1)
    running = jobs_count + 1

    # Padding ด้วย 0 (เช่น 001)
    running_str = f"{running:03d}"

    load_id = f"TDM-{yymmdd}-{running_str}"

    # double-check กัน insert ซ้ำ (น้อยมากจะเกิด)
    if db.query(models.Job).filter(models.Job.load_id == load_id).first():
        raise HTTPException(status_code=400, detail="Duplicate load_id, try again")

    # 2. Create Job
    new_job = models.Job(
        **data.dict(exclude={"created_at", "updated_at", "created_by", "updated_by", "load_id"}),
        load_id=load_id,
        created_by=current_user.username,
        created_at=now,
        updated_by=current_user.username,
        updated_at=now,
    )
    db.add(new_job)
    
    # 3. Auto create Ticket (เฉพาะ load_id)
    new_ticket = models.Ticket(load_id=load_id)
    db.add(new_ticket)

    # 4. Auto create Palletdata (เฉพาะ load_id)
    new_pallet = models.Palletdata(load_id=load_id)
    db.add(new_pallet)
    
    # 5. Commit ทุกอย่าง
    db.commit()
    db.refresh(new_job)
    
    return {
        "message": "✅ Job created",
        "job": model_to_dict(new_job),
        "load_id": load_id
    }

@app.put("/jobs")
def update_jobs(
    data_list: List[JobSchemaPut] = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    🔁 Update multiple jobs in a single request.
    Each item must include `load_id`.
    """
    now = datetime.now()
    updated_jobs = []
    not_found = []

    for data in data_list:
        load_id = data.load_id
        job = db.query(models.Job).filter(models.Job.load_id == load_id).first()

        if not job:
            not_found.append(load_id)
            continue

        for field, value in data.dict(exclude_unset=True).items():
            setattr(job, field, value)

        job.updated_at = now
        job.updated_by = current_user.username
        updated_jobs.append(job)

    db.commit()

    for job in updated_jobs:
        db.refresh(job)

    return {
        "message": f"✅ Updated {len(updated_jobs)} job(s) successfully",
        "updated_jobs": [model_to_dict(j) for j in updated_jobs],
        "not_found": not_found
    }

@app.delete("/jobs")
def delete_job(
    load_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    job = db.query(models.Job).filter(models.Job.load_id == load_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # 1. ลบ Ticket
    ticket = db.query(models.Ticket).filter(models.Ticket.load_id == load_id).first()
    if ticket:
        db.delete(ticket)

    # 2. ลบ Palletdata
    pallet = db.query(models.Palletdata).filter(models.Palletdata.load_id == load_id).first()
    if pallet:
        db.delete(pallet)

    # 3. ลบ Job
    db.delete(job)
    db.commit()
    return {"message": "✅ Job, Ticket, Palletdata deleted"}

from sqlalchemy import func
from typing import List

@app.post("/jobs/bulk")
def create_jobs_bulk(
    data: List[JobUpdateSchemaCreate] = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    now = datetime.now()
    results = []

    # cache นับจำนวน job ของแต่ละวันก่อน insert ในรอบนี้
    running_count_map = {}

    for job_in in data:
        if not job_in.date_plan:
            results.append({
                "load_id": None,
                "status": "❌ date_plan required"
            })
            continue

        yymmdd = job_in.date_plan.strftime("%y%m%d")
        key = str(job_in.date_plan)

        # นับ job ที่อยู่ใน DB แล้ว + job ที่เตรียมจะ insert ในรอบนี้
        if key not in running_count_map:
            jobs_count = db.query(func.count(models.Job.load_id)).filter(models.Job.date_plan == job_in.date_plan).scalar()
            running_count_map[key] = jobs_count

        running_count_map[key] += 1
        running_str = f"{running_count_map[key]:03d}"
        load_id = f"TDM-{yymmdd}-{running_str}"

        # Duplicate check
        if db.query(models.Job).filter(models.Job.load_id == load_id).first():
            results.append({
                "load_id": load_id,
                "status": "❌ duplicate"
            })
            continue

        # Insert JOB
        new_job = models.Job(
            **job_in.dict(exclude={"created_at", "updated_at", "created_by", "updated_by", "load_id"}),
            load_id=load_id,
            created_by=current_user.username,
            created_at=now,
            updated_by=current_user.username,
            updated_at=now,
        )
        db.add(new_job)

        # Insert Ticket & Palletdata
        db.add(models.Ticket(load_id=load_id))
        db.add(models.Palletdata(load_id=load_id))

        results.append({
            "load_id": load_id,
            "status": "✅ created"
        })

    db.commit()
    return {"results": results}

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from . import models, auth
from .schemas import PalletLogCreate, PalletLogOut

@app.post("/palletlogs", response_model=PalletLogOut)
def create_palletlog(
    data: PalletLogCreate = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # 1. Check duplicate (timestamp + driver + plate)
    exists = db.query(models.PalletLog).filter(
        models.PalletLog.timestamp == data.timestamp,
        models.PalletLog.driver_name == data.driver_name,
        models.PalletLog.t_plate == data.t_plate,
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Duplicate palletlog for this key")

    # 2. Get latest palletlog for this t_plate
    last_log = (
        db.query(models.PalletLog)
        .filter(models.PalletLog.t_plate == data.t_plate)
        .order_by(models.PalletLog.timestamp.desc())
        .first()
    )

    # 3. Use last pallet_current (None → 0 if missing)
    last_current = (last_log.pallet_current or 0) if last_log else 0

    # 4. Calculate new pallet_current
    if data.pallet_type in ["รับคืน", "ยืมลค."]:
        new_current = last_current + data.pallet_qty
    elif data.pallet_type in ["นำฝาก", "คืนลค."]:
        new_current = last_current - data.pallet_qty
    else:
        new_current = last_current

    # 5. Create row (exclude pallet_current from request)
    row = models.PalletLog(
        **data.dict(exclude={"pallet_current"}),
        pallet_current=new_current
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    # 6. Return response
    return PalletLogOut(
        message="Pallet log created successfully",
        pallet_current=new_current,
        last_timestamp=last_log.timestamp if last_log else None
    )

from typing import List, Optional, Union

@app.get("/palletlogs", response_model=List[PalletLogRead])
def list_palletlogs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),

    # filters
    start: Optional[datetime] = Query(None, description="timestamp >= start"),
    end: Optional[datetime] = Query(None, description="timestamp <= end"),
    driver_name: Optional[Union[List[str], str]] = Query(None),
    t_plate: Optional[Union[List[str], str]] = Query(None),
    pallet_type: Optional[Union[List[str], str]] = Query(None),
    pallet_location: Optional[Union[List[str], str]] = Query(None),

    # pagination
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    q = db.query(models.PalletLog)

    # --- role-based filter ---
    if current_user.role == "user":
        q = q.filter(models.PalletLog.driver_name == current_user.username)

    # --- normalize filters ---
    def normalize(val):
        if not val:
            return None
        if isinstance(val, str):
            return [v.strip() for v in val.split(",") if v.strip()]
        return [v.strip() for v in val]

    driver_name = normalize(driver_name)
    t_plate = normalize(t_plate)
    pallet_type = normalize(pallet_type)
    pallet_location = normalize(pallet_location)

    # --- apply filters ---
    if start:
        q = q.filter(models.PalletLog.timestamp >= start)
    if end:
        q = q.filter(models.PalletLog.timestamp <= end)
    if driver_name:
        q = q.filter(models.PalletLog.driver_name.in_(driver_name))
    if t_plate:
        q = q.filter(models.PalletLog.t_plate.in_(t_plate))
    if pallet_type:
        q = q.filter(models.PalletLog.pallet_type.in_(pallet_type))
    if pallet_location:
        q = q.filter(models.PalletLog.pallet_location.in_(pallet_location))

    rows = (
        q.order_by(models.PalletLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows

@app.get("/latest_palletlog", response_model=List[LatestPalletLogRead])
def get_latest_palletlog(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
    t_plate: Optional[List[str]] = Query(None, description="Filter by truck plate(s)"),
):
    q = db.query(models.VLatestPalletLog)



    # optional filter
    if t_plate:
        q = q.filter(models.VLatestPalletLog.t_plate.in_(t_plate))

    rows = q.all()
    return rows


@app.post("/gpsdata", response_model=List[VehicleCurrentDataCreate])
def upsert_vehicle_data(
    data_list: List[VehicleCurrentDataCreate] = Body(...),
    db: Session = Depends(get_db),
):
    """
    ✅ Always bulk UPSERT for Vehicle Current Data
    - Accepts multiple records in one POST
    - If gps_vendor = 'dtc' → match gps_id
    - If gps_vendor = 'thaitracking' → match plate_master
    - Updates if exists, inserts if new
    """
    results = []
    inserted, updated = 0, 0

    for data in data_list:
        # 1️⃣ Determine lookup field
        if data.gps_vendor == "dtc"
            lookup_field = models.VehicleCurrentData.gps_id
            lookup_value = data.gps_id
        elif data.gps_vendor in ("thaitracking", "hino"):
            lookup_field = models.VehicleCurrentData.plate_master
            lookup_value = data.plate_master
        else:
            print(f"⚠️ Skipping unknown vendor: {data.gps_vendor}")
            continue

        # 2️⃣ Find existing record
        record = db.query(models.VehicleCurrentData).filter(lookup_field == lookup_value).first()

        # 3️⃣ Update or Insert
        if record:
            for key, value in data.dict(exclude_unset=True).items():
                setattr(record, key, value)
            record.updated_at = datetime.utcnow()
            updated += 1
        else:
            record = models.VehicleCurrentData(
                **data.dict(),
                updated_at=datetime.utcnow(),
            )
            db.add(record)
            inserted += 1

        results.append(record)

    # 4️⃣ Commit once for performance
    db.commit()
    for r in results:
        db.refresh(r)

    print(f"✅ Vehicle upsert complete → Inserted: {inserted}, Updated: {updated}, Total: {len(results)}")
    return results
