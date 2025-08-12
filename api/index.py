from fastapi import FastAPI, Depends, HTTPException, Body, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime
from sqlalchemy import desc
from fastapi.responses import JSONResponse
from typing import Optional
from . import models, auth, database
from .database import SessionLocal
from .schemas import TicketUpdate , PalletDataUpdate , JobSchema , JobUpdateSchema , JobSchemaPut , JobUpdateSchemaCreate , RegisterRequest
from fastapi import Header, HTTPException, status
from datetime import datetime
from typing import List
from .auth import hash_password

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="TDM Backend API",
    description="API สำหรับ TDM Fleet Management",
    version="1.2.1",    # << ใส่ version ที่ต้องการ
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
            models.Job.date_plan >= start_date,
            models.Job.date_plan <= end_date
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
            0 if job.date_plan == date.today() else 1,
            -job.date_plan.toordinal() if job.date_plan else 0
        )
    )

    return {
        "role": current_user.role,
        "jobs": [job.__dict__ for job in sorted_jobs]
    }
def compute_status(ticket):
    # ให้เช็คตามลำดับล่าสุด -> earliest
    if ticket.complete_datetime:        return "จัดส่งแล้ว (POD)"
    if ticket.end_unload_datetime:      return "ลงสินค้าเสร็จ"
    if ticket.start_unload_datetime:    return "เริ่มลงสินค้า"
    if ticket.desination_datetime:      return "ถึงปลายทาง"
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

    if apply_to_group and getattr(anchor, "group_key", None):
        group_load_ids = [
            r[0]
            for r in db.query(models.Job.load_id)
                      .filter(models.Job.group_key == anchor.group_key)
                      .all()
        ]
    else:
        group_load_ids = [data.load_id]

    update_fields = {k: v for k, v in data.dict(exclude_unset=True).items() if k != "load_id"}

    affected = []
    try:
        for lid in group_load_ids:
            ticket = db.query(models.Ticket).filter(models.Ticket.load_id == lid).first()
            if ticket:
                for f, val in update_fields.items():
                    setattr(ticket, f, val)
            else:
                payload = data.dict(exclude_unset=True).copy()
                payload["load_id"] = lid
                ticket = models.Ticket(**payload)
                db.add(ticket)

            db.flush()

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
        "apply_to_group": apply_to_group,
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