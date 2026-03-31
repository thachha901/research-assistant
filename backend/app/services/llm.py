# backend/app/services/llm.py
from openai import AsyncOpenAI
from app.core.config import settings

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

SUMMARY_PROMPT = """You are an expert research assistant. 
Summarize the following academic paper clearly and concisely.

Return your response in this exact JSON format:
{{
  "one_line": "One sentence summary of the paper",
  "key_idea": "The main idea or problem being solved (2-3 sentences)",
  "contributions": ["contribution 1", "contribution 2", "contribution 3"],
  "method": "Brief explanation of the approach or methodology (2-3 sentences)",
  "limitations": ["limitation 1", "limitation 2"],
  "applications": ["application 1", "application 2"]
}}

Paper Title: {title}
Abstract: {abstract}

Return only valid JSON, no extra text."""


async def summarize_paper(title: str, abstract: str) -> dict:
    """Gọi OpenAI GPT để tóm tắt paper, trả về structured JSON."""
    prompt = SUMMARY_PROMPT.format(title=title, abstract=abstract[:3000])

    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",      # rẻ + nhanh, đủ dùng cho summary
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,          # thấp để output ổn định
        response_format={"type": "json_object"}
    )

    import json
    content = response.choices[0].message.content
    return json.loads(content)


async def compare_papers(papers: list[dict]) -> dict:
    """So sánh nhiều papers với nhau."""
    papers_text = "\n\n".join([
        f"Paper {i+1}: {p['title']}\nAbstract: {p['abstract'][:500]}"
        for i, p in enumerate(papers)
    ])

    prompt = f"""Compare these {len(papers)} research papers and return JSON:
{{
  "common_themes": ["theme 1", "theme 2"],
  "key_differences": ["difference 1", "difference 2"],
  "recommended_reading_order": [1, 2, 3],
  "recommendation": "Which paper to read first and why"
}}

Papers:
{papers_text}

Return only valid JSON."""

    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        response_format={"type": "json_object"}
    )

    import json
    return json.loads(response.choices[0].message.content)