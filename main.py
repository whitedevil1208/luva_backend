# main.py
from fastapi import FastAPI
from login import superadmin_login
from company import company_crud
from employee import employee_crud
from teams import team
app = FastAPI()

app.include_router(superadmin_login.app, prefix="/superadmin")
app.include_router(company_crud.app, prefix="/company")
app.include_router(employee_crud.app, prefix="/employee")
app.include_router(team.router, prefix="/team")
