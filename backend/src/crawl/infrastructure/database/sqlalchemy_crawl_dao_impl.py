from typing import List, Optional
from sqlalchemy.orm import Session
from src.shared.db_manager import db_session
from .models import CrawlTaskModel, CrawlResultModel
from .i_crawl_dao import ICrawlDao

class SqlAlchemyCrawlDaoImpl(ICrawlDao):
    """
    SQLAlchemy implementation of ICrawlDao
    """
    
    def __init__(self, session: Session = None):
        """
        :param session: Optional session for testing, otherwise uses global scoped session
        """
        self._session = session if session else db_session

    def create_task(self, task: CrawlTaskModel) -> None:
        try:
            self._session.add(task)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise e

    def get_task_by_id(self, task_id: str) -> Optional[CrawlTaskModel]:
        return self._session.query(CrawlTaskModel).filter(CrawlTaskModel.id == task_id).first()

    def update_task(self, task: CrawlTaskModel) -> None:
        try:
            # If the object is already attached to session, just commit.
            # If not, merge it.
            self._session.merge(task)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise e

    def get_all_tasks(self) -> List[CrawlTaskModel]:
        return self._session.query(CrawlTaskModel).order_by(CrawlTaskModel.created_at.desc()).all()

    def add_result(self, result: CrawlResultModel) -> None:
        try:
            self._session.add(result)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise e

    def get_results_by_task_id(self, task_id: str) -> List[CrawlResultModel]:
        return self._session.query(CrawlResultModel).filter(CrawlResultModel.task_id == task_id).all()

    def delete_results_by_task_id(self, task_id: str) -> None:
        try:
            self._session.query(CrawlResultModel).filter(CrawlResultModel.task_id == task_id).delete()
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise e
