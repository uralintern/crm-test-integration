"""
Скрипт для загрузки трансформированных данных стажировок в PostgreSQL БД
Читает JSON файлы из data/transformed и записывает в БД через internships_db

Может принимать необязательный аргумент — имя компании.
Если аргумент передан, загружает только одну компанию.
Если не передан — загружает все компании.
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from models.internship import Internship
from utils.internships_db import internships_db


class InternshipsLoader:
    """Загружает трансформированные данные в БД"""

    def __init__(self, transformed_dir: Path):
        self.transformed_dir = transformed_dir
        self.stats = {
            'total_files': 0,
            'total_records': 0,
            'loaded_records': 0,
            'failed_records': 0,
            'skipped_records': 0,
            'companies': {}
        }

    def create_internship(self, data: dict, company: str) -> Optional[Internship]:
        """Преобразует словарь в объект Internship"""
        try:
            # Валидация обязательных полей
            title = data.get('title', '').strip()
            direction = data.get('direction', 'Не указано').strip()
            company_name = data.get('company', company).strip()
            link = data.get('link', '').strip()

            if not title or not link:
                return None

            # Опциональные поля
            city = data.get('city')
            if city:
                city = city.strip() if isinstance(city, str) else None

            work_format = data.get('work_format')
            if work_format:
                work_format = work_format.strip() if isinstance(work_format, str) else None

            salary_from = data.get('salary_from')
            if salary_from:
                try:
                    salary_from = int(salary_from)
                except (ValueError, TypeError):
                    salary_from = None

            description = data.get('description')
            if description:
                description = description.strip() if isinstance(description, str) else None

            # Создание объекта Internship
            internship = Internship(
                title=title,
                direction=direction,
                company=company_name,
                city=city,
                work_format=work_format,
                link=link,
                salary_from=salary_from,
                description=description
            )

            return internship

        except Exception as e:
            print(f"  [ERROR] Ошибка при создании записи: {e}")
            return None

    def load_file(self, file_path: Path) -> List[Internship]:
        """Загружает и преобразует данные из JSON файла"""
        records = []
        company_name = file_path.stem  # Получаем имя файла без расширения

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, list):
                print(f"  [WARN] {company_name}.json: неправильный формат (не массив)")
                return records

            print(f"  Чтение {company_name}.json ({len(data)} записей)...", end=" ")

            for item in data:
                if not isinstance(item, dict):
                    self.stats['skipped_records'] += 1
                    continue

                internship = self.create_internship(item, company_name)
                if internship:
                    records.append(internship)
                else:
                    self.stats['skipped_records'] += 1

            print(f"[{len(records)} валидных]")

        except json.JSONDecodeError as e:
            print(f"  [ERROR] {company_name}.json: ошибка парсинга JSON - {e}")
        except Exception as e:
            print(f"  [ERROR] {company_name}.json: {e}")

        return records

    def load_one(self, company_name: str) -> bool:
        """Загружает данные одной компании по имени.

        Args:
            company_name: Имя компании (без .json).

        Returns:
            True при успехе, False при ошибке.
        """
        file_path = self.transformed_dir / f"{company_name}.json"
        if not file_path.exists():
            print(f"[ERROR] Файл {file_path} не найден")
            return False

        records = self.load_file(file_path)

        if not records:
            print(f"[WARN] Нет записей для загрузки у компании {company_name}")
            return True  # Не ошибка — просто нет данных

        try:
            loaded_count = internships_db.write_batch(records)
            self.stats['loaded_records'] += loaded_count
            self.stats['companies'][company_name] = {
                'total': len(records),
                'loaded': loaded_count
            }
            self.stats['total_records'] += len(records)
            self.stats['total_files'] += 1
            return True
        except Exception as e:
            print(f"  [ERROR] Ошибка при записи в БД: {e}")
            self.stats['companies'][company_name] = {
                'total': len(records),
                'loaded': 0
            }
            return False

    def load_all(self) -> bool:
        """Загружает все файлы из папки transformed"""
        if not self.transformed_dir.exists():
            print(f"[ERROR] Папка {self.transformed_dir} не найдена")
            return False

        json_files = sorted(self.transformed_dir.glob('*.json'))

        if not json_files:
            print(f"[ERROR] JSON файлы не найдены в {self.transformed_dir}")
            return False

        print(f"[INFO] Найдено {len(json_files)} файлов для загрузки")
        print()

        self.stats['total_files'] = len(json_files)

        all_success = True
        for file_path in json_files:
            company_name = file_path.stem

            if not self.load_one(company_name):
                all_success = False

        return all_success

    def print_summary(self):
        """Выводит статистику загрузки"""
        print()
        print("=" * 70)
        print("СТАТИСТИКА ЗАГРУЗКИ")
        print("=" * 70)
        print()

        print("По компаниям:")
        print("-" * 70)

        for company, stats in sorted(self.stats['companies'].items()):
            status = "[OK]" if stats['loaded'] == stats['total'] else "[!]"
            print(f"  {status} {company.ljust(20)} - "
                  f"загружено {stats['loaded']}/{stats['total']}")

        print()
        print("-" * 70)
        print(f"  Всего файлов:         {self.stats['total_files']}")
        print(f"  Всего записей:        {self.stats['total_records']}")
        print(f"  Успешно загружено:    {self.stats['loaded_records']}")
        print(f"  Пропущено:            {self.stats['skipped_records']}")
        print(f"  Ошибок:               {self.stats['total_records'] - self.stats['loaded_records']}")
        print()

        if (self.stats['total_records'] > 0
                and self.stats['loaded_records'] == self.stats['total_records']):
            print("  SUCCESS: Загрузка завершена успешно")
        else:
            print("  WARNING: Загрузка завершена с ошибками")

        print("=" * 70)


def main():
    """Главная функция"""
    print()
    print("=" * 70)
    print("Загрузка трансформированных данных стажировок в БД".center(70))
    print("=" * 70)
    print()

    # Определяем пути
    script_dir = Path(__file__).parent
    project_root = script_dir
    transformed_dir = project_root / "data" / "transformed"

    print(f"[INFO] Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[INFO] Исходная папка: {transformed_dir}")
    print()

    # Создаем загрузчик
    loader = InternshipsLoader(transformed_dir)

    # Выполняем загрузку
    print("[INFO] Начало загрузки данных...")
    print()

    try:
        # Если передан аргумент — загружаем только одну компанию
        if len(sys.argv) > 1:
            company = sys.argv[1]
            print(f"[INFO] Загрузка только компании: {company}")
            success = loader.load_one(company)
            loader.print_summary()

            if success:
                print()
                print("[SUCCESS] Данные успешно загружены в БД!")
                return 0
            else:
                print()
                print("[ERROR] Ошибка при загрузке данных")
                return 1
        else:
            # Иначе загружаем все компании
            success = loader.load_all()
            loader.print_summary()

            if success and loader.stats['loaded_records'] > 0:
                print()
                print("[SUCCESS] Все данные успешно загружены в БД!")
                return 0
            else:
                print()
                print("[ERROR] Ошибка при загрузке данных")
                return 1

    except KeyboardInterrupt:
        print()
        print("[INTERRUPTED] Загрузка прервана пользователем")
        return 1
    except Exception as e:
        print()
        print(f"[FATAL ERROR] Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())