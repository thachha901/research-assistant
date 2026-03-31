# backend/app/services/notifier.py
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import Subscription, Notification, Paper
from app.services.crawler import fetch_arxiv_papers
from app.services.semantic_scholar import search_semantic_scholar
from app.services.embeddings import index_paper
import asyncio


async def crawl_and_save(query: str, db: Session) -> list:
    """Crawl từ cả 2 nguồn, lưu paper mới, trả về list papers mới."""
    arxiv_task = fetch_arxiv_papers(query, max_results=10)
    ss_task = search_semantic_scholar(query, limit=10)
    arxiv_data, ss_data = await asyncio.gather(arxiv_task, ss_task)

    new_papers = []
    for p in arxiv_data + ss_data:
        existing = db.query(Paper).filter(Paper.arxiv_id == p["arxiv_id"]).first()
        if not existing:
            paper = Paper(**p)
            db.add(paper)
            db.flush()  # lấy ID ngay mà không commit
            new_papers.append(paper)

            # Index vào ChromaDB
            try:
                await index_paper(paper.arxiv_id, paper.title, paper.abstract or "")
            except Exception:
                pass  # không để lỗi embedding block flow chính

    db.commit()
    return new_papers


async def run_notifications(db: Session):
    """
    Chạy toàn bộ notification pipeline:
    1. Lấy tất cả subscriptions
    2. Crawl papers mới theo keyword/author
    3. Tạo notifications cho user
    """
    subs = db.query(Subscription).all()
    if not subs:
        return {"message": "No subscriptions found", "processed": 0}

    results = []
    notified_count = 0

    for sub in subs:
        query = sub.keyword or sub.author
        if not query:
            continue

        # Crawl papers mới
        new_papers = await crawl_and_save(query, db)

        # Tạo notification cho từng paper mới
        for paper in new_papers:
            reason = f"keyword: {sub.keyword}" if sub.keyword else f"author: {sub.author}"

            # Tránh tạo notification trùng
            exists = db.query(Notification).filter(
                Notification.user_id == sub.user_id,
                Notification.arxiv_id == paper.arxiv_id
            ).first()

            if not exists:
                notif = Notification(
                    user_id=sub.user_id,
                    arxiv_id=paper.arxiv_id,
                    title=paper.title,
                    reason=reason,
                )
                db.add(notif)
                notified_count += 1

        # Cập nhật last_run
        sub.last_run = datetime.utcnow()
        results.append({
            "query": query,
            "new_papers": len(new_papers)
        })

    db.commit()
    return {
        "processed": len(subs),
        "notifications_created": notified_count,
        "details": results
    }