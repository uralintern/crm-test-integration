"""Трансформатор для Ростелекома"""
from ETL.transforms.base import BaseTransformer, create_internship_record


class RostelekomTransformer(BaseTransformer):
    """Трансформирует данные Ростелекома"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Ростелекома в единый формат"""
        result = []
        for item in data:
            record = create_internship_record(
                title="Стажировка в " + item.get('title', ''),
                direction=item.get('title', ''),
                company="Ростелеком",
                link=item.get('link', ''),
                city="Москва",  # Основной офис в Москве
                work_format=None,
                description=item.get('description')
            )
            result.append(record)
        return result
