"""Трансформатор для Яндекса"""
import logging
from typing import Optional
from ETL.transforms.base import BaseTransformer, create_internship_record, extract_text_from_html
from ETL.logging_config import get_logger

logger = get_logger(__name__)


class YandexTransformer(BaseTransformer):
    """Трансформирует данные Яндекса"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Яндекса в единый формат"""
        logger.info("Starting Yandex transformation, input items: %d", len(data))
        result = []
        for item in data:
            record = create_internship_record(
                title=extract_text_from_html(item.get('heading', '')),
                direction=extract_text_from_html(item.get('title', '')),
                company="Яндекс",
                link=item.get('link', ''),
                city="Москва",
                work_format=None,
                description=extract_text_from_html(item.get('description', ''))
            )
            result.append(record)
        logger.info("Yandex transformation finished, output records: %d", len(result))
        return result
