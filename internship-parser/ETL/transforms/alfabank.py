"""Трансформатор для Альфа-Банка"""
import logging
from ETL.transforms.base import BaseTransformer, create_internship_record, extract_work_format, extract_city
from ETL.logging_config import get_logger

logger = get_logger(__name__)


class AlfaBankTransformer(BaseTransformer):
    """Трансформирует данные Альфа-Банка"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Альфа-Банка в единый формат"""
        logger.info("Starting Alfa-Bank transformation, input items: %d", len(data))
        result = []
        for item in data:
            direction = "Не указано"
            if item.get('direction') and isinstance(item.get('direction'), dict):
                direction = item.get('direction', {}).get('name', 'Не указано')
            
            city = "Москва"
            if item.get('city') and isinstance(item.get('city'), dict):
                city = item.get('city', {}).get('name', 'Москва')
            
            work_format = None
            if item.get('workFormat') and isinstance(item.get('workFormat'), dict):
                work_format = item.get('workFormat', {}).get('name')
            
            record = create_internship_record(
                title=item.get('name', ''),
                direction=direction,
                company="Альфа-Банк",
                link=item.get('link', ''),
                city=city,
                work_format=work_format,
                description=None
            )
            result.append(record)
        logger.info("Alfa-Bank transformation finished, output records: %d", len(result))
        return result
