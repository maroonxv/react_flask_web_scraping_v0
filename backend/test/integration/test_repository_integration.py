import pytest
import uuid
from datetime import datetime
from src.shared.db_manager import init_db, db_session
from src.crawl.infrastructure.database.sqlalchemy_crawl_dao_impl import SqlAlchemyCrawlDaoImpl
from src.crawl.infrastructure.database.crawl_repository_impl import CrawlRepositoryImpl
from src.crawl.domain.entity.crawl_task import CrawlTask
from src.crawl.domain.value_objects.crawl_config import CrawlConfig
from src.crawl.domain.value_objects.crawl_result import CrawlResult
from src.crawl.domain.value_objects.crawl_strategy import CrawlStrategy

@pytest.fixture(scope="module")
def setup_database():
    """Ensure tables exist before running tests"""
    from src.shared.db_manager import engine, Base
    # Drop all tables to ensure fresh schema
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    # No teardown of tables, just data cleanup in tests

@pytest.fixture
def repository():
    # Use the real db_session
    dao = SqlAlchemyCrawlDaoImpl(db_session)
    return CrawlRepositoryImpl(dao)

def test_repository_save_and_retrieve_task(setup_database, repository):
    task_id = str(uuid.uuid4())
    config = CrawlConfig(
        start_url="http://integration-test.com",
        strategy=CrawlStrategy.BFS,
        max_depth=3,
        max_pages=50,
        allow_domains=["integration-test.com"],
        priority_domains=["important.com"]
    )
    task = CrawlTask(id=task_id, config=config, name="Integration Task")
    task.visited_urls.add("http://integration-test.com")
    
    # Save
    repository.save_task(task)
    
    # Retrieve
    retrieved = repository.get_task(task_id)
    assert retrieved is not None
    assert retrieved.id == task_id
    assert retrieved.name == "Integration Task"
    assert retrieved.config.start_url == "http://integration-test.com"
    assert "http://integration-test.com" in retrieved.visited_urls
    
    # Cleanup
    # We don't have a delete_task in repository, so we rely on manual DB cleanup or just leave it
    # For integration tests, usually we want to clean up.
    # Let's add a cleanup using dao directly
    dao = SqlAlchemyCrawlDaoImpl(db_session)
    # Using internal session to delete
    from src.crawl.infrastructure.database.models import CrawlTaskModel
    db_session.query(CrawlTaskModel).filter_by(id=task_id).delete()
    db_session.commit()

def test_repository_save_results(setup_database, repository):
    task_id = str(uuid.uuid4())
    config = CrawlConfig(start_url="http://res-test.com")
    task = CrawlTask(id=task_id, config=config, name="Result Task")
    repository.save_task(task)
    
    result = CrawlResult(
        url="http://res-test.com/page1",
        title="Integration Result",
        depth=1,
        crawled_at=datetime.now()
    )
    
    repository.save_result(task_id, result)
    
    results = repository.get_results(task_id)
    assert len(results) == 1
    assert results[0].url == "http://res-test.com/page1"
    assert results[0].title == "Integration Result"
    
    # Cleanup
    dao = SqlAlchemyCrawlDaoImpl(db_session)
    dao.delete_results_by_task_id(task_id)
    from src.crawl.infrastructure.database.models import CrawlTaskModel
    db_session.query(CrawlTaskModel).filter_by(id=task_id).delete()
    db_session.commit()
