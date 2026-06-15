import argparse
import shutil
import os
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
import textwrap
import itertools
from pydantic import RootModel

from typing import List, Dict, Tuple, Optional

from quartzy_parser import get_plasmids, Plasmid, lint_plasmids, maps
import quartzy_parser.db as db
parser = argparse.ArgumentParser(description="Generates an sqlite3 database from plasmid details")


if __name__ == '__main__':
    args = parser.parse_args()
    base = Path(__file__).resolve().parent

    if Path(base / 'credentials.json').is_file():
        with open('credentials.json') as cred_file:
            credentials = json.load(cred_file)
    elif 'QUARTZY_USERNAME' in os.environ and 'QUARTZY_PASSWORD' in os.environ:
        credentials = {
            'username': os.environ['QUARTZY_USERNAME'],
            'password': os.environ['QUARTZY_PASSWORD']
        }
    else:
        raise ValueError("Cannot find credentials!")

    Path("cache").mkdir(parents=True, exist_ok=True)
    cached_plasmids = Path("cache/plasmid_details.json")
    if cached_plasmids.exists():
        raw_plasmids = json.loads(cached_plasmids.read_text())
        plasmids = [Plasmid(**p) for p in raw_plasmids]
    else:
        plasmids = get_plasmids(credentials['username'], credentials['password'], plasmid_limit=10)
        cached_plasmids.write_text(RootModel[List[Plasmid]](plasmids).model_dump_json(indent=2))
    maps.cache_plasmids(plasmids[:10], Path("./cache"))
    # write out db info
    db_path = Path("cache/features.db")
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path, autocommit=False) as con:
        db.create_database(con)
        db.write_plasmids(con, plasmids[:10])
        for plasmid in plasmids[:10]:
            features = maps.extract_features(Path("cache")/f"{plasmid.attachments[0].uuid}.dna")
            db.write_features(con, plasmid.uid, features)
#        for file in Path("cache").glob("*.dna"):
#            maps.extract_features(file)

