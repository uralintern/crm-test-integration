from curl_cffi import requests
import json


cookies = {
    'spjs': '1783542320312_0f5246d934cab733181cd233e601eca6_.HdthJGEOM9Bw7rpHHKoEoWZp6asa-bUQ0dnM8OPUscxdrs5-rGJQRqGAnXJggaT9NNLaKC1U.GNOxE8rLyczg',
    'spsc': '1783542320312_4bcc21312fc3a80ff60cc01556c54445_ux4GUPXCZyHjlxm8UvGZ0MZNL2VtaR.hPnZ.wuDcmgMZ',
    'spid': '1783542320312_1898fce7ee4c7459865df90a24fe1baa_kjxdni86ln6v562w',
    'site_city': '6ef9d855/kirov',
    'last_tags_of_interest': '',
    'Rl-nxSMiaMi085pi': '42f183b5-f4e1-472e-809a-e7edd7bfc89d',
    'lastVisitDate': '2026-07-08T20:34:04.207044290Z',
    'xpe': 'true',
    'platformId': 'alfasite',
    'youth-cookiePlateState': 'closed',
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0',
    'Accept': 'application/json',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    'Referer': 'https://alfabank.ru/alfafuture/ichoosealfa/vacancies/',
    'Sec-GPC': '1',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
}

def save_to_json(data: list[dict], filename: str) -> None:
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

response = requests.get(
    'https://alfabank.ru/api/v1/alfastudents-internships/internships?limit=100&offset=0&sort=updatedAt%3Aasc&type.eq=INTERNSHIP',
    cookies=cookies,
    headers=headers,
)
internships = response.json()['data']
for data in internships:
    data['link'] = f'https://alfabank.ru/alfafuture/ichoosealfa/vacancies/?rp-vacancy={data['uuid']}'

save_to_json(internships, 'data/parsed/alfabank.json')
