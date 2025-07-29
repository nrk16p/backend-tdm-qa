from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()  # โหลด .env

# ✅ ดึงค่าจาก .env
DATABASE_URL = os.getenv("DATABASE_URL")

# ✅ สร้าง engine ด้วย DATABASE_URL จาก .env
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
