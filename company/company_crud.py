# company/company_crud.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

# The import path and class names are now correct for the dynamic table approach.
from database import get_db, CompanyMaster

app = APIRouter()

# --- Pydantic Models (using consistent naming) ---
class CompanyCreate(BaseModel):
    company_code: str
    company_name: str
    company_address: str
    company_city: str
    company_state: str
    company_country: str
    # New fields added here
    company_email: Optional[str] = None
    company_phone_number: Optional[str] = None

class CompanyUpdate(BaseModel):
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    company_city: Optional[str] = None
    company_state: Optional[str] = None
    company_country: Optional[str] = None
    company_email: Optional[str] = None
    company_phone_number: Optional[str] = None
    active: Optional[bool] = None

# --- CREATE Company ---
@app.post("/create_company")
def create_company(data: CompanyCreate, db: Session = Depends(get_db)):
    # Check if company code already exists using the ORM
    db_company = db.query(CompanyMaster).filter(CompanyMaster.company_code == data.company_code).first()
    if db_company:
        raise HTTPException(status_code=400, detail="Company code already exists.")

    new_company = CompanyMaster(
        company_code=data.company_code,
        company_name=data.company_name,
        company_address=data.company_address,
        company_city=data.company_city,
        company_state=data.company_state,
        company_country=data.company_country,
        # New fields assigned here
        company_email=data.company_email,
        company_phone_number=data.company_phone_number,
        active=True
    )
    
    try:
        db.add(new_company)
        db.commit()
        # Refresh the instance to ensure it's re-bound to the session and has its attributes loaded
        db.refresh(new_company)

        # --- Create the dynamic employee table with a raw SQL query ---
        employee_table_name = f"{data.company_code}_Employees"
        create_table_sql = text(f"""
            CREATE TABLE IF NOT EXISTS `{employee_table_name}` (
                `Id` INT AUTO_INCREMENT PRIMARY KEY,
                `Company Code` VARCHAR(100),
                `Employee Code` VARCHAR(100) UNIQUE,
                `First Name` VARCHAR(156),
                `Last Name` VARCHAR(156),
                `Email` VARCHAR(100),
                `Mobile` VARCHAR(56),
                `Designation` VARCHAR(156),
                `Role` VARCHAR(50),
                `Password` VARCHAR(256),
                `Picture` VARCHAR(255),
                `Active` BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (`Company Code`) REFERENCES `Company Master` (`Company Code`) ON DELETE CASCADE
            )
        """)
        db.execute(create_table_sql)
        db.commit()

        return {
            "message": "Company created and employee table initialized.",
            "company_code": new_company.company_code,
            "employee_table": employee_table_name
        }

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Company code already exists.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred during table creation: {e}")
    finally:
        db.close()

# --- GET ALL Companies ---
@app.get("/companies")
def get_all_companies(db: Session = Depends(get_db)):
    companies = db.query(CompanyMaster).all()
    # Serialize the SQLAlchemy objects to a list of dictionaries
    return {"companies": [
        {
            "id": company.id,
            "company_code": company.company_code,
            "company_name": company.company_name,
            "company_address": company.company_address,
            "company_city": company.company_city,
            "company_state": company.company_state,
            "company_country": company.company_country,
            "company_email": company.company_email,
            "company_phone_number": company.company_phone_number,
            "active": company.active
        }
        for company in companies
    ]}

# --- GET Specific Company by Code ---
@app.get("/company/{company_code}")
def get_company(company_code: str, db: Session = Depends(get_db)):
    company = db.query(CompanyMaster).filter(CompanyMaster.company_code == company_code).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    return {
        "id": company.id,
        "company_code": company.company_code,
        "company_name": company.company_name,
        "company_address": company.company_address,
        "company_city": company.company_city,
        "company_state": company.company_state,
        "company_country": company.company_country,
        "company_email": company.company_email,
        "company_phone_number": company.company_phone_number,
        "active": company.active
    }

# --- UPDATE Company ---
@app.put("/update_company/{company_code}")
def update_company(company_code: str, data: CompanyUpdate, db: Session = Depends(get_db)):
    company = db.query(CompanyMaster).filter(CompanyMaster.company_code == company_code).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(company, key, value)
    
    db.commit()
    return {"message": "Company updated successfully."}

# --- DELETE Company ---
@app.delete("/delete_company/{company_code}")
def delete_company(company_code: str, db: Session = Depends(get_db)):
    company = db.query(CompanyMaster).filter(CompanyMaster.company_code == company_code).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    # --- Drop the dynamic employee table with a raw SQL query ---
    employee_table_name = f"{company_code}_Employees"
    db.execute(text(f"DROP TABLE IF EXISTS `{employee_table_name}`"))
    
    db.delete(company)
    db.commit()

    return {"message": "Company and its employee table deleted successfully."}