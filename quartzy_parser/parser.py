"""Helper module to interact with the (unofficial) Quartzy API."""

import asyncio
import base64
import hashlib
import itertools
import json
import math
import secrets
from typing import Dict, List, Optional
from urllib.parse import unquote

from gazpacho.soup import Soup
from httpx import AsyncClient
from httpx_limiter import AsyncRateLimitedTransport, Rate
from httpx_limiter.aiolimiter import AiolimiterAsyncLimiter
from requests import Session

from .models import Attachment, Plasmid, User


async def login(username: str, password: str, c: AsyncClient):
    """Perform login to Quartzy."""
    c.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0",
            "Origin": "https://app.quartzy.com",
            "Referer": "https://app.quartzy.com/",
        }
    )

    logURL = "https://app.quartzy.com/login"
    r = await c.get(logURL)
    login_page_env = Soup(r.text).find("meta", {"name": "frontend/config/environment"}, mode="first")
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
        "state": base64.urlsafe_b64encode(("7Z1_EDU.r" + secrets.token_hex(17)).encode()).decode(),
        "nonce": base64.urlsafe_b64encode(("_" + secrets.token_hex(21)).encode()).decode(),
        "code_challenge": base64.urlsafe_b64encode(code_verifier_hash).rstrip(b"=").decode(),
        "code_challenge_method": "S256",
        "auth0Client": base64.urlsafe_b64encode(b'{"name":"auth0-spa-js","version":"2.1.3"}').decode(),
    }

    r = await c.get(authorize_URL, params=authorize_params)

    login_soup = Soup(r.text)

    if type(login_soup) is not Soup:
        raise RuntimeError("Couldn't get HTML response for OIDC / Authorize call")

    login_form = login_soup.find("form", {"class": "_form-login-id"}, mode="first")

    if login_form is None:
        raise RuntimeError("Couldn't locate log in form after redirect to Auth0")

    login_state = login_form.find("input", {"name": "state"}, mode="first").attrs["value"]

    base_URL = r.url

    username_URL = f"https://{base_URL.host}/u/login/identifier"
    username_form_data = {
        "state": login_state,
        "username": username,
        "js-available": "true",
        "webauthn-available": "true",
        "is-brave": "false",
        "webauthn-platform-available": "true",
    }
    r = await c.post(username_URL, data=username_form_data, params={"state": login_state})

    if r.status_code != 200:
        raise RuntimeError("failed to submit username to Auth0")

    password_URL = f"https://{base_URL.host}/u/login/password"

    password_form_data = {"state": login_state, "username": username, "password": password}

    r = await c.post(password_URL, data=password_form_data, params={"state": login_state})

    query_params = r.url.params

    auth_code = query_params["code"]
    _ = query_params["state"]

    if "code" not in query_params or "state" not in query_params:
        raise RuntimeError("could not find authorization code/state")

    token_URL = f"https://{base_URL.host}/oauth/token"

    token_form_data = {
        "client_id": login_env["APP"]["authClientId"],
        "code_verifier": code_verifier.decode(),
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": login_env["APP"]["authRedirect"],
    }

    r = await c.post(token_URL, data=token_form_data, params={"state": login_state})

    tokens = r.json()
    access_token = tokens["access_token"]
    token_type = tokens["token_type"]

    c.headers.update({"Auth0-Access-Token": access_token, "Authorization": f"{token_type} {access_token}"})


async def build_plasmid_details(plasmid, c: AsyncClient) -> Plasmid:
    """Given the top-level plasmid metadata, return the full plasmid."""
    data = plasmid["attributes"]
    r = await c.get(f'https://io.quartzy.com/items/{plasmid["id"]}/attachments')
    attachments_json = r.json()
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

    return Plasmid(
        pKG=pKG,
        uid="",
        filename="",
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
        owner_id=plasmid["relationships"]["owned_by"]["data"]["id"],
    )


async def get_plasmids(username: str, password: str, plasmid_limit: Optional[int] = None) -> List[Plasmid]:
    """Login to quartzy and return up to plasmid_limit plasmids."""
    # limit to N requests per second so we don't get rate limited or blocked.
    limiter = AiolimiterAsyncLimiter.create(Rate.create(magnitude=15))

    async with AsyncClient(
        transport=AsyncRateLimitedTransport.create(limiter=limiter), http2=True, follow_redirects=True
    ) as c:
        await login(username, password, c)

        # Dump plasmids. Start by fetching the first page so we know what the last page is
        responses = []
        response = await c.get(
            "https://io.quartzy.com/groups/190392/items",
            params={"page": 1, "limit": "100", "sort": "-name"},
        )
        responses.append(response.json())
        end_page = int(responses[0]["meta"]["pagination"]["page"]["last"])
        # adjust end page down if we have a plasmid limit
        if plasmid_limit is not None:
            end_page = min(end_page, math.ceil(plasmid_limit / 100))

        tasks = [
            c.get(
                "https://io.quartzy.com/groups/190392/items",
                params={"page": i, "limit": "100", "sort": "-name"},
            )
            for i in range(2, end_page + 1)
        ]
        raw_responses = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [r for r in raw_responses if isinstance(r, BaseException)]
        for error in errors:
            print(f"[FAIL] fetching plasmid pages {str(error)}")
        responses.extend([r.json() for r in raw_responses if not isinstance(r, BaseException)])

        # post-process responses by merging the data
        plasmid_data = list(itertools.chain.from_iterable([response["data"] for response in responses]))
        print(f"Loaded {len(plasmid_data)} plasmids. Fetching metadata.")

        if plasmid_limit is not None:
            plasmid_data = plasmid_data[:plasmid_limit]

        build_plasmid_tasks = [build_plasmid_details(p, c) for p in plasmid_data]
        raw_plasmids = await asyncio.gather(*build_plasmid_tasks, return_exceptions=True)
        errors = [p for p in raw_plasmids if isinstance(p, BaseException)]
        for error in errors:
            print(f"[FAIL] fetching plasmid details {str(error)}")

        plasmids = [p for p in raw_plasmids if not isinstance(p, BaseException)]
        print(f"Loaded attachment metadata for {len(plasmids)} plasmids")

        # fixup uid's
        pKG_count_map: Dict[int, int] = {}
        for plasmid in plasmids:
            pKG = plasmid.pKG
            if pKG not in pKG_count_map:
                pKG_count_map[pKG] = 1
                plasmid.filename = f"pKG{pKG:05d}.rst"
                plasmid.uid = f"pKG{pKG:05d}"
            else:
                plasmid.filename = f"pKG{pKG:05d}_dup{pKG_count_map[pKG]}.rst"
                plasmid.uid = f"pKG{pKG:05d}_dup{pKG_count_map[pKG]}"
                pKG_count_map[pKG] += 1

    return plasmids


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
