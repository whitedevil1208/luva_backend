# super_admin.py
import os
import uuid
import smtplib
import bcrypt
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# The import path and class names have been corrected.
# CompanyEmployeeMaster has been removed from the import statement.
from database import get_db, CompanyMaster, SuperAdminDevices, SuperAdminVerificationCodes

# Load environment variables
load_dotenv()

# --- Configuration ---
SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL")
SUPERADMIN_HASHED_PASSWORD = os.getenv("SUPERADMIN_PASSWORD")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = 60

# --- Pydantic Schemas ---
class SuperAdminLogin(BaseModel):
    email: EmailStr
    password: str
    device_id: str

class CodeVerification(BaseModel):
    email: EmailStr
    code: str
    device_id: str

# --- Router ---
app = APIRouter()

# --- Utilities ---
def verify_password(plain_password: str, hashed_password: str):
    return bcrypt.checkpw(plain_password.encode(), SUPERADMIN_HASHED_PASSWORD.encode())

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRY_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def send_verification_email(to_email: str, code: str):
    msg = MIMEText(f"Your SuperAdmin verification code is: {code}")
    msg["Subject"] = "SuperAdmin Login Verification"
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_APP_PASSWORD)
        server.send_message(msg)

def get_dashboard_data(db: Session) -> Dict[str, Any]:
    """
    Fetches comprehensive dashboard data including total counts and a list of companies
    with their individual employee counts from dynamic tables.
    """
    companies = db.query(CompanyMaster).all()
    companies_count = len(companies)
    total_employees_count = 0
    companies_list = []

    for company in companies:
        employee_table_name = f"{company.company_code}_Employees"
        try:
            # Query the dynamic table for the employee count
            count_sql = text(f"SELECT COUNT(*) FROM `{employee_table_name}`")
            employee_count = db.execute(count_sql).scalar()
            total_employees_count += employee_count
            companies_list.append({
                "company_id": company.id,
                "company_name": company.company_name,
                "company_code": company.company_code,
                "employees_count": employee_count
            })
        except Exception:
            # Handle case where the table might not exist
            companies_list.append({
                "company_id": company.id,
                "company_name": company.company_name,
                "company_code": company.company_code,
                "employees_count": 0
            })
    
    return {
        "companies_count": companies_count,
        "employees_count": total_employees_count,
        "companies_list": companies_list
    }

# --- Routes ---
@app.post("/login")
def login(payload: SuperAdminLogin, db: Session = Depends(get_db)):
    if payload.email != SUPERADMIN_EMAIL or not verify_password(payload.password, SUPERADMIN_HASHED_PASSWORD):
        raise HTTPException(status_code=403, detail="Invalid email or password")

    device = db.query(SuperAdminDevices).filter_by(superadmin_email=payload.email, device_id=payload.device_id).first()
    if device:
        dashboard_data = get_dashboard_data(db)
        token = create_access_token({"sub": payload.email})
        
        # Return the exact JSON format requested by the user, with the new data
        return {
            "access_token": token,
            "token_type": "bearer",
            "email": payload.email,
            "name": "Super Admin",
            "phone": "0000000000",
            "role": "SuperAdmin",
            **dashboard_data,
            "modules": [
                {"name": "Company", "access": "write"},
                {"name": "Employee", "access": "write"}
            ],
            "menus": [
                {"name": "Dashboard"},
                {"name": "Companies"},
                {"name": "Employees"}
            ]
        }

    # New device - send code
    code = str(uuid.uuid4().int)[:6]
    expiry = datetime.utcnow() + timedelta(minutes=10)
    db.query(SuperAdminVerificationCodes).filter_by(email=payload.email).delete()
    db.add(SuperAdminVerificationCodes(email=payload.email, code=code, expires_at=expiry))
    db.commit()
    send_verification_email(payload.email, code)
    return {"message": "Verification code sent to your email."}

@app.post("/verify")
def verify(payload: CodeVerification, db: Session = Depends(get_db)):
    record = db.query(SuperAdminVerificationCodes).filter_by(email=payload.email, code=payload.code).first()
    if not record or record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    # Trust the device
    db.add(SuperAdminDevices(
        superadmin_email=payload.email,
        device_id=payload.device_id,
        last_used=datetime.utcnow()
    ))
    db.commit()

    dashboard_data = get_dashboard_data(db)
    token = create_access_token({"sub": payload.email})

    # Return the exact JSON format requested by the user, with the new data
    return {
        "access_token": token,
        "token_type": "bearer",
        "email": payload.email,
        "name": "Super Admin",
        "phone": "0000000000",
        "role": "SuperAdmin",
        **dashboard_data,
        "modules": [
            {"name": "Company", "access": "write"},
            {"name": "Employee", "access": "write"}
            ],
        "menus": [
            {"name": "Dashboard"},
            {"name": "Companies"},
            {"name": "Employees"}
        ]
    }
