# backend/app/routers/ai.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Paper
from app.services.llm import summarize_paper, compare_papers

router = APIRouter(prefix="/ai", tags=["ai"])


class CompareRequest(BaseModel):
    arxiv_ids: list[str]


@router.get("/summarize/{arxiv_id}")
async def get_summary(arxiv_id: str, db: Session = Depends(get_db)):
    """
    Tóm tắt 1 paper bằng AI.
    Cache kết quả vào DB để không gọi lại OpenAI lần sau.
    """
    paper = db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Trả cache nếu đã có
    if paper.summary_ai:
        import json
        try:
            return {"arxiv_id": arxiv_id, "summary": json.loads(paper.summary_ai), "cached": True}
        except Exception:
            pass  # nếu cache lỗi thì generate lại

    # Gọi OpenAI
    summary = await summarize_paper(paper.title, paper.abstract or "")

    # Lưu cache vào DB
    import json
    paper.summary_ai = json.dumps(summary)
    db.commit()

    return {"arxiv_id": arxiv_id, "summary": summary, "cached": False}


@router.post("/compare")
async def compare(request: CompareRequest, db: Session = Depends(get_db)):
    """So sánh 2-5 papers với nhau."""
    if len(request.arxiv_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 papers to compare")
    if len(request.arxiv_ids) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 papers at once")

    papers = db.query(Paper).filter(Paper.arxiv_id.in_(request.arxiv_ids)).all()
    if len(papers) < 2:
        raise HTTPException(status_code=404, detail="Papers not found in database")

    papers_data = [
        {"title": p.title, "abstract": p.abstract or ""}
        for p in papers
    ]

    comparison = await compare_papers(papers_data)
    return {
        "papers": [{"arxiv_id": p.arxiv_id, "title": p.title} for p in papers],
        "comparison": comparison
    }