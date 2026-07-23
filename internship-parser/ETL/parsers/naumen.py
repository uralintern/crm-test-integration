from curl_cffi import requests
import bs4
import json


URL = 'https://www.naumen.ru/career/trainee/'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Sec-GPC': '1',
    'Connection': 'keep-alive',
    'Cookie': '__ddg1_=BLHN1eRpUBXnaQi6LqWq; __ddg8_=u54ZArosJngwoiqR; __ddg10_=1784789997; __ddg9_=178.141.225.161; PHPSESSID=cCQ1iunqz4mxsnulIzeXrwoP0wcXXASy',
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


response = requests.get(URL, headers=HEADERS)
response.raise_for_status()
soup = bs4.BeautifulSoup(response.text, 'html.parser')

internships = []

tabs = soup.find_all('div', class_='career-task-wrap')
if not tabs:
    raise ValueError('Career task wraps not found')

for tab in tabs:
    tab_id = tab.get('id', '')

    city_name = None
    tab_link = soup.find('span', class_='career-menu-tab', attrs={'data-career-tab': tab_id})
    if tab_link:
        city_name = tab_link.get_text(separator=' ', strip=True)

    if not city_name:
        continue

    cards = tab.find_all('div', class_='trainee-t-title')
    if not cards:
        continue

    for card in cards:
        title = card.get_text(separator=' ', strip=True)
        if not title:
            continue

        parent = card.find_parent('div', class_=lambda x: x and 'col-' in x)
        if not parent:
            continue

        status_el = parent.find('div', class_='trainee-close')
        if status_el:
            status_text = status_el.get_text(separator=' ', strip=True)
            if 'Набор закрыт' in status_text:
                continue

        internships.append({
            'status': 'Набор открыт',
            'title': title,
            'city': city_name,
            'link': URL,
        })

save_to_json(internships, 'data/parsed/naumen.json')
