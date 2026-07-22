"""Очищает таблицу стажировок в БД перед запуском ETL."""
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.internships_db import internships_db


def main():
    print("=" * 60)
    print("Очистка БД перед ETL")
    print("=" * 60)

    try:
        count = internships_db.clear()
        print(f"[OK] Удалено {count} записей из таблицы стажировок")
    except Exception as e:
        print(f"[ERROR] Ошибка при очистке БД: {e}")
        return 1

    print("=" * 60)
    print("БД очищена успешно")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())