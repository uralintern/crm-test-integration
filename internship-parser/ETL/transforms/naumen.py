"""Трансформатор для Naumen"""
from ETL.transforms.base import BaseTransformer, create_internship_record


class NaumenTransformer(BaseTransformer):
    """Трансформирует данные Naumen"""

    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Naumen в единый формат"""
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
        return result
