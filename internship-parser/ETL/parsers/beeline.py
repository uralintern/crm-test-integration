from curl_cffi import requests
import json

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
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

response = requests.get('https://job.beeline.ru/api/v1/vacancies/', params=params, headers=headers)
internships = response.json()['results']
for data in internships:
    data['link'] = f'https://job.beeline.ru/vacancies/{data['id']}'
save_to_json(internships, 'data/parsed/beeline.json')