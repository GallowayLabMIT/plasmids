"""Using Quartzy information, update and build an equivalent sqlite3 database."""

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import List

import webdav3.client
from pydantic import RootModel

import quartzy_parser.db as db
from quartzy_parser import Plasmid, get_plasmids, maps

parser = argparse.ArgumentParser(description="Generates an sqlite3 database from plasmid details")
parser.add_argument("--webdav", action="store_true", help="Use WebDAV to ")


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
        "webdav_hostname" not in credentials
        or "webdav_user" not in credentials
        or "webdav_password" not in credentials
    ):
        raise ValueError("Cannot find Webdav credentials!")

    webdav_options = {
        "webdav_hostname": credentials["webdav_url"],
        "webdav_login": credentials["webdav_user"],
        "webdav_password": credentials["webdav_password"],
    }

    Path("cache").mkdir(parents=True, exist_ok=True)

    # Download the cached database, if it exists and matches the current version
    db_path = Path("cache/features.db")

    if args.webdav:
        cache_client = webdav3.client.Client(webdav_options)
        try:
            cache_client.download_sync(remote_path="plasmids.db", local_path=db_path)
        except webdav3.client.WebDavException:
            pass
    # remove an old database if present
    if db_path.exists() and not db.check_schema_version(db_path):
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
        plasmids = get_plasmids(
            credentials["quartzy_username"], credentials["quartzy_password"], plasmid_limit=10
        )
        cached_plasmids.write_text(RootModel[List[Plasmid]](plasmids).model_dump_json(indent=2))

    # Reopen connection for real now
    with sqlite3.connect(db_path, autocommit=False) as con:
        con.execute("PRAGMA foreign_keys = 1")
        cursor = con.cursor()

        # set all plasmids as not present, so we can remove them if they got deleted
        con.execute("UPDATE plasmids SET present = 0")
        con.commit()

        for plasmid in plasmids:
            needs_map_update = db.write_plasmid(con, plasmid)

            if needs_map_update:
                map_filename = maps.cache_plasmid(plasmid, Path("./cache"))
                if map_filename is not None:
                    features = maps.extract_features(map_filename)
                    db.write_features(con, plasmid.uid, features)

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
