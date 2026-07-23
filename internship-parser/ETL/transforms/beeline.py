"""Трансформатор для Beeline"""
import logging
from ETL.transforms.base import BaseTransformer, create_internship_record, extract_city
from ETL.logging_config import get_logger

logger = get_logger(__name__)


class BeelineTransformer(BaseTransformer):
    """Трансформирует данные Beeline"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Beeline в единый формат"""
        logger.info("Starting Beeline transformation, input items: %d", len(data))
        result = []
        for item in data:
            city = extract_city(item.get('city', []))
            if not city:
                city = "Москва"
            
            work_format = None
            formats = item.get('work_format', [])
            if formats:
                work_format = formats[0]
            
            record = create_internship_record(
                title=item.get('name', ''),
                direction=item.get('role', 'Не указано'),
                company="Beeline",
                link=item.get('link', ''),
                city=city,
                work_format=work_format,
                description=None
            )
            result.append(record)
        logger.info("Beeline transformation finished, output records: %d", len(result))
        return result
