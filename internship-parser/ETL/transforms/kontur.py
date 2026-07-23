"""Трансформатор для Контура"""
from ETL.transforms.base import BaseTransformer, create_internship_record


class KonturTransformer(BaseTransformer):
    """Трансформирует данные Контура"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Контура в единый формат"""
        result = []
        for item in data:
            record = create_internship_record(
                title=item.get('title', ''),
                direction=item.get('title', ''),  # Используем title как направление
                company="Контур",
                link=item.get('link', ''),
                city="Екатеринбург",  # Контур базируется в Екатеринбурге
                work_format="Удалённая работа",  # По умолчанию удалённо
                description=item.get('desc')
            )
            result.append(record)
        return result
