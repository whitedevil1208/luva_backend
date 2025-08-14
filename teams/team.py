from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, Field
from typing import List, Optional

from database import get_db, CompanyMaster, get_employee_model_for_company

router = APIRouter()

# New Pydantic model for a team update
class TeamUpdate(BaseModel):
    team_name: Optional[str] = None
    team_description: Optional[str] = None

class TeamCreate(BaseModel):
    company_code: str
    team_name: str
    team_description: Optional[str] = None

class TeamMemberAdd(BaseModel):
    team_id: int
    company_code: str
    employee_codes: List[str] = Field(..., min_length=1)

class EmployeeInfo(BaseModel):
    employee_code: str
    first_name: str
    last_name: str

# Updated TeamInfo model to include member count
class TeamInfo(BaseModel):
    team_id: int
    team_name: str
    team_description: Optional[str] = None
    team_member_count: int
    team_members: List[EmployeeInfo]

class CompanyTeamsResponse(BaseModel):
    company_code: str
    teams: List[TeamInfo]

class TeamCountResponse(BaseModel):
    company_code: str
    team_count: int


@router.post("/teams", status_code=status.HTTP_201_CREATED)
def create_team(team_data: TeamCreate, db: Session = Depends(get_db)):
    company = db.query(CompanyMaster).filter(CompanyMaster.company_code == team_data.company_code).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    try:
        check_query = text("SELECT Id FROM `Employee Teams` WHERE `Company Code` = :company_code AND `Team Name` = :team_name")
        result = db.execute(check_query, {'company_code': team_data.company_code, 'team_name': team_data.team_name}).fetchone()
        if result:
            raise HTTPException(status_code=409, detail="Team name already exists for this company")
            
        insert_query = text("INSERT INTO `Employee Teams` (`Company Code`, `Team Name`, `Team Description`) VALUES (:company_code, :team_name, :team_description)")
        db.execute(insert_query, team_data.dict())
        db.commit()
        return {"message": "Team created successfully", "team_id": db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.patch("/teams/{team_id}", status_code=status.HTTP_200_OK)
def update_team(team_id: int, team_update_data: TeamUpdate, db: Session = Depends(get_db)):
    try:
        check_team_query = text("SELECT `Id` FROM `Employee Teams` WHERE `Id` = :team_id")
        team = db.execute(check_team_query, {'team_id': team_id}).fetchone()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found.")

        update_fields = {k: v for k, v in team_update_data.dict(exclude_unset=True).items() if v is not None}
        if not update_fields:
            return {"message": "No fields to update."}
            
        set_clause = ", ".join([f"`{key}` = :{key}" for key in update_fields.keys()])
        update_query = text(f"UPDATE `Employee Teams` SET {set_clause} WHERE `Id` = :team_id")
        
        update_fields['team_id'] = team_id
        
        db.execute(update_query, update_fields)
        db.commit()
        
        return {"message": "Team updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/teams/{team_id}", status_code=status.HTTP_200_OK)
def delete_team(team_id: int, db: Session = Depends(get_db)):
    try:
        delete_query = text("DELETE FROM `Employee Teams` WHERE `Id` = :team_id")
        result = db.execute(delete_query, {'team_id': team_id})
        db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Team not found.")
            
        return {"message": "Team deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/teams/members", status_code=status.HTTP_201_CREATED)
def add_team_members(member_data: TeamMemberAdd, db: Session = Depends(get_db)):
    try:
        check_team_query = text("SELECT Id FROM `Employee Teams` WHERE `Id` = :team_id AND `Company Code` = :company_code")
        team = db.execute(check_team_query, {'team_id': member_data.team_id, 'company_code': member_data.company_code}).fetchone()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found for the given company.")
        
        EmployeeModel = get_employee_model_for_company(member_data.company_code)
        if not EmployeeModel:
            raise HTTPException(status_code=404, detail=f"Employee table for company '{member_data.company_code}' not found.")
        
        values_to_insert = []
        for employee_code in member_data.employee_codes:
            employee_exists = db.query(EmployeeModel).filter(EmployeeModel.employee_code == employee_code).first()
            if not employee_exists:
                 raise HTTPException(status_code=404, detail=f"Employee with code '{employee_code}' not found in the company '{member_data.company_code}'.")
            
            values_to_insert.append({'team_id': member_data.team_id, 'employee_code': employee_code, 'company_code': member_data.company_code})
            
        insert_query = text("INSERT INTO `Employee Team Mapping` (`Team Id`, `Employee Code`, `Company Code`) VALUES (:team_id, :employee_code, :company_code)")
        
        db.execute(insert_query, values_to_insert)
        db.commit()
        
        return {"message": "Team members added successfully"}
    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/teams/{team_id}/members/{employee_code}", status_code=status.HTTP_200_OK)
def remove_team_member(team_id: int, employee_code: str, db: Session = Depends(get_db)):
    try:
        delete_query = text("DELETE FROM `Employee Team Mapping` WHERE `Team Id` = :team_id AND `Employee Code` = :employee_code")
        result = db.execute(delete_query, {'team_id': team_id, 'employee_code': employee_code})
        db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Member not found in the specified team.")
            
        return {"message": f"Employee {employee_code} removed from team {team_id} successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/teams/count/{company_code}", response_model=TeamCountResponse)
def get_team_count(company_code: str, db: Session = Depends(get_db)):
    try:
        query = text("SELECT COUNT(*) as team_count FROM `Employee Teams` WHERE `Company Code` = :company_code")
        result = db.execute(query, {'company_code': company_code}).fetchone()
        
        return TeamCountResponse(company_code=company_code, team_count=result.team_count if result else 0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# This endpoint is modified to include the team member count
@router.get("/teams/{company_code}", response_model=CompanyTeamsResponse)
def get_company_teams(company_code: str, db: Session = Depends(get_db)):
    try:
        EmployeeModel = get_employee_model_for_company(company_code)
        if not EmployeeModel:
            raise HTTPException(status_code=404, detail=f"Employee table for company '{company_code}' not found.")

        teams_query = text("SELECT Id, `Team Name`, `Team Description` FROM `Employee Teams` WHERE `Company Code` = :company_code")
        teams_data = db.execute(teams_query, {'company_code': company_code}).mappings().fetchall()
        
        teams_list = []
        for team in teams_data:
            members_query = text(f"""
                SELECT
                    t1.`Employee Code` as employee_code,
                    t1.`First Name` as first_name,
                    t1.`Last Name` as last_name
                FROM
                    `{EmployeeModel.__tablename__}` AS t1
                JOIN
                    `Employee Team Mapping` AS t2 ON t1.`Employee Code` = t2.`Employee Code`
                WHERE
                    t2.`Team Id` = :team_id AND t2.`Company Code` = :company_code;
            """)
            members_data = db.execute(members_query, {'team_id': team['Id'], 'company_code': company_code}).mappings().fetchall()
            
            teams_list.append(
                TeamInfo(
                    team_id=team['Id'],
                    team_name=team['Team Name'],
                    team_description=team['Team Description'],
                    team_member_count=len(members_data),  # Count of team members
                    team_members=[EmployeeInfo(**member) for member in members_data]
                )
            )
            
        return CompanyTeamsResponse(company_code=company_code, teams=teams_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")