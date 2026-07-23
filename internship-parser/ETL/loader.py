"""
Скрипт для загрузки трансформированных данных стажировок в PostgreSQL БД
Читает JSON файлы из data/transformed и записывает в БД через internships_db

Может принимать необязательный аргумент — имя компании.
Если аргумент передан, загружает только одну компанию.
Если не передан — загружает все компании.
"""
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from ETL.logging_config import get_logger

from models.internship import Internship
from utils.internships_db import internships_db

logger = get_logger(__name__)


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
            title = data.get('title', '').strip()
            direction = data.get('direction', 'Не указано').strip()
            company_name = data.get('company', company).strip()
            link = data.get('link', '').strip()

            if not title or not link:
                return None

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
            logger.error("[ERROR] Failed to create record: %s", e)
            return None

    def load_file(self, file_path: Path) -> List[Internship]:
        """Загружает и преобразует данные из JSON файла"""
        records = []
        company_name = file_path.stem

        try:
            logger.info("Opening file: %s", file_path)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info("File loaded: %s", file_path)

            if not isinstance(data, list):
                logger.warning("[WARN] %s.json: invalid format (not an array)", company_name)
                return records

            logger.info("Processing %s.json (%d records)...", company_name, len(data))

            for item in data:
                if not isinstance(item, dict):
                    self.stats['skipped_records'] += 1
                    continue

                internship = self.create_internship(item, company_name)
                if internship:
                    records.append(internship)
                else:
                    self.stats['skipped_records'] += 1

            logger.info("[%d valid records]", len(records))

        except json.JSONDecodeError as e:
            logger.error("[ERROR] %s.json: JSON parsing error - %s", company_name, e)
        except Exception as e:
            logger.error("[ERROR] %s.json: %s", company_name, e)

        return records

    def load_one(self, company_name: str) -> bool:
        """Загружает данные одной компании по имени."""
        file_path = self.transformed_dir / f"{company_name}.json"
        if not file_path.exists():
            logger.error("[ERROR] File %s not found", file_path)
            return False

        records = self.load_file(file_path)

        if not records:
            logger.warning("[WARN] No records to load for company %s", company_name)
            return True

        try:
            logger.info("Starting DB write for %s (%d records)", company_name, len(records))
            loaded_count = internships_db.write_batch(records)
            logger.info("Finished DB write for %s: %d/%d loaded", company_name, loaded_count, len(records))
            self.stats['loaded_records'] += loaded_count
            self.stats['companies'][company_name] = {
                'total': len(records),
                'loaded': loaded_count
            }
            self.stats['total_records'] += len(records)
            self.stats['total_files'] += 1
            return True
        except Exception as e:
            logger.error("[ERROR] Failed to write to database: %s", e)
            self.stats['companies'][company_name] = {
                'total': len(records),
                'loaded': 0
            }
            return False

    def load_all(self) -> bool:
        """Загружает все файлы из папки transformed"""
        if not self.transformed_dir.exists():
            logger.error("[ERROR] Directory %s not found", self.transformed_dir)
            return False

        json_files = sorted(self.transformed_dir.glob('*.json'))

        if not json_files:
            logger.error("[ERROR] No JSON files found in %s", self.transformed_dir)
            return False

        logger.info("[INFO] Found %d files to load", len(json_files))
        logger.info("")

        self.stats['total_files'] = len(json_files)

        all_success = True
        for file_path in json_files:
            company_name = file_path.stem

            if not self.load_one(company_name):
                all_success = False

        return all_success

    def print_summary(self):
        """Выводит статистику загрузки"""
        logger.info("")
        logger.info("=" * 70)
        logger.info("LOADING STATISTICS")
        logger.info("=" * 70)
        logger.info("")

        logger.info("By company:")
        logger.info("-" * 70)

        for company, stats in sorted(self.stats['companies'].items()):
            status = "[OK]" if stats['loaded'] == stats['total'] else "[!]"
            logger.info("  %s %s - loaded %d/%d", status, company.ljust(20), stats['loaded'], stats['total'])

        logger.info("")
        logger.info("-" * 70)
        logger.info("  Total files:            %d", self.stats['total_files'])
        logger.info("  Total records:          %d", self.stats['total_records'])
        logger.info("  Successfully loaded:    %d", self.stats['loaded_records'])
        logger.info("  Skipped:                %d", self.stats['skipped_records'])
        logger.info("  Errors:                 %d", self.stats['total_records'] - self.stats['loaded_records'])
        logger.info("")

        if (self.stats['total_records'] > 0
                and self.stats['loaded_records'] == self.stats['total_records']):
            logger.info("  SUCCESS: Loading completed successfully")
        else:
            logger.info("  WARNING: Loading completed with errors")

        logger.info("=" * 70)


def main():
    """Главная функция"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("Loading transformed internship data into database".center(70))
    logger.info("=" * 70)
    logger.info("")

    script_dir = Path(__file__).parent
    project_root = script_dir
    transformed_dir = project_root / "data" / "transformed"

    logger.info("[INFO] Start time: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    logger.info("[INFO] Source directory: %s", transformed_dir)
    logger.info("")

    loader = InternshipsLoader(transformed_dir)

    logger.info("[INFO] Starting data loading...")
    logger.info("")

    try:
        if len(sys.argv) > 1:
            company = sys.argv[1]
            logger.info("[INFO] Loading only company: %s", company)
            success = loader.load_one(company)
            loader.print_summary()

            if success:
                logger.info("")
                logger.info("[SUCCESS] Data successfully loaded into database!")
                return 0
            else:
                logger.info("")
                logger.error("[ERROR] Failed to load data")
                return 1
        else:
            success = loader.load_all()
            loader.print_summary()

            if success and loader.stats['loaded_records'] > 0:
                logger.info("")
                logger.info("[SUCCESS] All data loaded into database successfully!")
                return 0
            else:
                logger.info("")
                logger.error("[ERROR] Failed to load data")
                return 1

    except KeyboardInterrupt:
        logger.info("")
        logger.info("[INTERRUPTED] Loading interrupted by user")
        return 1
    except Exception as e:
        logger.info("")
        logger.error("[FATAL ERROR] Critical error: %s", e)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    logger.info("loader script started")
    sys.exit(main())
