"""Трансформатор для ВКонтакте"""
import logging
from ETL.transforms.base import BaseTransformer, create_internship_record
from ETL.logging_config import get_logger

logger = get_logger(__name__)


class VKTransformer(BaseTransformer):
    """Трансформирует данные ВКонтакте"""
    
    def transform(self, data: dict) -> list[dict]:
        """Преобразует данные ВКонтакте в единый формат"""
        logger.info("Starting VK transformation")
        result = []
        
        page = data.get('props', {}).get('pageProps', {}).get('page', {})
        vacancies = page.get('vacancies', [])
        directions = page.get('directions', [])
        
        direction_map = {d['id']: d['name'] for d in directions}
        
        format_map = {
            'office': 'Офис',
            'remote': 'Удалённая работа',
            'hybrid': 'Гибрид'
        }
        
        for vacancy in vacancies:
            if not vacancy.get('is_opened', False):
                continue
            
            direction_name = direction_map.get(
                vacancy.get('direction', 0),
                'Не указано'
            )
            
            work_format = format_map.get(
                vacancy.get('format', ''),
                None
            )
            
            record = create_internship_record(
                title=vacancy.get('title', ''),
                direction=direction_name,
                company="ВКонтакте",
                link=f"https://vk.company/careers/internship/{vacancy.get('id', '')}",
                city=vacancy.get('city', 'Москва'),
                work_format=work_format,
                description=None
            )
            result.append(record)
        
        logger.info("VK transformation finished, output records: %d", len(result))
        return result
