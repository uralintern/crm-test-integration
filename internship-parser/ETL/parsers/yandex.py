import requests
import bs4
import json
import logging

from ETL.logging_config import get_logger

logger = get_logger(__name__)


URL = 'https://yandex.ru/yaintern/internship'
COOKIES = {
    '_yasc': 'qMYIePrZfR16nZ5jnnqcfz9W5fOPKUbun1fBJFtw1NAe7fHQqEIcKEF6WbX4392TiVRYrPtj/yxQ',
    'bh': 'YOSMuNIGahfcyuH/CJLYobEDn8/14QzH4PGOA+CdAg==',
    'is_gdpr': '0',
    'is_gdpr_b': 'CNv0SxCJjwM=',
    'pi': 'QeXmsue/SaLyWYaeTOSWJmX6a7JSCq8+T5iGUg8edzHm7ghIHsdwyOwsBJ6Y47DBDQPY5B2y618aS57pgyNvMHG6Iok=',
    'i': 'NhBdkyGwBSq+G/ZcIPdQxv3gDghVrbJZTs7xq1AR+vSTRzu5WS0cW8MpdrlHCTiVUQAJ7cYtVyDx3eYruDgOY9cEEE8=',
    'yandexuid': '2309618601783492735',
    'yashr': '2318038141783492735',
    'yp': '1784097536.szm.1_25:1536x864:1536x731',
    'yuidss': '2309618601783492735',
    'ymex': '2098852737.yrts.1783492737',
    'gdpr': '0',
    '_ym_uid': '1783492737773119887',
    '_ym_d': '1783492737',
    '_ym_isad': '2',
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
    'Priority': 'u=0, i',
}


def get_parsed_data() -> dict:
    logger.info("Sending GET request to %s", URL)
    response = requests.get(URL, cookies=COOKIES, headers=HEADERS)
    logger.info("Received response with status %s", response.status_code)
    logger.info("Parsing HTML response")
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    section = soup.find('section', id='kastomnyj-html-page_internshiprujson')
    if not section:
        raise ValueError('Section not found')
    template = section.find('template')
    if not template:
        raise ValueError('Template not found')
    data = json.loads(template.get_text(strip=True))
    logger.info("Parsed JSON data from HTML template")
    return data

def save_to_json(data, filename: str) -> None:
    logger.info("Opening file for write: %s", filename)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger.info("File written successfully: %s", filename)


logger.info("Starting Yandex parser")

try:
    data = get_parsed_data()
    internships = []

    for direction in data['fields']['internships']['directions']:
        for cur_data in direction['list']:
            if cur_data.get('notFound') or cur_data.get('statusInvert') in (None, True):
                continue
            cur_data['title'] = direction['title']
            cur_data['slug'] = direction['slug']
            del cur_data['stripes']
            internships.append(cur_data)

    logger.info("Total internships collected: %d", len(internships))
    save_to_json(internships, 'data/parsed/yandex.json')
    logger.info("Yandex parsing finished successfully")
except Exception as e:
    logger.error("[ERROR] Failed to parse Yandex internships: %s", e)
