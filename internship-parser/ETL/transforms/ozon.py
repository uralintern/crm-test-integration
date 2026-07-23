"""Трансформатор для Озона"""
import logging
from ETL.transforms.base import BaseTransformer, create_internship_record, extract_work_format
from ETL.logging_config import get_logger

logger = get_logger(__name__)


class OzonTransformer(BaseTransformer):
    """Трансформирует данные Озона"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Озона в единый формат"""
        logger.info("Starting Ozon transformation, input items: %d", len(data))
        result = []
        for item in data:
            work_format = None
            if item.get('work_formats'):
                formats = item.get('work_formats', [])
                work_format = formats[0] if formats else None
            
            record = create_internship_record(
                title=item.get('title', ''),
                direction="Информационные технологии",
                company="Озон",
                link=item.get('link', ''),
                city=item.get('city', 'Москва'),
                work_format=work_format,
                description=None
            )
            result.append(record)
        logger.info("Ozon transformation finished, output records: %d", len(result))
        return result
