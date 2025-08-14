# employee_crud.py
import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# The import path and class names are now correct for the dynamic table approach.
from database import get_db, CompanyMaster

app = APIRouter()

# --- Pydantic Schema ---
class EmployeeCreate(BaseModel):
    company_code: str
    employee_code: str
    first_name: str
    last_name: str
    email: EmailStr
    mobile: str
    designation: str
    role: str
    password: str

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    designation: Optional[str] = None
    active: Optional[bool] = None

class TeamCreate(BaseModel):
    company_code: str
    team_name: str
    team_description: str

# --- Hash Password ---
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# --- Add Employee ---
@app.post("/add_employee")
def add_employee(data: EmployeeCreate, db: Session = Depends(get_db)):
    # Check if the company exists first
    company = db.query(CompanyMaster).filter(CompanyMaster.company_code == data.company_code).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company does not exist.")
    
    # Hash password
    hashed_pw = hash_password(data.password)

    # Use raw SQL to insert into the dynamic table
    employee_table_name = f"{data.company_code}_Employees"
    insert_sql = text(f"""
        INSERT INTO `{employee_table_name}` (
            `Company Code`, `Employee Code`, `First Name`, `Last Name`, `Email`, `Mobile`, `Designation`, `Role`, `Password`, `Active`
        ) VALUES (
            :company_code, :employee_code, :first_name, :last_name, :email, :mobile, :designation, :role, :password, :active
        )
    """)

    params = {
        "company_code": data.company_code,
        "employee_code": data.employee_code,
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "mobile": data.mobile,
        "designation": data.designation,
        "role": data.role,
        "password": hashed_pw,
        "active": True
    }

    try:
        db.execute(insert_sql, params)
        db.commit()
    except IntegrityError as e:
        raise HTTPException(status_code=400, detail="Employee code or email already exists.")
        
    return {"message": f"Employee added successfully."}

# --- Add Team (NEW ENDPOINT) ---
@app.post("/add_team")
def add_team(data: TeamCreate, db: Session = Depends(get_db)):
    # Check if the company exists first
    company = db.query(CompanyMaster).filter(CompanyMaster.company_code == data.company_code).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company does not exist.")
    
    # Dynamically create a team table for the company if it doesn't exist
    team_table_name = f"{data.company_code}_Teams"
    create_table_sql = text(f"""
        CREATE TABLE IF NOT EXISTS `{team_table_name}` (
            `Id` INT AUTO_INCREMENT PRIMARY KEY,
            `Team Name` VARCHAR(255) UNIQUE,
            `Team Description` TEXT
        )
    """)
    db.execute(create_table_sql)
    db.commit()

    # Insert the new team into the dynamic team table
    insert_sql = text(f"""
        INSERT INTO `{team_table_name}` (
            `Team Name`, `Team Description`
        ) VALUES (
            :team_name, :team_description
        )
    """)
    params = {
        "team_name": data.team_name,
        "team_description": data.team_description
    }

    try:
        db.execute(insert_sql, params)
        db.commit()
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Team with this name already exists.")
    
    return {"message": "Team added successfully."}


# --- Get Employee by Code ---
@app.get("/get_employee/{company_code}/{employee_code}")
def get_employee(company_code: str, employee_code: str, db: Session = Depends(get_db)):
    employee_table_name = f"{company_code}_Employees"
    select_sql = text(f"SELECT * FROM `{employee_table_name}` WHERE `Employee Code` = :employee_code")
    
    result = db.execute(select_sql, {"employee_code": employee_code}).fetchone()
    
    if not result:
        raise HTTPException(status_code=404, detail="Employee not found.")
    
    return dict(result._mapping)

# --- Update Employee ---
@app.put("/update_employee/{company_code}/{employee_code}")
def update_employee(company_code: str, employee_code: str, data: EmployeeUpdate, db: Session = Depends(get_db)):
    employee_table_name = f"{company_code}_Employees"
    
    updates = []
    params = {"employee_code": employee_code}
    
    if data.first_name is not None:
        updates.append("`First Name` = :first_name")
        params["first_name"] = data.first_name
    if data.last_name is not None:
        updates.append("`Last Name` = :last_name")
        params["last_name"] = data.last_name
    if data.email is not None:
        updates.append("`Email` = :email")
        params["email"] = data.email
    if data.mobile is not None:
        updates.append("`Mobile` = :mobile")
        params["mobile"] = data.mobile
    if data.designation is not None:
        updates.append("`Designation` = :designation")
        params["designation"] = data.designation
    if data.active is not None:
        updates.append("`Active` = :active")
        params["active"] = data.active

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
        
    update_query = text(f"UPDATE `{employee_table_name}` SET {', '.join(updates)} WHERE `Employee Code` = :employee_code")

    try:
        db.execute(update_query, params)
        db.commit()
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Email already exists for another employee.")
        
    return {"message": "Employee updated successfully."}

# --- Delete Employee ---
@app.delete("/delete_employee/{company_code}/{employee_code}")
def delete_employee(company_code: str, employee_code: str, db: Session = Depends(get_db)):
    employee_table_name = f"{company_code}_Employees"
    delete_sql = text(f"DELETE FROM `{employee_table_name}` WHERE `Employee Code` = :employee_code")
    
    db.execute(delete_sql, {"employee_code": employee_code})
    db.commit()
    
    return {"message": "Employee deleted successfully."}
