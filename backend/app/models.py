# backend/app/models.py
from sqlalchemy import Column, String, Text, DateTime, Integer, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.database import Base

class Paper(Base):
    __tablename__ = "papers"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    arxiv_id   = Column(String, unique=True, index=True)
    title      = Column(String, nullable=False)
    abstract   = Column(Text)
    authors    = Column(ARRAY(String))
    categories = Column(ARRAY(String))
    published  = Column(DateTime)
    pdf_url    = Column(String)
    source         = Column(String, default="arxiv")        # "arxiv" hoặc "semantic_scholar"
    citation_count = Column(Integer, nullable=True)
    external_id    = Column(String, nullable=True, index=True)  # ID từ nguồn gốc
    summary_ai = Column(Text, nullable=True)   # cache AI summary
    created_at = Column(DateTime, server_default=func.now())

class SavedPaper(Base):
    __tablename__ = "saved_papers"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    arxiv_id   = Column(String, index=True)
    user_id    = Column(String, index=True)   # dùng simple string trước, auth sau
    created_at = Column(DateTime, server_default=func.now())

# thêm vào cuối file models.py
class Subscription(Base):
    __tablename__ = "subscriptions"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(String, index=True, default="local_user")
    keyword    = Column(String, nullable=True)   # theo dõi keyword
    author     = Column(String, nullable=True)   # theo dõi tác giả
    created_at = Column(DateTime, server_default=func.now())
    last_run   = Column(DateTime, nullable=True) # lần crawl gần nhất


class Notification(Base):
    __tablename__ = "notifications"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(String, index=True)
    arxiv_id   = Column(String)
    title      = Column(String)
    reason     = Column(String)   # "keyword: transformer" hoặc "author: Yann LeCun"
    is_read    = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())