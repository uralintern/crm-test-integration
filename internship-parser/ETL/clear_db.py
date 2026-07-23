"""Очищает таблицу стажировок в БД перед запуском ETL."""
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.internships_db import internships_db


def clear_json_dirs():
    base = Path(__file__).parent / "data"
    dirs = ["parsed", "transformed"]
    total = 0
    for d in dirs:
        target = base / d
        if not target.exists():
            continue
        for f in target.glob("*.json"):
            try:
                f.unlink()
                total += 1
            except Exception as e:
                print(f"[ERROR] Не удалось удалить {f}: {e}")
    print(f"[OK] Удалено {total} JSON файлов из data/parsed и data/transformed")


def main():
    print("=" * 60)
    print("Очистка БД перед ETL")
    print("=" * 60)

    db_ok = False
    try:
        count = internships_db.clear()
        print(f"[OK] Удалено {count} записей из таблицы стажировок")
        db_ok = True
    except Exception as e:
        print(f"[ERROR] Ошибка при очистке БД: {e}")
        return 1

    if db_ok:
        clear_json_dirs()

    print("=" * 60)
    print("БД очищена успешно")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())