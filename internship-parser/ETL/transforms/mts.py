"""Трансформатор для МТС"""
from ETL.transforms.base import BaseTransformer, create_internship_record, extract_city


class MTSTransformer(BaseTransformer):
    """Трансформирует данные МТС"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные МТС в единый формат"""
        result = []
        for item in data:
            # Извлекаем город
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
        return result
