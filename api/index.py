from fastapi import FastAPI, Depends, HTTPException, Body, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime
from sqlalchemy import desc
from fastapi.responses import JSONResponse
from typing import Optional
from . import models, auth, database
from .database import SessionLocal
from .schemas import TicketUpdate
from fastapi import Header, HTTPException, status

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
    if ticket.complete_datetime:        return "เสร็จงาน"
    if ticket.end_unload_datetime:      return "ลงสินค้าเสร็จ"
    if ticket.start_unload_datetime:    return "เริ่มลงสินค้า"
    if ticket.desination_datetime:      return "ถึงปลายทาง"
    if ticket.intransit_datetime:       return "เริ่มขนส่ง"
    if ticket.end_recive_datetime:      return "ขึ้นสินค้าเสร็จ"
    if ticket.start_recive_datetime:    return "เริ่มขึ้นสินค้า"
    if ticket.origin_datetime:          return "ถึงต้นทาง"
    if ticket.start_datetime:           return "เริ่มงาน"
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



