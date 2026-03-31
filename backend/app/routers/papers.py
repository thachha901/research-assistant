# backend/app/routers/papers.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import Paper, SavedPaper
from app.services.crawler import fetch_arxiv_papers
from app.services.embeddings import index_paper  # Đã di chuyển lên đầu file
from app.services.semantic_scholar import search_semantic_scholar, get_recommendations  # Đã di chuyển lên đầu file
class SavePaperRequest(BaseModel):
    arxiv_id: str
    user_id: str = "local_user"
    
router = APIRouter(prefix="/papers", tags=["papers"])

# ==========================================
# 1. CÁC ĐƯỜNG DẪN CỐ ĐỊNH (Phải đặt lên trước)
# ==========================================

@router.get("/crawl")
async def crawl_papers(query: str = "machine learning", max_results: int = 20, db: Session = Depends(get_db)):
    papers_data = await fetch_arxiv_papers(query, max_results)
    saved = 0

    for p in papers_data:
        existing = db.query(Paper).filter(Paper.arxiv_id == p["arxiv_id"]).first()
        if not existing:
            paper = Paper(**p)
            db.add(paper)
            saved += 1

    db.commit()
    return {"fetched": len(papers_data), "saved_new": saved, "query": query}

@router.post("/index-all")
async def index_all_papers(db: Session = Depends(get_db)):
    """Index toàn bộ papers trong DB vào ChromaDB để semantic search."""
    papers = db.query(Paper).all()
    indexed = 0
    failed = 0

    for paper in papers:
        try:
            await index_paper(paper.arxiv_id, paper.title, paper.abstract or "")
            indexed += 1
        except Exception as e:
            failed += 1
            print(f"Failed to index {paper.arxiv_id}: {e}")

    return {
        "total": len(papers),
        "indexed": indexed,
        "failed": failed
    }

@router.post("/save")
def save_paper(request: SavePaperRequest, db: Session = Depends(get_db)):
    # Kiểm tra đã lưu chưa
    existing = db.query(SavedPaper).filter(
        SavedPaper.arxiv_id == request.arxiv_id,
        SavedPaper.user_id == request.user_id
    ).first()

    if existing:
        return {"status": "already_saved", "arxiv_id": request.arxiv_id}

    saved = SavedPaper(arxiv_id=request.arxiv_id, user_id=request.user_id)
    db.add(saved)
    db.commit()
    return {"status": "saved", "arxiv_id": request.arxiv_id}

@router.delete("/save/{arxiv_id}")
def unsave_paper(arxiv_id: str, user_id: str = "local_user", db: Session = Depends(get_db)):
    saved = db.query(SavedPaper).filter(
        SavedPaper.arxiv_id == arxiv_id,
        SavedPaper.user_id == user_id
    ).first()

    if not saved:
        return {"status": "not_found"}

    db.delete(saved)
    db.commit()
    return {"status": "removed", "arxiv_id": arxiv_id}

# Đã xóa cái hàm list_saved_papers() thứ 2 bị trùng lặp
@router.get("/saved")
def list_saved_papers(user_id: str = "local_user", db: Session = Depends(get_db)):
    saved_records = db.query(SavedPaper).filter(
        SavedPaper.user_id == user_id
    ).order_by(SavedPaper.created_at.desc()).all()

    if not saved_records:
        return []

    arxiv_ids = [s.arxiv_id for s in saved_records]
    papers = db.query(Paper).filter(Paper.arxiv_id.in_(arxiv_ids)).all()

    # Giữ đúng thứ tự saved (mới nhất trước)
    paper_map = {p.arxiv_id: p for p in papers}
    return [paper_map[s.arxiv_id] for s in saved_records if s.arxiv_id in paper_map]

@router.get("/")
def list_papers(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    papers = db.query(Paper).order_by(Paper.published.desc()).offset(skip).limit(limit).all()
    return papers


# ==========================================
# 2. CÁC ĐƯỜNG DẪN ĐỘNG (Bắt buộc đặt cuối cùng)
# ==========================================

@router.get("/{arxiv_id}")
def get_paper(arxiv_id: str, db: Session = Depends(get_db)):
    paper = db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper

@router.get("/crawl/semantic-scholar")
async def crawl_semantic_scholar(
    query: str = "machine learning",
    max_results: int = 20,
    db: Session = Depends(get_db)
):
    """Crawl papers từ Semantic Scholar."""
    papers_data = await search_semantic_scholar(query, max_results)
    saved = 0
    skipped = 0

    for p in papers_data:
        existing = db.query(Paper).filter(Paper.arxiv_id == p["arxiv_id"]).first()
        if existing:
            skipped += 1
            continue

        paper = Paper(**p)
        db.add(paper)
        saved += 1

    db.commit()
    return {
        "fetched": len(papers_data),
        "saved_new": saved,
        "skipped_duplicate": skipped,
        "query": query,
        "source": "semantic_scholar"
    }


@router.get("/crawl/all")
async def crawl_all_sources(
    query: str = "machine learning",
    max_results: int = 20,
    db: Session = Depends(get_db)
):
    """Crawl từ cả arXiv lẫn Semantic Scholar cùng lúc."""
    import asyncio
    arxiv_task = fetch_arxiv_papers(query, max_results)
    ss_task = search_semantic_scholar(query, max_results)

    arxiv_data, ss_data = await asyncio.gather(arxiv_task, ss_task)
    all_papers = arxiv_data + ss_data

    saved = 0
    skipped = 0
    for p in all_papers:
        existing = db.query(Paper).filter(Paper.arxiv_id == p["arxiv_id"]).first()
        if existing:
            skipped += 1
            continue
        paper = Paper(**p)
        db.add(paper)
        saved += 1

    db.commit()
    return {
        "arxiv_fetched": len(arxiv_data),
        "ss_fetched": len(ss_data),
        "saved_new": saved,
        "skipped_duplicate": skipped,
        "query": query,
    }


@router.get("/{arxiv_id}/recommendations")
async def get_paper_recommendations(arxiv_id: str, db: Session = Depends(get_db)):
    """Gợi ý papers liên quan (chỉ hoạt động với papers từ Semantic Scholar)."""
    paper = db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()
    if not paper or not paper.external_id:
        return {"recommendations": [], "message": "No Semantic Scholar ID available"}

    recs = await get_recommendations(paper.external_id, limit=5)
    return {"recommendations": recs}