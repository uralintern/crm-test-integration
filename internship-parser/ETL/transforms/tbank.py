"""Трансформатор для Т-Банка"""
import logging
from ETL.transforms.base import BaseTransformer, create_internship_record, extract_text_from_html
from ETL.logging_config import get_logger

logger = get_logger(__name__)


class TBankTransformer(BaseTransformer):
    """Трансформирует данные Т-Банка"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Т-Банка в единый формат"""
        logger.info("Starting T-Bank transformation, input items: %d", len(data))
        result = []
        for item in data:
            record = create_internship_record(
                title=extract_text_from_html(item.get('title', '')),
                direction="Информационные технологии",
                company="Т-Банк",
                link=item.get('link', ''),
                city="Москва",
                work_format=None,
                description=extract_text_from_html(item.get('desc', ''))
            )
            result.append(record)
        logger.info("T-Bank transformation finished, output records: %d", len(result))
        return result
