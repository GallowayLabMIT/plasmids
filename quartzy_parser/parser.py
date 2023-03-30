from typing import List, Optional, Dict
from requests import Session
from urllib.parse import unquote, quote
from gazpacho.soup import Soup
from time import sleep
import json

from .models import Plasmid, User

def get_plasmids(username: str, password: str, plasmid_limit: Optional[int]=None) -> List[Plasmid]:
    result: List[Plasmid] = []
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

        pKG_count_map: Dict[int,int] = {}

        # Dump plasmids
        page = 1
        end_page = 1e10
        while page < end_page:
            if plasmid_limit is not None and len(result) > plasmid_limit:
                break
            sleep(0.1) # Sleep to prevent getting rate-limited
            response = s.get('https://io.quartzy.com/groups/190392/items', params={
                'page': page,
                'limit': '100',
                'sort': '-name'}).json()
            end_page = int(response['meta']['pagination']['page']['last'])
            page = page + 1
            for elem in response['data']:
                data = elem['attributes']
                attachments_json = s.get(f'https://io.quartzy.com/items/{elem["id"]}/attachments').json()
                sleep(0.05)
                attachments: List[str] = [a['attributes']['file_name'] for a in attachments_json['data'] if a['type'] == 'attachment']

                # Dump pKG and compute filename
                pKG = int(data['custom_fields']['pKG#'])
                if pKG not in pKG_count_map:
                    pKG_count_map[pKG] = 1
                    filename = f'pKG{pKG:05d}.rst'
                else:
                    filename = f'pKG{pKG:05d}_dup{pKG_count_map[pKG]}.rst'
                    pKG_count_map[pKG] += 1

                result.append(Plasmid(
                    pKG=pKG,
                    filename=filename,
                    q_item_name=data['name'],
                    name=data['custom_fields']['Plasmid'],
                    species=data['custom_fields']['Species'],
                    resistances=data['custom_fields']['Resistance markers'],
                    plasmid_type=data['custom_fields']['Plasmid type'],
                    date_stored=data['custom_fields']['Date stored'],
                    technical_details=data['technical_details'].split(';') if data['technical_details'] is not None else [],
                    attachment_filenames=attachments,
                    vendor=data['vendor_name'],
                    alt_name=data['catalog_number'] if data['catalog_number'] is not None else '',
                    owner_id=elem['relationships']['owned_by']['data']['id']))
                #print('.', end='', flush=True)
        print('plasmids done!')
    return result

def get_users(username: str, password: str) -> List[User]:
    result: List[User] = []

    # Start session, copied from get_plasmids
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

        # Dump users
        response = s.get('https://io.quartzy.com/users?filter[has_items]=1&filter[group]=190392').json()
        for elem in response['data']:
            data = elem['attributes']
            result.append(User(
                id=elem['id'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                full_name=data['full_name']))
            #print('.', end='', flush=True)
        print('users done!')
    return result
