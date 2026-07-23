from curl_cffi import requests
import json
import logging

from ETL.logging_config import get_logger

logger = get_logger(__name__)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0',
    'Accept': '*/*',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    'Referer': 'https://job.beeline.ru/vacancies?internship=true',
    'Sec-GPC': '1',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Priority': 'u=4',
}

params = {
    'is_intership': 'true',
}

def save_to_json(data: list[dict], filename: str) -> None:
    logger.info("Opening file for write: %s", filename)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger.info("File written successfully: %s", filename)

logger.info("Starting Beeline parser")

try:
    url = 'https://job.beeline.ru/api/v1/vacancies/'
    logger.info("Sending GET request to %s with params %s", url, params)
    response = requests.get(url, params=params, headers=headers)
    logger.info("Received response with status %s", response.status_code)
    internships = response.json()['results']
    logger.info("Parsed %d internships from response", len(internships))
    for data in internships:
        data['link'] = f"https://job.beeline.ru/vacancies/{data['id']}"
    save_to_json(internships, 'data/parsed/beeline.json')
    logger.info("Beeline parsing finished successfully")
except Exception as e:
    logger.error("[ERROR] Failed to parse Beeline internships: %s", e)
