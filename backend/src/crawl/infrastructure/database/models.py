from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from src.shared.db_manager import Base
from datetime import datetime
from sqlalchemy.dialects.mysql import LONGTEXT

class CrawlTaskModel(Base):
    __tablename__ = "crawl_tasks"

    id = Column(String(36), primary_key=True, comment="Task UUID")
    name = Column(String(255), nullable=True, comment="Task Name")
    status = Column(String(50), nullable=False, default="PENDING", comment="Task Status")
    
    # Config fields flattened
    start_url = Column(Text, nullable=False, comment="Start URL")
    strategy = Column(String(50), default="BFS", comment="Crawl Strategy")
    max_depth = Column(Integer, default=3, comment="Max Depth")
    max_pages = Column(Integer, default=100, comment="Max Pages")
    request_interval = Column(Float, default=1.0, comment="Request Interval")
    allow_domains = Column(JSON, nullable=True, comment="Allowed Domains List")
    priority_domains = Column(JSON, nullable=True, comment="Priority Domains List")
    visited_urls = Column(JSON, nullable=True, comment="Set of visited URLs")
    
    created_at = Column(DateTime, default=datetime.now, comment="Creation Time")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="Update Time")

    # Relationship
    results = relationship("CrawlResultModel", back_populates="task", cascade="all, delete-orphan")
    pdf_results = relationship("PdfResultModel", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CrawlTaskModel(id={self.id}, status={self.status})>"

class CrawlResultModel(Base):
    __tablename__ = "crawl_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(36), ForeignKey("crawl_tasks.id"), nullable=False, index=True)
    
    url = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    author = Column(String(255), nullable=True)
    abstract = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True)
    publish_date = Column(String(100), nullable=True)
    pdf_links = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    depth = Column(Integer, default=0)
    crawled_at = Column(DateTime, default=datetime.now)

    # Relationship
    task = relationship("CrawlTaskModel", back_populates="results")

    def __repr__(self):
        return f"<CrawlResultModel(id={self.id}, url={self.url})>"

class PdfResultModel(Base):
    __tablename__ = "pdf_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(36), ForeignKey("crawl_tasks.id"), nullable=False, index=True)
    
    url = Column(Text, nullable=False)
    is_success = Column(Integer, default=1) # 1 for success, 0 for fail
    error_message = Column(Text, nullable=True)
    
    # Content
    content_text = Column(LONGTEXT, nullable=True)
    
    # Metadata
    meta_title = Column(Text, nullable=True)
    meta_author = Column(Text, nullable=True)
    page_count = Column(Integer, default=0)
    creation_date = Column(DateTime, nullable=True)
    
    depth = Column(Integer, default=0)
    crawled_at = Column(DateTime, default=datetime.now)

    # Relationship
    task = relationship("CrawlTaskModel", back_populates="pdf_results")

    def __repr__(self):
        return f"<PdfResultModel(id={self.id}, url={self.url}, success={self.is_success})>"
