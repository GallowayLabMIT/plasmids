from typing import List
from requests import Session
from urllib.parse import unquote, quote
from gazpacho.soup import Soup
from time import sleep
import json

from .models import Plasmid

def get_plasmids(username: str, password: str) -> List[Plasmid]:
    result = []
    with Session() as s:
        s.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0',
            'Origin': 'https://app.quartzy.com',
            'Referer': 'https://app.quartzy.com/'
        })
        # Request the login page to get the client ID.
        login_page_env = Soup(s.get('https://app.quartzy.com/login').text).find('meta', {'name': 'frontend/config/environment'}, mode='first')
        if type(login_page_env) is not Soup or login_page_env.attrs is None:
            raise RuntimeError("Couldn't load Quartzy environment!")
        login_env = json.loads(unquote(login_page_env.attrs['content']))
        response = s.post('https://io.quartzy.com/oauth/tokens',
            data=f'grant_type=password&client_id={login_env["api"]["clientId"]}&username={quote(username)}&password={password.replace(" ", "%20")}',
            headers={'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}).json()
        auth_header = f"{response['token_type']} {response['access_token']}"
        s.headers.update({'Authorization': auth_header})

        # Dump plasmids
        page = 1
        end_page = 1e10
        while page < end_page:
            sleep(0.1) # Sleep to prevent getting rate-limited
            response = s.get('https://io.quartzy.com/groups/190392/items', params={
                'page': page,
                'limit': '100',
                'sort': '-name'}).json()
            end_page = int(response['meta']['pagination']['page']['last'])
            page = page + 1
            for elem in response['data']:
                data = elem['attributes']
                result.append(Plasmid(
                    pKG=int(data['custom_fields']['pKG#']),
                    name=data['custom_fields']['Plasmid'],
                    species=data['custom_fields']['Species'],
                    resistances=data['custom_fields']['Resistance markers'],
                    plasmid_type=data['custom_fields']['Plasmid type'],
                    date_stored=data['custom_fields']['Date stored'],
                    alt_name=data['catalog_number'] if data['catalog_number'] is not None else ''))
    return result