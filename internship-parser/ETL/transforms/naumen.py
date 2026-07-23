"""Трансформатор для Naumen"""
import logging
from ETL.transforms.base import BaseTransformer, create_internship_record
from ETL.logging_config import get_logger

logger = get_logger(__name__)


class NaumenTransformer(BaseTransformer):
    """Трансформирует данные Naumen"""

    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Naumen в единый формат"""
        logger.info("Starting Naumen transformation, input items: %d", len(data))
        result = []
        for item in data:
            direction = item.get('title', 'Не указано')
            record = create_internship_record(
                title=direction,
                direction=direction,
                company="Naumen",
                link=item.get('link', ''),
                city=item.get('city'),
                work_format=None,
                description=None
            )
            result.append(record)
        logger.info("Naumen transformation finished, output records: %d", len(result))
        return result
