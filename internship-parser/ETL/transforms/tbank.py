"""Трансформатор для Т-Банка"""
from ETL.transforms.base import BaseTransformer, create_internship_record, extract_text_from_html


class TBankTransformer(BaseTransformer):
    """Трансформирует данные Т-Банка"""
    
    def transform(self, data: list[dict]) -> list[dict]:
        """Преобразует данные Т-Банка в единый формат"""
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
        return result
