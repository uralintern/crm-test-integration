from curl_cffi import requests
import bs4
import json


headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
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
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

response = requests.get('https://education.tbank.ru/start/', headers=headers)
soup = bs4.BeautifulSoup(response.text, 'html.parser')
data = soup.find('script', id='__TRAMVAI_STATE__')
if not data:
    raise ValueError('Data not found')


internships = []

contents = json.loads(data.text)['stores']['router']['currentRoute']['config']['content']['content'][5]['content']
for content in contents:
    for block in content['content']:
        version = block['version']
        if version == '6.1':
            for panel in block['properties']['panels']:
                status = panel['badges'][0]['title']['text']
                title = panel['title']['text']
                desc = panel['subtitle']['text']
                link = 'https://education.tbank.ru' + panel['slideLink']['onClick']['url']
                internships.append({
                    'status': status,
                    'title': title,
                    'desc': desc,
                    'link': link
                })
        elif version == '5.1':
            continue
        else:
            raise ValueError('Unknow version')

save_to_json(internships, 'data/parsed/t-bank.json')

