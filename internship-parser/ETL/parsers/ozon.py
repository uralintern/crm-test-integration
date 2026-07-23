from curl_cffi import requests
import json
import logging

from ETL.logging_config import get_logger

logger = get_logger(__name__)

cookies = {
    '__Secure-ETC': '3c937b3dda21e19d2f4b0571454e9207',
    'abt_data': '7.SYxO-RK-OHLvsDA-o5VcHSwjyHDu5w9EqJqG-2k6vZcU8r0WLLVfiQMOLWBaaR89VKWdHU0TapT68Zx1LccrDxwHOj6u5H1YoowTTj2h4r8bm9KYFmI5WiagYf4yE8NMZhxmjcNxtYp_U3S1SJm14NBUC-pdwLCrdMdFW5K604sP92hQuzF_ly7d7V6qnabqseouOgiNzmmoXU300tPjCwuJZRAD9-bLb-bXLbIAA_KE1tvg3RLxFgA_kL8jCrUil60hqhJkppFoNYIePq-g-jo01orwCThRwXX_wbKlt3lUJynjHSQwDXCOlpUWU2ED2X1tFOYdLaZg3Togz6vCPOywnpFRxQsWFVhZCTA8IM_PTcpFNtMvQgjpr6Tw3Yhajt6O8JqIkXn7DGiZyJNYY5VRkunIhInq2LfDPdKq74Xtt7d6FQOKKPhkTzm5NopFs3kedKSdpyg1ifgisbHHmDcPpZ64LEJi',
    'X-O3-INGRESSCOOKIE': '4b0c3d817982336019dcacafd396e84e^|6d74333020c47da12980f6062fb14d92',
    'TSDK_trackerSessionId': '11cfdb53-07c4-85ad-885a',
    'o3-fe-use-cookie': 'true',
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    'Content-Type': 'application/json',
    'X-O3-App-Name': 'ozon-tech-ui',
    'X-O3-App-Version': 'release/IWP-506',
    'Origin': 'https://ozon.tech',
    'Sec-GPC': '1',
    'Connection': 'keep-alive',
    'Referer': 'https://ozon.tech/vacancies/?levels=Intern',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
}

json_data = {
    'filters': {
        'levels': [
            'Intern',
        ],
    },
    'page': 1,
    'page_limit': 50,
}

def save_to_json(data: list[dict], filename: str) -> None:
    logger.info("Opening file for write: %s", filename)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger.info("File written successfully: %s", filename)

logger.info("Starting Ozon parser")

try:
    url = 'https://ozon.tech/p-api/ozon-tech/vacancy/list'
    logger.info("Sending POST request to %s", url)
    response = requests.post(url, cookies=cookies, headers=headers, json=json_data)
    logger.info("Received response with status %s", response.status_code)
    internships = response.json()['items']
    logger.info("Parsed %d internships from response", len(internships))
    for data in internships:
        data['link'] = f'https://ozon.tech/vacancies/{data['internal_uuid']}'
    save_to_json(internships, 'data/parsed/ozon.json')
    logger.info("Ozon parsing finished successfully")
except Exception as e:
    logger.error("[ERROR] Failed to parse Ozon internships: %s", e)
