"""Трансформатор для МТС"""
import logging
from ETL.transforms.base import BaseTransformer, create_internship_record, extract_city
from ETL.logging_config import get_logger

logger = get_logger(__name__)


class MTSTransformer(BaseTransformer):
    """Трансформирует данные МТС"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные МТС в единый формат"""
        logger.info("Starting MTS transformation, input items: %d", len(data))
        result = []
        for item in data:
            city = extract_city(item.get('cities', []))
            if not city:
                city = "Москва"
            
            record = create_internship_record(
                title=item.get('displayTitle') or item.get('title', ''),
                direction="Информационные технологии",
                company="МТС",
                link=item.get('link', ''),
                city=city,
                work_format=None,
                description=item.get('summary')
            )
            result.append(record)
        logger.info("MTS transformation finished, output records: %d", len(result))
        return result
