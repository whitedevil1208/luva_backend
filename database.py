# database.py
import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, MetaData, Table, inspect
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
DATABASE_URL = os.getenv("MYSQL_URL")
if not DATABASE_URL:
    raise ValueError("MYSQL_URL environment variable not set")

# --- DB setup ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
metadata = MetaData()

# --- SQLAlchemy Models ---
class SuperAdminDevices(Base):
    __tablename__ = "SuperAdminDevices"
    id = Column(Integer, primary_key=True, index=True)
    superadmin_email = Column(String(255))
    device_id = Column(String(255))
    last_used = Column(DateTime)

class SuperAdminVerificationCodes(Base):
    __tablename__ = "SuperAdminVerificationCodes"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255))
    code = Column(String(6))
    expires_at = Column(DateTime)

class CompanyMaster(Base):
    __tablename__ = "Company Master"
    id = Column(Integer, primary_key=True, index=True)
    company_code = Column("Company Code", String(100), unique=True, index=True)
    company_name = Column("Company Name", String(256))
    company_address = Column("Company Address", String(256))
    company_city = Column("Company City", String(100))
    company_state = Column("Company State", String(100))
    company_country = Column("Company Country", String(100))
    active = Column("Active", Boolean, default=True)
    
class CompanyEmployeeMaster(Base):
    __tablename__ = "Company Employee Master"
    id = Column(Integer, primary_key=True, index=True)
    company_code = Column("Company Code", String(100))
    employee_code = Column("Employee Code", String(100), unique=True, index=True)
    first_name = Column("First Name", String(156))
    last_name = Column("Last Name", String(156))
    email = Column("Email", String(100))
    mobile = Column("Mobile", String(56))
    designation = Column("Designation", String(156))
    role = Column("Role", String(50))
    password = Column("Password", String(256))
    active = Column("Active", Boolean)

# Dependency to get a DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dynamic function to get or create a table model for a company
def get_employee_model_for_company(company_code: str):
    table_name = f"{company_code}_Employees"
    insp = inspect(engine)
    if not insp.has_table(table_name):
        return None
    
    # Create a dynamic model for the company's employee table
    class DynamicEmployee(Base):
        __tablename__ = table_name
        __table_args__ = {'extend_existing': True}
        id = Column(Integer, primary_key=True, index=True)
        company_code = Column("Company Code", String(100))
        employee_code = Column("Employee Code", String(100), unique=True, index=True)
        first_name = Column("First Name", String(156))
        last_name = Column("Last Name", String(156))
        email = Column("Email", String(100))
        mobile = Column("Mobile", String(56))
        designation = Column("Designation", String(156))
        role = Column("Role", String(50))
        password = Column("Password", String(256))
        active = Column("Active", Boolean)
    
    return DynamicEmployee