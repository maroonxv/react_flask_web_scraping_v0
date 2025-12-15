import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from src.shared.db_manager import Base
from src.crawl.infrastructure.database.models import CrawlTaskModel, CrawlResultModel
from src.crawl.infrastructure.database.sqlalchemy_crawl_dao_impl import SqlAlchemyCrawlDaoImpl

# Use in-memory SQLite for unit tests
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def session():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)

@pytest.fixture
def dao(session):
    return SqlAlchemyCrawlDaoImpl(session)

def test_create_and_get_task(dao, session):
    task = CrawlTaskModel(
        id="task-1",
        name="Test Task",
        status="PENDING",
        start_url="http://example.com",
        strategy="BFS",
        max_depth=2,
        max_pages=10,
        request_interval=1.0,
        allow_domains=["example.com"],
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    dao.create_task(task)
    
    fetched = dao.get_task_by_id("task-1")
    assert fetched is not None
    assert fetched.name == "Test Task"
    assert fetched.status == "PENDING"
    assert fetched.allow_domains == ["example.com"]

def test_update_task(dao, session):
    task = CrawlTaskModel(
        id="task-2",
        name="Update Test",
        status="PENDING",
        start_url="http://test.com",
        created_at=datetime.now()
    )
    dao.create_task(task)
    
    task.status = "RUNNING"
    dao.update_task(task)
    
    fetched = dao.get_task_by_id("task-2")
    assert fetched.status == "RUNNING"

def test_add_and_get_results(dao, session):
    task = CrawlTaskModel(
        id="task-3",
        name="Result Test",
        status="RUNNING",
        start_url="http://result.com",
        created_at=datetime.now()
    )
    dao.create_task(task)
    
    result = CrawlResultModel(
        task_id="task-3",
        url="http://result.com/page1",
        title="Page 1",
        depth=1,
        crawled_at=datetime.now()
    )
    dao.add_result(result)
    
    results = dao.get_results_by_task_id("task-3")
    assert len(results) == 1
    assert results[0].url == "http://result.com/page1"
    assert results[0].title == "Page 1"

def test_delete_results(dao, session):
    task = CrawlTaskModel(
        id="task-4",
        name="Delete Test",
        status="RUNNING",
        start_url="http://delete.com",
        created_at=datetime.now()
    )
    dao.create_task(task)
    
    dao.add_result(CrawlResultModel(task_id="task-4", url="u1"))
    dao.add_result(CrawlResultModel(task_id="task-4", url="u2"))
    
    assert len(dao.get_results_by_task_id("task-4")) == 2
    
    dao.delete_results_by_task_id("task-4")
    assert len(dao.get_results_by_task_id("task-4")) == 0
