from curl_cffi import requests
import json
import logging

from ETL.logging_config import get_logger

logger = get_logger(__name__)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0',
    'Accept': '*/*',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    'Referer': 'https://job.mts.ru/programs/start',
    'Sec-GPC': '1',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Priority': 'u=0',
}

def save_to_json(data: list[dict], filename: str) -> None:
    logger.info("Opening file for write: %s", filename)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger.info("File written successfully: %s", filename)

logger.info("Starting MTS parser")

try:
    url = 'https://job.mts.ru/api/v2/catalog/v1/vacancies?professionalRole=v-60377545291333713,it-60376693377859705,v-295882384589619276,v-295882384589602892,v-534648392060502141,v-60378626381578361,v-60378652839247957,v-60378676868415604,backend-295882384589455436,frontend-295882384589471820,ml-295882384589504588,mobile-295882384589488204,v-295882384589520972,v-295882384589537356,v-60377929682518099,v-60377900922175580&isInternship=true&limit=100&offset=0'
    logger.info("Sending GET request to MTS API")
    response = requests.get(url, headers=headers)
    logger.info("Received response with status %s", response.status_code)
    save_to_json(response.json()['data'], 'data/parsed/mts.json')
    logger.info("MTS parsing finished successfully")
except Exception as e:
    logger.error("[ERROR] Failed to parse MTS internships: %s", e)
