# backend/app/services/crawler.py
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict

ARXIV_API = "https://export.arxiv.org/api/query"
NS = "{http://www.w3.org/2005/Atom}"

async def fetch_arxiv_papers(query: str, max_results: int = 20) -> List[Dict]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(ARXIV_API, params=params)
        response.raise_for_status()

    root = ET.fromstring(response.text)
    papers = []

    for entry in root.findall(f"{NS}entry"):
        arxiv_id = entry.find(f"{NS}id").text.split("/abs/")[-1]
        title    = entry.find(f"{NS}title").text.strip().replace("\n", " ")
        abstract = entry.find(f"{NS}summary").text.strip().replace("\n", " ")
        published_str = entry.find(f"{NS}published").text
        published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))

        authors = [
            a.find(f"{NS}name").text
            for a in entry.findall(f"{NS}author")
        ]

        categories = [
            c.get("term")
            for c in entry.findall("{http://arxiv.org/schemas/atom}primary_category")
        ] or ["unknown"]

        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

        papers.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "categories": categories,
            "published": published,
            "pdf_url": pdf_url
        })

    return papers