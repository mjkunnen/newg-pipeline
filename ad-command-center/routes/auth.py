from fastapi import APIRouter, Depends, HTTPException, Header
from config import DASHBOARD_SECRET

router = APIRouter()

async def verify_auth(authorization: str = Header(None)):
    if not authorization or authorization != f"Bearer {DASHBOARD_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

@router.post("/api/auth/login")
async def login(body: dict):
    if body.get("password") == DASHBOARD_SECRET:
        return {"token": DASHBOARD_SECRET}
    raise HTTPException(status_code=401, detail="Invalid password")
