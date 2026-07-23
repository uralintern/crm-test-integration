import logging
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from utils.config import config
from models.internship import Internship, Base

logger = logging.getLogger(__name__)


class InternshipsDB:
    _instance: Optional['InternshipsDB'] = None

    def __new__(cls, db_url: str) -> 'InternshipsDB':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_url: str):
        if self._initialized:
            return

        self._db_url = db_url
        self._engine = create_engine(
            self._db_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False
        )
        self._SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self._engine
        )
        self._init_tables()
        self._initialized = True
        logger.info("InternshipsDB инициализирован успешно")

    def _init_tables(self) -> None:
        try:
            Base.metadata.create_all(bind=self._engine)
            logger.info("Таблицы инициализированы")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при инициализации таблиц: {e}")
            raise

    def _get_session(self) -> Session:
        return self._SessionLocal()

    def write(self, data: Internship) -> bool:
        session: Optional[Session] = None
        try:
            session = self._get_session()
            session.add(data)
            session.commit()
            logger.info(f"Стажировка '{data.title}' успешно записана в БД")
            return True
        except SQLAlchemyError as e:
            if session:
                session.rollback()
            logger.error(f"Ошибка при записи в БД: {e}")
            return False
        finally:
            if session:
                session.close()

    def write_batch(self, data_list: list[Internship]) -> int:
        session: Optional[Session] = None
        count = 0
        try:
            session = self._get_session()
            session.add_all(data_list)
            session.commit()
            count = len(data_list)
            logger.info(f"Успешно записано {count} стажировок в БД")
            return count
        except SQLAlchemyError as e:
            if session:
                session.rollback()
            logger.error(f"Ошибка при массовой записи в БД: {e}")
            return count
        finally:
            if session:
                session.close()

    def clear(self) -> int:
        session: Optional[Session] = None
        try:
            session = self._get_session()
            count = session.query(Internship).delete()
            session.commit()
            logger.info(f"Очищено {count} записей из БД")
            return count
        except SQLAlchemyError as e:
            if session:
                session.rollback()
            logger.error(f"Ошибка при очистке БД: {e}")
            return 0
        finally:
            if session:
                session.close()

    def close(self) -> None:
        try:
            self._engine.dispose()
            logger.info("Соединение с БД закрыто")
        except Exception as e:
            logger.error(f"Ошибка при закрытии соединения: {e}")


internships_db = InternshipsDB(config.db_url)
