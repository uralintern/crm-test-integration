from curl_cffi import requests
import bs4
import json

URL = 'https://kontur.ru/education/internship'

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

def init_internship_data() -> dict:
    return {
        'title': None,
        'desc': None,
        'link': URL
    }


def get_internships() -> list[dict]:
    response = requests.get('https://kontur.ru/education/internship', headers=headers, impersonate="firefox")
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    cards = soup.find_all('div', class_='internships-card')
    if not cards:
        raise ValueError('Divs not found')
    
    internships = []
    data = init_internship_data()

    for card in cards:
        card_text = card.get_text(separator=' ', strip=True)

        if 'Набор закрыт' in card_text:
            continue

        info = card.find('a', class_='internships-card-link')
        if not info:
            raise ValueError('Info not found')
        
        if info['href']:
            data['link'] = 'https://kontur.ru' + str(info['href'])

        title = info.find('span')
        if not title:
            raise ValueError('Title not found')
        data['title'] = title.get_text(separator=' ', strip=True)
        
        desc = info.find('p')
        if not desc:
            raise ValueError('Description not found')
        data['desc'] = desc.get_text(separator=' ', strip=True)

        internships.append(data)
        data = init_internship_data()
    
    return internships

def save_to_json(data: list[dict], filename: str) -> None:
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

data = get_internships()
save_to_json(data, 'data/parsed/kontur.json')
