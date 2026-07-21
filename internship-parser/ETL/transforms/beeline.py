"""Трансформатор для Beeline"""
from ETL.transforms.base import BaseTransformer, create_internship_record, extract_city


class BeelineTransformer(BaseTransformer):
    """Трансформирует данные Beeline"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Beeline в единый формат"""
        result = []
        for item in data:
            # Извлекаем город
            city = extract_city(item.get('city', []))
            if not city:
                city = "Москва"
            
            # Извлекаем формат работы
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
        return result
