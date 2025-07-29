from mangum import Mangum

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

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello from FastAPI on Vercel!"}

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
    return {"access_token": access_token, "token_type": "bearer"}



# --- Jobs Endpoint ---
@app.get("/jobs")
def get_jobs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    today_date = date.today()
    start_date = today_date - timedelta(days=7)
    end_date = today_date + timedelta(days=7)

    jobs = db.query(models.Job).filter(
        models.Job.date_plan >= start_date,
        models.Job.date_plan <= end_date,
        models.Job.driver_name == current_user.username
    ).all()

    sorted_jobs = sorted(
        jobs,
        key=lambda job: (
            0 if job.date_plan == today_date else 1,
            -job.date_plan.toordinal()
        )
    )

    return [job.__dict__ for job in sorted_jobs]

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
        return {"message": "✅ Ticket updated", "ticket": ticket.__dict__}
    else:
        new_ticket = models.Ticket(**data.dict())
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)
        return {"message": "✅ Ticket created", "ticket": new_ticket.__dict__}

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
    job_dict = job.__dict__.copy()
    job_dict["ticket"] = ticket.__dict__ if ticket else None

    return job_dict

handler = Mangum(app)

