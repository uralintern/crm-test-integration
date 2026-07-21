"""Главный скрипт для трансформации данных всех компаний"""
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


def main():
    """Запускает трансформацию данных всех компаний"""
    base_path = Path(__file__).parent.parent
    parsed_dir = base_path / "data" / "parsed"
    transformed_dir = base_path / "data" / "transformed"
    
    # Создаем директорию для трансформированных данных
    transformed_dir.mkdir(parents=True, exist_ok=True)
    
    # Список всех трансформаторов
    transformers = [
        ("yandex", YandexTransformer),
        ("ozon", OzonTransformer),
        ("alfabank", AlfaBankTransformer),
        ("mts", MTSTransformer),
        ("vk", VKTransformer),
        ("beeline", BeelineTransformer),
        ("kontur", KonturTransformer),
        ("rostelekom", RostelekomTransformer),
        ("t-bank", TBankTransformer),
    ]
    
    print("=" * 60)
    print("Запуск трансформации данных компаний")
    print("=" * 60)
    
    successful = 0
    failed = 0
    
    for company_name, transformer_class in transformers:
        input_file = parsed_dir / f"{company_name}.json"
        output_file = transformed_dir / f"{company_name}.json"
        
        if not input_file.exists():
            print(f"[FAIL] Файл {input_file} не найден")
            failed += 1
            continue
        
        transformer = transformer_class(company_name, input_file, output_file)
        try:
            transformer.run()
            successful += 1
        except Exception as e:
            print(f"[ERROR] Ошибка при трансформации {company_name}: {e}")
            failed += 1
    
    print("=" * 60)
    print(f"Результаты: {successful} успешно, {failed} ошибок")
    print("=" * 60)


if __name__ == "__main__":
    main()
