"""Трансформатор для Яндекса"""
from typing import Optional
from ETL.transforms.base import BaseTransformer, create_internship_record, extract_text_from_html


class YandexTransformer(BaseTransformer):
    """Трансформирует данные Яндекса"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Яндекса в единый формат"""
        result = []
        for item in data:
            record = create_internship_record(
                title=extract_text_from_html(item.get('heading', '')),
                direction=extract_text_from_html(item.get('title', '')),
                company="Яндекс",
                link=item.get('link', ''),
                city="Москва",  # Яндекс основной офис в Москве
                work_format=None,
                description=extract_text_from_html(item.get('description', ''))
            )
            result.append(record)
        return result
