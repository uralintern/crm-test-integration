import requests
import bs4
import json
import unicodedata 
import logging

from ETL.logging_config import get_logger

logger = get_logger(__name__)


URL = 'https://first.rt.ru/'
COOKIES = {
    '__ddg8_': 'R8ByyeYYKMMH1gjO',
    '__ddg10_': '1783494266',
    '__ddg9_': '178.141.226.95',
    '__ddg1_': 'GuCqjAp57GWNlOWHfypi',
}
HEADERS = {
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
}

def get_tags_with_data() -> list[bs4.Tag]:
    logger.info("Sending GET request to %s", URL)
    response = requests.get(URL, cookies=COOKIES, headers=HEADERS)
    logger.info("Received response with status %s", response.status_code)
    logger.info("Parsing HTML response")
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    div = soup.find('div', id='rec2221735971')
    if not div:
        raise ValueError('Div not found')
    parsed_data = div.find_all('div', class_='t396__elem')
    if not parsed_data:
        raise ValueError('No data found in the div')
    logger.info("Found %d data elements", len(parsed_data))
    return parsed_data

def init_internship_data() -> dict:
    return {
        'title': None,
        'description': None,
        'link': URL
    }

def save_to_json(data: list[dict], filename: str) -> None:
    logger.info("Opening file for write: %s", filename)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger.info("File written successfully: %s", filename)

logger.info("Starting Rostelecom parser")

try:
    tags = get_tags_with_data()
    internships = []
    data = init_internship_data()

    for ind, cur_tag in enumerate(tags):
        order = ind % 4
        match order:
            case 1:
                data['description'] = unicodedata.normalize("NFKD", cur_tag.get_text(strip=True))
            case 2:
                data['title'] = unicodedata.normalize("NFKD", cur_tag.get_text(strip=True))
            case 3:
                internships.append(data)
                data = init_internship_data()

    logger.info("Total internships collected: %d", len(internships))
    save_to_json(internships, 'data/parsed/rostelekom.json')
    logger.info("Rostelecom parsing finished successfully")
except Exception as e:
    logger.error("[ERROR] Failed to parse Rostelecom internships: %s", e)
