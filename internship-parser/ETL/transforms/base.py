"""Базовый класс для трансформаторов"""
import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


def extract_text_from_html(html_text: str) -> str:
    """Удаляет HTML теги и сущности из текста"""
    if not html_text:
        return ""
    import html
    # Удаляем теги
    text = re.sub(r'<[^>]+>', '', html_text)
    # Декодируем HTML сущности
    text = html.unescape(text)
    # Удаляем лишние пробелы и переносы строк
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_city(city_data: any) -> Optional[str]:
    """Извлекает город из различных форматов данных"""
    if isinstance(city_data, str):
        return city_data if city_data.strip() else None
    elif isinstance(city_data, dict):
        return city_data.get('name') or city_data.get('title')
    elif isinstance(city_data, list):
        if city_data and isinstance(city_data[0], dict):
            return city_data[0].get('name') or city_data[0].get('title')
        elif city_data and isinstance(city_data[0], str):
            return city_data[0]
    return None


def extract_work_format(format_data: any) -> Optional[str]:
    """Извлекает формат работы из различных форматов данных"""
    if isinstance(format_data, str):
        return format_data if format_data.strip() else None
    elif isinstance(format_data, dict):
        return format_data.get('name') or format_data.get('title')
    elif isinstance(format_data, list):
        if format_data:
            if isinstance(format_data[0], dict):
                return format_data[0].get('name') or format_data[0].get('title')
            elif isinstance(format_data[0], str):
                return format_data[0]
    return None


class BaseTransformer(ABC):
    """Базовый класс для всех трансформаторов"""
    
    def __init__(self, company_name: str, input_path: Path, output_path: Path):
        self.company_name = company_name
        self.input_path = input_path
        self.output_path = output_path
    
    def load_data(self) -> any:
        """Загружает данные из JSON файла"""
        with open(self.input_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_data(self, data: list[dict]) -> None:
        """Сохраняет данные в JSON файл"""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @abstractmethod
    def transform(self, data: any) -> list[dict]:
        """Трансформирует данные в единый формат"""
        pass
    
    def run(self) -> None:
        """Выполняет трансформацию"""
        print(f"Обработка {self.company_name}...")
        try:
            raw_data = self.load_data()
            transformed_data = self.transform(raw_data)
            self.save_data(transformed_data)
            print(f"[OK] {self.company_name}: {len(transformed_data)} записей трансформировано")
        except Exception as e:
            print(f"[ERROR] Ошибка при обработке {self.company_name}: {e}")


def create_internship_record(
    title: str,
    direction: str,
    company: str,
    link: str,
    city: Optional[str] = None,
    work_format: Optional[str] = None,
    salary_from: Optional[int] = None,
    description: Optional[str] = None
) -> dict:
    """Создает запись стажировки в едином формате"""
    return {
        "title": title or "Стажировка",
        "direction": direction or "Не указано",
        "company": company,
        "city": city,
        "work_format": work_format,
        "salary_from": salary_from,
        "description": description,
        "link": link
    }
