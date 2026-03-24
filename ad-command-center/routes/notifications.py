from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db import get_db
from models import Notification
from routes.auth import verify_auth

router = APIRouter(dependencies=[Depends(verify_auth)])

@router.get("/api/notifications")
def get_notifications(db: Session = Depends(get_db)):
    notifs = db.query(Notification).filter_by(read=False).order_by(Notification.created_at.desc()).limit(50).all()
    return [
        {"id": n.id, "type": n.type, "message": n.message, "created_at": str(n.created_at)}
        for n in notifs
    ]

@router.post("/api/notifications/{notif_id}/read")
def mark_read(notif_id: int, db: Session = Depends(get_db)):
    n = db.query(Notification).filter_by(id=notif_id).first()
    if n:
        n.read = True
        db.commit()
    return {"success": True}
