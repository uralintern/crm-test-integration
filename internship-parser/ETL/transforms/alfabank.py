"""Трансформатор для Альфа-Банка"""
from ETL.transforms.base import BaseTransformer, create_internship_record, extract_work_format, extract_city


class AlfaBankTransformer(BaseTransformer):
    """Трансформирует данные Альфа-Банка"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Альфа-Банка в единый формат"""
        result = []
        for item in data:
            # Извлекаем направление
            direction = "Не указано"
            if item.get('direction') and isinstance(item.get('direction'), dict):
                direction = item.get('direction', {}).get('name', 'Не указано')
            
            # Извлекаем город
            city = "Москва"
            if item.get('city') and isinstance(item.get('city'), dict):
                city = item.get('city', {}).get('name', 'Москва')
            
            # Извлекаем формат работы
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
        return result
