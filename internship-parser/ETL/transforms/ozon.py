"""Трансформатор для Озона"""
from ETL.transforms.base import BaseTransformer, create_internship_record, extract_work_format


class OzonTransformer(BaseTransformer):
    """Трансформирует данные Озона"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Озона в единый формат"""
        result = []
        for item in data:
            work_format = None
            if item.get('work_formats'):
                formats = item.get('work_formats', [])
                work_format = formats[0] if formats else None
            
            record = create_internship_record(
                title=item.get('title', ''),
                direction="Информационные технологии",  # Озон технологический сектор
                company="Озон",
                link=item.get('link', ''),
                city=item.get('city', 'Москва'),
                work_format=work_format,
                description=None
            )
            result.append(record)
        return result
