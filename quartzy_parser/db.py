"""Module for recording plasmid/feature state into an SQLite database."""

import sqlite3
from pathlib import Path
from typing import List

from .models import Feature, Plasmid

SCHEMA_VERSION = 1


def check_schema_version(db: Path) -> bool:
    """Check that the schema version matches."""
    con = sqlite3.connect(db)
    try:
        version = con.execute("SELECT version FROM metadata").fetchone()[0]
        return version == SCHEMA_VERSION
    except sqlite3.OperationalError:
        return False


def create_database(con: sqlite3.Connection):
    """Create necessary database tables to record features."""
    con.cursor().executescript(f"""
    CREATE TABLE metadata (
        version INTEGER PRIMARY KEY
    );
    INSERT INTO metadata(version) VALUES ({SCHEMA_VERSION});

    CREATE TABLE plasmids (
        id TEXT PRIMARY KEY,
        pKG INTEGER NOT NULL,
        alt_id TEXT,
        vendor TEXT,
        name TEXT NOT NULL,
        map_uuid TEXT,
        species TEXT,
        stock_date TEXT,
        embargo INTEGER DEFAULT 0,
        present INTEGER DEFAULT 0
    );

    CREATE TABLE diagnostics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plasmid TEXT NOT NULL,
        summary TEXT NOT NULL,
        details TEXT NOT NULL,
        is_error INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (plasmid) REFERENCES plasmids(id) ON DELETE CASCADE
    );

    CREATE TABLE plasmid_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plasmid TEXT NOT NULL,
        type TEXT NOT NULL,
        FOREIGN KEY (plasmid) REFERENCES plasmids(id) ON DELETE CASCADE
    );

    CREATE TABLE resistances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plasmid TEXT NOT NULL,
        resistance TEXT NOT NULL,
        FOREIGN KEY (plasmid) REFERENCES plasmids(id) ON DELETE CASCADE
    );

    CREATE TABLE sequences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sequence TEXT UNIQUE NOT NULL
    );

    CREATE TABLE translations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        translation TEXT UNIQUE NOT NULL
    );

    CREATE TABLE features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plasmid TEXT,
        name TEXT,
        type TEXT,
        sequence INTEGER,
        translation INTEGER,
        FOREIGN KEY (plasmid) REFERENCES plasmids(id) ON DELETE CASCADE,
        FOREIGN KEY (sequence) REFERENCES sequences(id) ON DELETE CASCADE,
        FOREIGN KEY (translation) REFERENCES translations(id) ON DELETE CASCADE
    );
    """)


def write_plasmid(con: sqlite3.Connection, plasmid: Plasmid) -> bool:
    """
    Write plasmid information into the database, overwriting older (non-feature) entries if they exist.

    Returns true if map needs to be updated
    """
    map_updated = False
    cursor = con.cursor()

    p = plasmid
    map_uuid = p.attachments[0].uuid if len(p.attachments) > 0 else None
    # check to see if the plasmid UUID has updated. If so, there is a new plasmid map
    # and we should cascade-delete all entries
    result = cursor.execute("SELECT map_uuid FROM plasmids WHERE id = ? AND map_uuid = ?", (p.uid, map_uuid))
    if result.fetchone() is None:
        # this cascades into the features
        cursor.execute("DELETE FROM plasmids WHERE id = ?", (p.uid,))
        map_updated = True

    embargo = "embargo" in plasmid.technical_details

    # insert the new details
    cursor.execute(
        "INSERT OR REPLACE "
        + "INTO plasmids(id,pKG,alt_id,vendor,name,map_uuid,species,stock_date,embargo,present) "
        + "VALUES (?,?,?,?,?,?,?,?,?,1);",
        (p.uid, p.pKG, p.alt_name, p.vendor, p.name, map_uuid, p.species, p.date_stored, embargo),
    )

    # replace diagnostics
    cursor.execute("DELETE FROM diagnostics WHERE plasmid=?", (p.uid,))
    cursor.executemany(
        "INSERT INTO diagnostics (plasmid,summary,details,is_error) VALUES (?,?,?,0)",
        [(p.uid, warn[0], warn[1]) for warn in p.warnings],
    )
    cursor.executemany(
        "INSERT INTO diagnostics (plasmid,summary,details,is_error) VALUES (?,?,?,1)",
        [(p.uid, error[0], error[1]) for error in p.errors],
    )

    # replace plasmid types
    cursor.execute("DELETE FROM plasmid_types WHERE plasmid=?", (p.uid,))
    cursor.executemany(
        "INSERT INTO plasmid_types (plasmid,type) VALUES (?,?)", [(p.uid, ptype) for ptype in p.plasmid_type]
    )

    # replace antibiotic resistances
    cursor.execute("DELETE FROM resistances WHERE plasmid=?", (p.uid,))
    cursor.executemany(
        "INSERT INTO resistances (plasmid,resistance) VALUES (?,?)", [(p.uid, r) for r in p.resistances]
    )
    con.commit()
    return map_updated


def remove_plasmid(con: sqlite3.Connection, plasmid_uid: str):
    """Remove a plasmid and all associated features (and pairwise entries)."""
    con.cursor().execute("DELETE FROM plasmids WHERE id = ?", (plasmid_uid,))
    con.commit()


def write_features(con: sqlite3.Connection, plasmid_uid: str, features: List[Feature]):
    """Write feature information into the database."""
    sequence_map = {}
    translation_map = {}

    cursor = con.cursor()
    for seq in [f.sequence for f in features]:
        result = cursor.execute("SELECT id FROM sequences WHERE sequence = ?", (seq,)).fetchone()
        if result is not None:
            sequence_map[seq] = result[0]
        else:
            cursor.execute("INSERT INTO sequences (sequence) VALUES (?)", (seq,))
            sequence_map[seq] = cursor.lastrowid
    for translation in [f.translation for f in features if f.translation is not None]:
        result = cursor.execute(
            "SELECT id FROM translations WHERE translation = ?", (translation,)
        ).fetchone()
        if result is not None:
            translation_map[translation] = result[0]
        else:
            cursor.execute("INSERT INTO translations (translation) VALUES (?)", (translation,))
            translation_map[translation] = cursor.lastrowid

    for f in features:
        cursor.execute(
            "INSERT INTO features (plasmid,name,type,sequence,translation) VALUES (?,?,?,?,?)",
            (
                plasmid_uid,
                f.name,
                f.type,
                sequence_map.get(f.sequence),
                translation_map.get(f.translation, None),
            ),
        )
    con.commit()


def compute_pairwise_tables(con: sqlite3.Connection):
    """Compute pairwise distance metrics from sequence/translation tables."""
