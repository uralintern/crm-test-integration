"""Трансформатор для ВКонтакте"""
from ETL.transforms.base import BaseTransformer, create_internship_record


class VKTransformer(BaseTransformer):
    """Трансформирует данные ВКонтакте"""
    
    def transform(self, data: dict) -> list[dict]:
        """Преобразует данные ВКонтакте в единый формат"""
        result = []
        
        # Извлекаем вакансии и направления
        page = data.get('props', {}).get('pageProps', {}).get('page', {})
        vacancies = page.get('vacancies', [])
        directions = page.get('directions', [])
        
        # Создаем словарь направлений для быстрого поиска
        direction_map = {d['id']: d['name'] for d in directions}
        
        # Преобразуем формат работы из внутреннего кода
        format_map = {
            'office': 'Офис',
            'remote': 'Удалённая работа',
            'hybrid': 'Гибрид'
        }
        
        for vacancy in vacancies:
            # Пропускаем закрытые вакансии
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
        
        return result
