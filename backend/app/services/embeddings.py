# backend/app/services/embeddings.py
import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import AsyncOpenAI
from app.core.config import settings

# Client OpenAI async
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# ChromaDB lưu local (tạo thư mục chroma_data/ tự động)
chroma_client = chromadb.PersistentClient(
    path="./chroma_data",
    settings=ChromaSettings(anonymized_telemetry=False)
)

# Collection chứa embeddings của papers
collection = chroma_client.get_or_create_collection(
    name="papers",
    metadata={"hnsw:space": "cosine"}
)


async def embed_text(text: str) -> list[float]:
    """Gọi OpenAI để tạo embedding cho 1 đoạn text."""
    response = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text[:8000]  # giới hạn token
    )
    return response.data[0].embedding


async def index_paper(arxiv_id: str, title: str, abstract: str):
    """Tạo embedding và lưu vào ChromaDB."""
    # Ghép title + abstract để embedding có context đầy đủ
    text = f"{title}\n\n{abstract}"
    embedding = await embed_text(text)

    # Upsert — nếu đã có thì update, chưa có thì thêm mới
    collection.upsert(
        ids=[arxiv_id],
        embeddings=[embedding],
        documents=[text],
        metadatas=[{"arxiv_id": arxiv_id, "title": title}]
    )


async def semantic_search(query: str, n_results: int = 10) -> list[dict]:
    """Tìm kiếm semantic: query → embedding → tìm papers gần nhất."""
    query_embedding = await embed_text(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["metadatas", "distances", "documents"]
    )

    # Format kết quả trả về
    papers = []
    if results["ids"] and results["ids"][0]:
        for i, arxiv_id in enumerate(results["ids"][0]):
            papers.append({
                "arxiv_id": arxiv_id,
                "title": results["metadatas"][0][i]["title"],
                "score": round(1 - results["distances"][0][i], 4),  # cosine similarity
                "snippet": results["documents"][0][i][:300] + "..."
            })

    return papers


def get_indexed_count() -> int:
    """Trả về số lượng papers đã được index."""
    return collection.count()