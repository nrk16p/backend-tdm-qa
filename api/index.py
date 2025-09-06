from fastapi import FastAPI, Depends, HTTPException, Body, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime
from sqlalchemy import desc
from fastapi.responses import JSONResponse
from typing import Optional
from . import models, auth, database
from .database import SessionLocal
from .schemas import TicketUpdate , PalletDataUpdate , JobSchema , JobUpdateSchema , JobSchemaPut , JobUpdateSchemaCreate , RegisterRequest , ChangePasswordRequest , PalletLogRead , LatestPalletLogRead
from fastapi import Header, HTTPException, status
from datetime import datetime
from typing import List
from .auth import hash_password

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="TDM Backend API",
    description="API สำหรับ TDM Fleet Management",
    version="2.2.1",    # << ใส่ version ที่ต้องการ
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
@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token = auth.create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer","role": user.role}

API_SECRET_KEY = "=E=QY]!{PjD53Mq"
def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key"
        )

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


@app.get("/user")
def get_users(
    db: Session = Depends(get_db),
        api_key: str = Depends(verify_api_key),   

):
    users = db.query(models.User).filter(models.User.role == "user").all()
    result = [
        {
            "username": user.username,
            "role": user.role,
        }
        for user in users
    ]
    return {"users": result}


@app.get("/jobs")
def get_jobs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),

    load_id: Optional[List[str]] = Query(None),
    h_plate: Optional[List[str]] = Query(None),
    t_plate: Optional[List[str]] = Query(None),
    locat_recive: Optional[List[str]] = Query(None),
    date_recive: Optional[List[str]] = Query(None),  # ถ้า date จริงควรเป็น List[date]
    locat_deliver: Optional[List[str]] = Query(None),
    date_deliver: Optional[List[str]] = Query(None), # ถ้า date จริงควรเป็น List[date]
    driver_name: Optional[List[str]] = Query(None),
    status: Optional[List[str]] = Query(None),
    date_plan_start: Optional[date] = Query(None),
    date_plan_end: Optional[date] = Query(None),
):
    query = db.query(models.Job)

    # 1. Filter ตาม role
    if current_user.role != "admin":
        query = query.filter(models.Job.driver_name == current_user.username)

    # 2. Filter date_plan ทุก role
    if date_plan_start:
        query = query.filter(models.Job.date_plan >= date_plan_start)
    if date_plan_end:
        query = query.filter(models.Job.date_plan <= date_plan_end)

    # 3. User ถ้าไม่ส่ง date filter จะ default 7 วันรอบนี้
    if current_user.role != "admin" and not date_plan_start and not date_plan_end:
        today_date = date.today()
        start_date = today_date - timedelta(days=7)
        end_date = today_date + timedelta(days=7)
        query = query.filter(
            models.Job.date_recive >= start_date,
            models.Job.date_recive <= end_date
        )

    # 4. Filter field แบบหลายค่า
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

    sorted_jobs = sorted(
        jobs,
        key=lambda job: (
            # 1. Put jobs with "other statuses" first
            0 if job.status not in ["พร้อมรับงาน", "จัดส่งแล้ว (POD)"] else 1,
            
            # 2. Today’s jobs come before others
            0 if job.date_plan == date.today() else 1,
            
            # 3. Sort by date_plan (descending if exists)
            -job.date_plan.toordinal() if job.date_plan else 0
        )
    )

    return {
        "role": current_user.role,
        "jobs": [job.__dict__ for job in sorted_jobs]
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
    raw_update_fields = {k: v for k, v in data.dict(exclude_unset=True).items() if k != "load_id"}
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

            if ticket:
                for f, val in update_fields.items():
                    setattr(ticket, f, val)
            else:
                payload = {**update_fields, "load_id": lid}
                ticket = models.Ticket(**payload)
                db.add(ticket)

            db.flush()  # ให้ ticket ได้ค่าล่าสุดก่อนคำนวณสถานะ

            status = compute_status(ticket)

            job = db.query(models.Job).filter(models.Job.load_id == lid).first()
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
def update_job(
    load_id: str = Query(...),
    data: JobSchemaPut = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    now = datetime.now()
    job = db.query(models.Job).filter(models.Job.load_id == load_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(job, field, value)
    job.updated_at = now
    job.updated_by = current_user.username
    db.commit()
    db.refresh(job)
    return {"message": "✅ Job updated", "job": model_to_dict(job)}

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