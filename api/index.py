from fastapi import FastAPI, Depends, HTTPException, Body, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime
from sqlalchemy import desc
from fastapi.responses import JSONResponse
from typing import Optional
from . import models, auth, database
from .database import SessionLocal
from .schemas import TicketUpdate , PalletDataUpdate , JobSchema , JobUpdateSchema , JobSchemaPut
from fastapi import Header, HTTPException, status
from datetime import datetime
from typing import List

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

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


# --- Jobs Endpoint ---
@app.get("/jobs")
def get_jobs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    today_date = date.today()
    start_date = today_date - timedelta(days=7)
    end_date = today_date + timedelta(days=7)

    query = db.query(models.Job).filter(
        models.Job.date_plan >= start_date,
        models.Job.date_plan <= end_date,
    )
    # ถ้าไม่ใช่ admin ให้ filter ตาม driver_name
    if current_user.role != "admin":
        query = query.filter(models.Job.driver_name == current_user.username)

    jobs = query.all()

    sorted_jobs = sorted(
        jobs,
        key=lambda job: (
            0 if job.date_plan == today_date else 1,
            -job.date_plan.toordinal()
        )
    )

    return {
        "role": current_user.role,            # <<< เพิ่ม role ใน response
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

# --- Job Tickets ---
@app.post("/job-tickets")
def create_or_update_ticket(
    data: TicketUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    job = db.query(models.Job).filter(models.Job.load_id == data.load_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="load_id not found in jobdata")

    ticket = db.query(models.Ticket).filter(models.Ticket.load_id == data.load_id).first()

    if ticket:
        for field, value in data.dict(exclude_unset=True).items():
            if field != "load_id":
                setattr(ticket, field, value)
        db.commit()
        db.refresh(ticket)
        # เพิ่มตรงนี้
        status = compute_status(ticket)
    else:
        new_ticket = models.Ticket(**data.dict())
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)
        # เพิ่มตรงนี้
        status = compute_status(new_ticket)

    # อัปเดต status ใน jobdata ถ้ามี
    if status:
        job.status = status
        db.commit()
        db.refresh(job)

    return {
        "message": "✅ Ticket updated" if ticket else "✅ Ticket created",
        "ticket": (ticket or new_ticket).__dict__,
        "new_status": status  # <<-- เพิ่มตรงนี้ (หรือจะตั้งชื่อ key ว่า "status" ก็ได้)
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
 
@app.post("/jobs")
def create_job(
    data: JobUpdateSchema = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    now = datetime.now()
    # 1. Check duplicate
    job = db.query(models.Job).filter(models.Job.load_id == data.load_id).first()
    if job:
        raise HTTPException(status_code=400, detail="Job with this load_id already exists")

    # 2. Create Job
    new_job = models.Job(
        **data.dict(exclude={"created_at", "updated_at", "created_by", "updated_by"}),
        created_by=current_user.username,
        created_at=now,
        updated_by=current_user.username,
        updated_at=now,
    )
    db.add(new_job)
    
    # 3. Auto create Ticket (เฉพาะ load_id)
    new_ticket = models.Ticket(load_id=data.load_id)
    db.add(new_ticket)

    # 4. Auto create Palletdata (เฉพาะ load_id)
    new_pallet = models.Palletdata(load_id=data.load_id)
    db.add(new_pallet)
    
    # 5. Commit ทุกอย่าง
    db.commit()
    db.refresh(new_job)
    # (optionally refresh ticket, palletdata ถ้าต้องการ response กลับ)
    
    return {
        "message": "✅ Job created",
        "job": model_to_dict(new_job)

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

@app.post("/jobs/bulk")
def create_jobs_bulk(
    data: List[JobSchema] = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    now = datetime.now()
    results = []
    for job_in in data:
        job = db.query(models.Job).filter(models.Job.load_id == job_in.load_id).first()
        if job:
            results.append({
                "load_id": job_in.load_id,
                "status": "❌ already exists"
            })
            continue
        new_job = models.Job(
            **job_in.dict(exclude={"created_at", "updated_at", "created_by", "updated_by"}),
            created_by=current_user.username,
            created_at=now,
            updated_by=current_user.username,
            updated_at=now,
        )
        db.add(new_job)
        db.flush()  # ใช้ flush แทน commit เพื่อ insert ได้ไว
        results.append({
            "load_id": job_in.load_id,
            "status": "✅ created"
        })
    db.commit()  # commit ทีเดียวหลัง loop
    return {"results": results}