# backend/app/routers/search.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Paper
from app.services.embeddings import semantic_search, get_indexed_count

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/")
async def search_papers(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Hybrid search: semantic search trước, sau đó lấy full data từ PostgreSQL.
    """
    if not q.strip():
        return {"results": [], "total": 0}

    # 1. Semantic search → lấy danh sách arxiv_id + score
    semantic_results = await semantic_search(q, n_results=limit)

    if not semantic_results:
        # Fallback: keyword search trong PostgreSQL nếu chưa có embedding
        papers = db.query(Paper).filter(
            Paper.title.ilike(f"%{q}%") |
            Paper.abstract.ilike(f"%{q}%")
        ).limit(limit).all()

        return {
            "results": papers,
            "total": len(papers),
            "mode": "keyword_fallback"
        }

    # 2. Lấy full paper data từ PostgreSQL theo thứ tự score
    arxiv_ids = [r["arxiv_id"] for r in semantic_results]
    scores = {r["arxiv_id"]: r["score"] for r in semantic_results}

    papers = db.query(Paper).filter(Paper.arxiv_id.in_(arxiv_ids)).all()

    # Sắp xếp theo score giảm dần
    papers_sorted = sorted(papers, key=lambda p: scores.get(p.arxiv_id, 0), reverse=True)

    # Gắn score vào kết quả
    results = []
    for paper in papers_sorted:
        paper_dict = {
            "id": str(paper.id),
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "abstract": paper.abstract,
            "authors": paper.authors,
            "categories": paper.categories,
            "published": paper.published,
            "pdf_url": paper.pdf_url,
            "similarity_score": scores.get(paper.arxiv_id, 0)
        }
        results.append(paper_dict)

    return {
        "results": results,
        "total": len(results),
        "mode": "semantic",
        "query": q
    }


@router.get("/stats")
def search_stats(db: Session = Depends(get_db)):
    """Thống kê index hiện tại."""
    total_papers = db.query(Paper).count()
    indexed = get_indexed_count()
    return {
        "total_papers_in_db": total_papers,
        "total_indexed_for_search": indexed,
        "not_indexed_yet": total_papers - indexed
    }