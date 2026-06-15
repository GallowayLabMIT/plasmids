"""Helper module to interact with the (unofficial) Quartzy API."""

import base64
import hashlib
import json
import secrets
from time import sleep
from typing import Dict, List, Optional
from urllib.parse import unquote, urlparse

from gazpacho.soup import Soup
from requests import Session

from .models import Attachment, Plasmid, User


def login(username: str, password: str, s: Session):
    """Perform login to Quartzy."""
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0",
            "Origin": "https://app.quartzy.com",
            "Referer": "https://app.quartzy.com/",
        }
    )

    logURL = "https://app.quartzy.com/login"
    login_page_env = Soup(s.get(logURL).text).find(
        "meta", {"name": "frontend/config/environment"}, mode="first"
    )
    if type(login_page_env) is not Soup or login_page_env.attrs is None:
        raise RuntimeError("Couldn't load Quartzy environment!")
    login_env = json.loads(unquote(login_page_env.attrs["content"]))

    code_verifier = secrets.token_hex(64).encode()
    code_verifier_hash = hashlib.sha256(code_verifier).digest()

    authorize_URL = f'https://{login_env["APP"]["authTenant"]}/authorize'
    authorize_params = {
        "client_id": login_env["APP"]["authClientId"],
        "scope": "openid email profile",
        "redirect_uri": login_env["APP"]["authRedirect"],
        "audience": login_env["APP"]["authAudience"],
        "screen_hint": "login",
        "response_type": "code",
        "response_mode": "query",
        "state": base64.urlsafe_b64encode(("7Z1_EDU.r" + secrets.token_hex(17)).encode()),
        "nonce": base64.urlsafe_b64encode(("_" + secrets.token_hex(21)).encode()),
        "code_challenge": base64.urlsafe_b64encode(code_verifier_hash).rstrip(b"="),
        "code_challenge_method": "S256",
        "auth0Client": base64.urlsafe_b64encode(b'{"name":"auth0-spa-js","version":"2.1.3"}'),
    }

    r = s.get(authorize_URL, params=authorize_params)

    login_soup = Soup(r.text)

    if type(login_soup) is not Soup:
        raise RuntimeError("Couldn't get HTML response for OIDC / Authorize call")

    login_form = login_soup.find("form", {"class": "_form-login-id"}, mode="first")

    if login_form is None:
        raise RuntimeError("Couldn't locate log in form after redirect to Auth0")

    login_state = login_form.find("input", {"name": "state"}, mode="first").attrs["value"]

    base_URL = urlparse(r.url)
    username_URL = f"https://{base_URL.hostname}/u/login/identifier"
    username_form_data = {
        "state": login_state,
        "username": username,
        "js-available": "true",
        "webauthn-available": "true",
        "is-brave": "false",
        "webauthn-platform-available": "true",
    }
    r = s.post(username_URL, data=username_form_data, params={"state": login_state})

    if r.status_code != 200:
        raise RuntimeError("failed to submit username to Auth0")

    password_URL = f"https://{base_URL.hostname}/u/login/password"

    password_form_data = {"state": login_state, "username": username, "password": password}

    r = s.post(password_URL, data=password_form_data, params={"state": login_state})

    parsed = urlparse(r.url)
    query = parsed.query

    parts = query.split("&")

    query_params = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            query_params[k] = v

    auth_code = query_params["code"]
    _ = query_params["state"]

    if "code" not in query_params or "state" not in query_params:
        raise RuntimeError("could not find authroization code/state")

    token_URL = f"https://{base_URL.hostname}/oauth/token"

    token_form_data = {
        "client_id": login_env["APP"]["authClientId"],
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": login_env["APP"]["authRedirect"],
    }

    r = s.post(token_URL, data=token_form_data, params={"state": login_state})

    tokens = r.json()
    access_token = tokens["access_token"]
    token_type = tokens["token_type"]

    s.headers.update({"Auth0-Access-Token": access_token, "Authorization": f"{token_type} {access_token}"})


def get_plasmids(username: str, password: str, plasmid_limit: Optional[int] = None) -> List[Plasmid]:
    """Login to quartzy and return up to plasmid_limit plasmids."""
    result: List[Plasmid] = []

    with Session() as s:
        login(username, password, s)

        pKG_count_map: Dict[int, int] = {}

        # Dump plasmids
        page = 1
        end_page = 1e10
        while page < end_page:
            if plasmid_limit is not None and len(result) > plasmid_limit:
                break
            sleep(0.05)  # Sleep to prevent getting rate-limited
            response = s.get(
                "https://io.quartzy.com/groups/190392/items",
                params={"page": page, "limit": "100", "sort": "-name"},
            ).json()
            end_page = int(response["meta"]["pagination"]["page"]["last"])
            page = page + 1
            for elem in response["data"]:
                data = elem["attributes"]
                attachments_json = s.get(f'https://io.quartzy.com/items/{elem["id"]}/attachments').json()
                sleep(0.05)
                attachments: List[Attachment] = [
                    Attachment(
                        uuid=a["attributes"]["uuid"],
                        file_name=a["attributes"]["file_name"],
                        url=a["attributes"]["url"],
                    )
                    for a in attachments_json["data"]
                    if a["type"] == "attachment"
                ]

                # Dump pKG and compute filename
                pKG = int(data["custom_fields"]["pKG#"])
                if pKG not in pKG_count_map:
                    pKG_count_map[pKG] = 1
                    filename = f"pKG{pKG:05d}.rst"
                    uid = f"pKG{pKG:05d}"
                else:
                    filename = f"pKG{pKG:05d}_dup{pKG_count_map[pKG]}.rst"
                    uid = f"pKG{pKG:05d}_dup{pKG_count_map[pKG]}"
                    pKG_count_map[pKG] += 1

                result.append(
                    Plasmid(
                        pKG=pKG,
                        uid=uid,
                        filename=filename,
                        q_item_name=data["name"],
                        name=data["custom_fields"]["Plasmid"],
                        species=data["custom_fields"]["Species"],
                        resistances=data["custom_fields"]["Resistance markers"],
                        plasmid_type=data["custom_fields"]["Plasmid type"],
                        date_stored=data["custom_fields"]["Date stored"],
                        attachments=attachments,
                        technical_details=data["technical_details"].split(";")
                        if data["technical_details"] is not None
                        else [],
                        vendor=data["vendor_name"],
                        alt_name=data["catalog_number"] if data["catalog_number"] is not None else "",
                        owner_id=elem["relationships"]["owned_by"]["data"]["id"],
                    )
                )
        print("plasmids done!")
    return result


def get_users(username: str, password: str) -> List[User]:
    """Login to Quartzy and return a list of lab user profiles."""
    result: List[User] = []

    # Start session, copied from get_plasmids
    with Session() as s:
        login(username, password, s)

        # Dump users
        response = s.get("https://io.quartzy.com/users?filter[has_items]=1&filter[group]=190392").json()
        for elem in response["data"]:
            data = elem["attributes"]
            result.append(
                User(
                    id=elem["id"],
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    full_name=data["full_name"],
                )
            )
        print("users done!")
    return result
