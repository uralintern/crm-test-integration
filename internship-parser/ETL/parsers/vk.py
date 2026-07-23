from curl_cffi import requests
import json
import bs4
import logging

from ETL.logging_config import get_logger

logger = get_logger(__name__)

URL = 'https://internship.vk.company/internship'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Sec-GPC': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Priority': 'u=0, i',
}

def save_to_json(data: list[dict], filename: str) -> None:
    logger.info("Opening file for write: %s", filename)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger.info("File written successfully: %s", filename)

logger.info("Starting VK parser")

try:
    logger.info("Sending GET request to %s", URL)
    response = requests.get(URL, headers=headers)
    logger.info("Received response with status %s", response.status_code)
    logger.info("Parsing HTML response")
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    data = soup.find('script', id='__NEXT_DATA__')
    if not data:
        raise ValueError('Data not found')
    logger.info("Found __NEXT_DATA__ script tag")
    save_to_json(json.loads(data.text), 'data/parsed/vk.json')
    logger.info("VK parsing finished successfully")
except Exception as e:
    logger.error("[ERROR] Failed to parse VK internships: %s", e)
