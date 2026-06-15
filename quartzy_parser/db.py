import itertools
import sqlite3
from typing import List

from .models import Feature, Plasmid

def create_database(con: sqlite3.Connection):
    con.cursor().executescript("""
    CREATE TABLE plasmids (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL
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
        FOREIGN KEY (plasmid) REFERENCES plasmids(id),
        FOREIGN KEY (sequence) REFERENCES sequences(id),
        FOREIGN KEY (translation) REFERENCES translations(id)
    );
    """)

def write_plasmids(con: sqlite3.Connection, plasmids: List[Plasmid]):
    """Writes plasmid information into the database"""
    con.cursor().executemany(
        "INSERT INTO plasmids(id,name) VALUES (?,?);",
        [(p.uid, p.name) for p in plasmids]
    )
    con.commit()
    

def write_features(con: sqlite3.Connection, plasmid_uid: str, features: List[Feature]):
    """Writes feature information into the database"""
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
        print(f"Translation: {translation}")
        result = cursor.execute("SELECT id FROM translations WHERE translation = ?", (translation,)).fetchone()
        if result is not None:
            translation_map[translation] = result[0]
        else:
            cursor.execute("INSERT INTO translations (translation) VALUES (?)", (translation,))
            translation_map[translation] = cursor.lastrowid
    
    for f in features:
        cursor.execute(
            "INSERT INTO features (plasmid,name,type,sequence,translation) VALUES (?,?,?,?,?)",
            (plasmid_uid, f.name, f.type, sequence_map.get(f.sequence), translation_map.get(f.translation, None))
        )
    con.commit()