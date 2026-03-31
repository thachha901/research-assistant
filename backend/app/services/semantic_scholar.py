# backend/app/services/semantic_scholar.py
import os
import asyncio
import httpx
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

# Load các biến môi trường từ file .env
load_dotenv()

BASE_URL = "https://api.semanticscholar.org/graph/v1"

FIELDS = ",".join([
    "paperId", "externalIds", "title", "abstract",
    "authors", "year", "publicationDate", "fieldsOfStudy",
    "citationCount", "openAccessPdf", "publicationTypes"
])

def get_ss_headers() -> Dict[str, str]:
    """Hàm hỗ trợ tạo headers chứa API Key nếu có."""
    headers = {"User-Agent": "ResearchAssistant/1.0"}
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers


async def search_semantic_scholar(query: str, limit: int = 20) -> List[Dict]:
    """Tìm kiếm papers từ Semantic Scholar API có kèm API Key và Retry."""
    data = {}
    
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(3): # Thử tối đa 3 lần
            response = await client.get(
                f"{BASE_URL}/paper/search",
                params={
                    "query": query,
                    "limit": limit,
                    "fields": FIELDS,
                },
                headers=get_ss_headers() # Dùng header chứa API Key
            )
            
            if response.status_code == 200:
                data = response.json()
                break # Thành công thì thoát vòng lặp
            elif response.status_code == 429:
                wait_time = 2 ** attempt
                print(f"⚠️ Semantic Scholar Rate limit hit. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                response.raise_for_status()

    papers = []
    
    # Nếu data rỗng (do lỗi cả 3 lần) thì trả về list rỗng
    if not data or "data" not in data:
        return papers

    for item in data.get("data", []):
        # Bỏ qua paper không có abstract
        if not item.get("abstract"):
            continue

        # Lấy arxiv_id nếu có (để tránh duplicate với arXiv source)
        external_ids = item.get("externalIds") or {}
        arxiv_id = external_ids.get("ArXiv")
        ss_id = item.get("paperId", "")

        # Dùng arxiv_id nếu có, không thì dùng ss: prefix
        paper_id = arxiv_id if arxiv_id else f"ss:{ss_id}"

        # Parse ngày
        pub_date = item.get("publicationDate")
        published = None
        if pub_date:
            try:
                published = datetime.strptime(pub_date, "%Y-%m-%d")
            except ValueError:
                year = item.get("year")
                if year:
                    published = datetime(year, 1, 1)

        # PDF url
        pdf_info = item.get("openAccessPdf") or {}
        pdf_url = pdf_info.get("url") or (
            f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else ""
        )

        # Authors
        authors = [a.get("name", "") for a in item.get("authors", [])]

        # Categories từ fieldsOfStudy
        categories = item.get("fieldsOfStudy") or ["unknown"]

        papers.append({
            "arxiv_id": paper_id,
            "title": item.get("title", "").strip(),
            "abstract": item.get("abstract", "").strip(),
            "authors": authors,
            "categories": categories,
            "published": published,
            "pdf_url": pdf_url,
            "source": "semantic_scholar",
            "citation_count": item.get("citationCount"),
            "external_id": ss_id,
        })

    return papers


async def get_paper_details(ss_id: str) -> Dict:
    """Lấy chi tiết 1 paper theo Semantic Scholar ID."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{BASE_URL}/paper/{ss_id}",
            params={"fields": FIELDS},
            headers=get_ss_headers() # Dùng header chứa API Key
        )
        response.raise_for_status()

    return response.json()


async def get_recommendations(ss_id: str, limit: int = 5) -> List[Dict]:
    """Lấy papers liên quan theo Semantic Scholar recommendations."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{ss_id}",
            params={"limit": limit, "fields": "title,abstract,authors,year,citationCount"},
            headers=get_ss_headers() # Dùng header chứa API Key
        )
        if response.status_code != 200:
            return []

    return response.json().get("recommendedPapers", [])