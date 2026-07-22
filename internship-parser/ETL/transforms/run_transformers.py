"""Главный скрипт для трансформации данных всех компаний.

Может принимать необязательный аргумент — имя компании.
Если аргумент передан, трансформирует только одну компанию.
Если не передан — трансформирует все компании.
"""
import sys
from pathlib import Path

from ETL.transforms.yandex import YandexTransformer
from ETL.transforms.ozon import OzonTransformer
from ETL.transforms.alfabank import AlfaBankTransformer
from ETL.transforms.mts import MTSTransformer
from ETL.transforms.vk import VKTransformer
from ETL.transforms.beeline import BeelineTransformer
from ETL.transforms.kontur import KonturTransformer
from ETL.transforms.rostelekom import RostelekomTransformer
from ETL.transforms.tbank import TBankTransformer


# Маппинг: имя компании -> класс трансформатора
TRANSFORMERS: dict[str, type] = {
    "yandex": YandexTransformer,
    "ozon": OzonTransformer,
    "alfabank": AlfaBankTransformer,
    "mts": MTSTransformer,
    "vk": VKTransformer,
    "beeline": BeelineTransformer,
    "kontur": KonturTransformer,
    "rostelekom": RostelekomTransformer,
    "t-bank": TBankTransformer,
}


def run_one(company_name: str, parsed_dir: Path, transformed_dir: Path) -> bool:
    """Трансформирует данные одной компании.

    Returns:
        True при успехе, False при ошибке.
    """
    transformer_class = TRANSFORMERS.get(company_name)
    if transformer_class is None:
        print(f"[ERROR] Неизвестная компания: {company_name}")
        return False

    input_file = parsed_dir / f"{company_name}.json"
    output_file = transformed_dir / f"{company_name}.json"

    if not input_file.exists():
        print(f"[FAIL] Файл {input_file} не найден")
        return False

    transformer = transformer_class(company_name, input_file, output_file)
    try:
        transformer.run()
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка при трансформации {company_name}: {e}")
        return False


def run_all(parsed_dir: Path, transformed_dir: Path) -> tuple[int, int]:
    """Трансформирует данные всех компаний.

    Returns:
        (успешно, ошибок)
    """
    successful = 0
    failed = 0

    print("=" * 60)
    print("Запуск трансформации данных компаний")
    print("=" * 60)

    for company_name in TRANSFORMERS:
        if run_one(company_name, parsed_dir, transformed_dir):
            successful += 1
        else:
            failed += 1

    print("=" * 60)
    print(f"Результаты: {successful} успешно, {failed} ошибок")
    print("=" * 60)

    return successful, failed


def main():
    base_path = Path(__file__).parent.parent
    parsed_dir = base_path / "data" / "parsed"
    transformed_dir = base_path / "data" / "transformed"

    # Создаём директорию для трансформированных данных
    transformed_dir.mkdir(parents=True, exist_ok=True)

    # Если передан аргумент — обрабатываем только одну компанию
    if len(sys.argv) > 1:
        company = sys.argv[1]
        success = run_one(company, parsed_dir, transformed_dir)
        sys.exit(0 if success else 1)
    else:
        successful, failed = run_all(parsed_dir, transformed_dir)
        sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()