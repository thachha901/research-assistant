# backend/app/routers/notifications.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Subscription, Notification
from app.services.notifier import run_notifications
from typing import Union

router = APIRouter(prefix="/notifications", tags=["notifications"])


class SubscribeRequest(BaseModel):
    keyword: Union[str, None] = None
    author: Union[str, None] = None
    user_id: str = "local_user"


# --- Subscriptions ---

@router.post("/subscribe")
def subscribe(req: SubscribeRequest, db: Session = Depends(get_db)):
    if not req.keyword and not req.author:
        raise HTTPException(status_code=400, detail="Provide keyword or author")

    # Tránh duplicate subscription
    existing = db.query(Subscription).filter(
        Subscription.user_id == req.user_id,
        Subscription.keyword == req.keyword,
        Subscription.author == req.author,
    ).first()

    if existing:
        return {"status": "already_subscribed"}

    sub = Subscription(
        user_id=req.user_id,
        keyword=req.keyword,
        author=req.author,
    )
    db.add(sub)
    db.commit()
    return {"status": "subscribed", "keyword": req.keyword, "author": req.author}


@router.get("/subscriptions")
def list_subscriptions(user_id: str = "local_user", db: Session = Depends(get_db)):
    subs = db.query(Subscription).filter(Subscription.user_id == user_id).all()
    return subs


@router.delete("/subscriptions/{sub_id}")
def delete_subscription(sub_id: str, db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    db.delete(sub)
    db.commit()
    return {"status": "deleted"}


# --- Notifications ---

@router.get("/")
def list_notifications(user_id: str = "local_user", db: Session = Depends(get_db)):
    notifs = db.query(Notification).filter(
        Notification.user_id == user_id
    ).order_by(Notification.created_at.desc()).limit(50).all()
    return notifs


@router.patch("/{notif_id}/read")
def mark_read(notif_id: str, db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.id == notif_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Not found")
    notif.is_read = 1
    db.commit()
    return {"status": "ok"}


@router.patch("/read-all")
def mark_all_read(user_id: str = "local_user", db: Session = Depends(get_db)):
    db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == 0
    ).update({"is_read": 1})
    db.commit()
    return {"status": "ok"}


# --- Trigger pipeline ---

@router.post("/run")
async def trigger_notifications(db: Session = Depends(get_db)):
    """Chạy thủ công — sau này sẽ được gọi bởi cron job."""
    result = await run_notifications(db)
    return result