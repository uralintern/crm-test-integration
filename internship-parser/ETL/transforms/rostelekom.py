"""Трансформатор для Ростелекома"""
import logging
from ETL.transforms.base import BaseTransformer, create_internship_record
from ETL.logging_config import get_logger

logger = get_logger(__name__)


class RostelekomTransformer(BaseTransformer):
    """Трансформирует данные Ростелекома"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Ростелекома в единый формат"""
        logger.info("Starting Rostelecom transformation, input items: %d", len(data))
        result = []
        for item in data:
            record = create_internship_record(
                title="Стажировка в " + item.get('title', ''),
                direction=item.get('title', ''),
                company="Ростелеком",
                link=item.get('link', ''),
                city="Москва",
                work_format=None,
                description=item.get('description')
            )
            result.append(record)
        logger.info("Rostelecom transformation finished, output records: %d", len(result))
        return result
