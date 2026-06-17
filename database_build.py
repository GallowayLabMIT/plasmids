"""Using Quartzy information, update and build an equivalent sqlite3 database."""

import argparse
import asyncio
import json
import os
import sqlite3
from pathlib import Path
from typing import List

import webdav3
import webdav3.client
from pydantic import RootModel

import quartzy_parser.db as db
from quartzy_parser import Plasmid, get_plasmids, maps
from quartzy_parser.linter import lint_plasmids

parser = argparse.ArgumentParser(description="Generates an sqlite3 database from plasmid details")
parser.add_argument("--webdav", action="store_true", help="Use WebDAV to cache database files")
parser.add_argument(
    "--plasmid-limit", type=int, default=None, help="Number of plasmids to fetch from Quartzy"
)


if __name__ == "__main__":
    args = parser.parse_args()
    base = Path(__file__).resolve().parent

    if Path(base / "credentials.json").is_file():
        with open("credentials.json") as cred_file:
            credentials = json.load(cred_file)
    else:
        credentials = {}

    if "QUARTZY_USERNAME" in os.environ and "QUARTZY_PASSWORD" in os.environ:
        credentials["quartzy_username"] = os.environ["QUARTZY_USERNAME"]
        credentials["quartzy_password"] = os.environ["QUARTZY_PASSWORD"]

    if "WEBDAV_URL" in os.environ and "WEBDAV_USER" in os.environ and "WEBDAV_PASSWORD" in os.environ:
        credentials["webdav_url"] = os.environ["WEBDAV_URL"]
        credentials["webdav_user"] = os.environ["WEBDAV_USER"]
        credentials["webdav_password"] = os.environ["WEBDAV_PASSWORD"]

    if "quartzy_username" not in credentials or "quartzy_password" not in credentials:
        raise ValueError("Cannot find Quartzy login credentials!")

    if args.webdav and (
        "webdav_url" not in credentials
        or "webdav_user" not in credentials
        or "webdav_password" not in credentials
    ):
        raise ValueError("Cannot find Webdav credentials!")

    Path("cache").mkdir(parents=True, exist_ok=True)

    # Download the cached database, if it exists and matches the current version
    db_path = Path("cache/features.db")

    if args.webdav:
        webdav_options = {
            "webdav_hostname": credentials["webdav_url"],
            "webdav_login": credentials["webdav_user"],
            "webdav_password": credentials["webdav_password"],
            "webdav_timeout": 5,
        }
        cache_client = webdav3.client.Client(webdav_options)
        try:
            print("Downloading database")
            cache_client.download_sync(remote_path="plasmids.db", local_path=db_path)
        except webdav3.exceptions.WebDavException as e:
            print(f"Failed to download. Error: {str(e)}")
            pass
    # remove an old database if present
    if db_path.exists() and not db.check_schema_version(db_path):
        print("Schema version mismatch! Removing database", flush=True)
        db_path.unlink()

    if not db_path.exists():
        with sqlite3.connect(db_path, autocommit=False) as con:
            db.create_database(con)

    # process plasmids one by one, dumping features as needed.
    cached_plasmids = Path("cache/plasmid_details.json")
    if cached_plasmids.exists():
        raw_plasmids = json.loads(cached_plasmids.read_text())
        plasmids = [Plasmid(**p) for p in raw_plasmids]
    else:
        plasmids = asyncio.run(
            get_plasmids(
                credentials["quartzy_username"],
                credentials["quartzy_password"],
                plasmid_limit=args.plasmid_limit,
            )
        )
        if args.plasmid_limit is not None:
            plasmids = plasmids[: (args.plasmid_limit)]

        lint_plasmids(plasmids)
        cached_plasmids.write_text(RootModel[List[Plasmid]](plasmids).model_dump_json(indent=2))

    # Reopen connection for real now
    with sqlite3.connect(db_path, autocommit=False) as con:
        con.execute("PRAGMA foreign_keys = 1")
        cursor = con.cursor()

        # set all plasmids as not present, so we can remove them if they got deleted
        con.execute("UPDATE plasmids SET present = 0")
        con.commit()

        map_update_list: List[Plasmid] = []
        print(f"Processing {len(plasmids)} plasmids into the database", flush=True)
        for plasmid in plasmids:
            needs_map_update = db.write_plasmid(con, plasmid)

            if needs_map_update:
                map_update_list.append(plasmid)

        # filter map_update_list if they don't have an attachment field
        map_update_list = [p for p in map_update_list if len(p.attachments) > 0]
        if len(map_update_list) > 0:
            print(f"{len(map_update_list)} plasmids need map updates. Performing async", flush=True)
            # fetch all feature updates async
            updates = asyncio.run(maps.fetch_features(map_update_list))

            print("Features fetched! Writing to database", flush=True)
            for uid, features in updates.items():
                db.write_features(con, uid, features)
        else:
            print(f"{len(map_update_list)} plasmids need map updates!", flush=True)

        # now delete all plasmids that are no longer present
        con.execute("DELETE FROM plasmids WHERE present = 0")

        # purge sequences and translations that are no longer present
        con.execute(
            "DELETE FROM sequences "
            + "WHERE id IN "
            + "(SELECT sequences.id FROM sequences "
            + " LEFT JOIN features ON sequences.id=features.sequence "
            + " WHERE features.sequence IS NULL)"
        )
        con.execute(
            "DELETE FROM translations "
            + "WHERE id IN "
            + "(SELECT translations.id FROM translations "
            + " LEFT JOIN features ON translations.id=features.translation "
            + " WHERE features.translation IS NULL)"
        )
        con.commit()

    # reupload the processed file
    if args.webdav:
        webdav_options = {
            "webdav_hostname": credentials["webdav_url"],
            "webdav_login": credentials["webdav_user"],
            "webdav_password": credentials["webdav_password"],
            "webdav_timeout": 5,
        }
        cache_client = webdav3.client.Client(webdav_options)
        try:
            print("Uploading database")
            cache_client.upload_sync(local_path=db_path, remote_path="plasmids.db")
        except webdav3.exceptions.WebDavException as e:
            print(f"Upload failure: {str(e)}")
            pass
