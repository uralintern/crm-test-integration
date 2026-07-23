"""Главный скрипт для трансформации данных всех компаний.

Может принимать необязательный аргумент — имя компании.
Если аргумент передан, трансформирует только одну компания.
Если не передан — трансформирует все компании.
"""
import logging
import sys
from pathlib import Path

from ETL.logging_config import get_logger

from ETL.transforms.yandex import YandexTransformer
from ETL.transforms.ozon import OzonTransformer
from ETL.transforms.alfabank import AlfaBankTransformer
from ETL.transforms.mts import MTSTransformer
from ETL.transforms.vk import VKTransformer
from ETL.transforms.beeline import BeelineTransformer
from ETL.transforms.kontur import KonturTransformer
from ETL.transforms.rostelekom import RostelekomTransformer
from ETL.transforms.tbank import TBankTransformer
from ETL.transforms.naumen import NaumenTransformer

logger = get_logger(__name__)


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
    "naumen": NaumenTransformer,
}


def run_one(company_name: str, parsed_dir: Path, transformed_dir: Path) -> bool:
    """Трансформирует данные одной компании.

    Returns:
        True при успехе, False при ошибке.
    """
    transformer_class = TRANSFORMERS.get(company_name)
    if transformer_class is None:
        logger.error("[ERROR] Unknown company: %s", company_name)
        return False

    input_file = parsed_dir / f"{company_name}.json"
    output_file = transformed_dir / f"{company_name}.json"

    if not input_file.exists():
        logger.error("[FAIL] File %s not found", input_file)
        return False

    transformer = transformer_class(company_name, input_file, output_file)
    try:
        transformer.run()
        return True
    except Exception as e:
        logger.error("[ERROR] Failed to transform %s: %s", company_name, e)
        return False


def run_all(parsed_dir: Path, transformed_dir: Path) -> tuple[int, int]:
    """Трансформирует данные всех компаний.

    Returns:
        (успешно, ошибок)
    """
    successful = 0
    failed = 0

    logger.info("=" * 60)
    logger.info("Starting data transformation for companies")
    logger.info("=" * 60)

    for company_name in TRANSFORMERS:
        if run_one(company_name, parsed_dir, transformed_dir):
            successful += 1
        else:
            failed += 1

    logger.info("=" * 60)
    logger.info("Results: %d successful, %d errors", successful, failed)
    logger.info("=" * 60)

    return successful, failed


def main():
    base_path = Path(__file__).parent.parent
    parsed_dir = base_path / "data" / "parsed"
    transformed_dir = base_path / "data" / "transformed"

    logger.info("Parser base path: %s", base_path)
    logger.info("Parsed data directory: %s", parsed_dir)
    logger.info("Transformed data directory: %s", transformed_dir)

    transformed_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Transformed directory ensured")

    if len(sys.argv) > 1:
        company = sys.argv[1]
        logger.info("Single company mode: %s", company)
        success = run_one(company, parsed_dir, transformed_dir)
        sys.exit(0 if success else 1)
    else:
        successful, failed = run_all(parsed_dir, transformed_dir)
        sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    logger.info("run_transformers script started")
    main()
