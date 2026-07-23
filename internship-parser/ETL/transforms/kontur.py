"""Трансформатор для Контура"""
import logging
from ETL.transforms.base import BaseTransformer, create_internship_record
from ETL.logging_config import get_logger

logger = get_logger(__name__)


class KonturTransformer(BaseTransformer):
    """Трансформирует данные Контура"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Контура в единый формат"""
        logger.info("Starting Kontur transformation, input items: %d", len(data))
        result = []
        for item in data:
            record = create_internship_record(
                title=item.get('title', ''),
                direction=item.get('title', ''),
                company="Контур",
                link=item.get('link', ''),
                city="Екатеринбург",
                work_format="Удалённая работа",
                description=item.get('desc')
            )
            result.append(record)
        logger.info("Kontur transformation finished, output records: %d", len(result))
        return result
