"""Build the website from cached database state."""

import argparse
import dataclasses
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

import jinja2
import Levenshtein
import webdav3
import webdav3.client

parser = argparse.ArgumentParser(description="Generates HTML and PDFs from Markdown files")
parser.add_argument("--force-rebuild", action="store_true")
parser.add_argument("--webdav", action="store_true", help="Use WebDAV to cache database files")


jinja2_env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"), autoescape=False)


@dataclasses.dataclass
class TOCDetails:
    """Plasmid details needed for the table of contents."""

    uid: str
    pKG: int
    alt_id: str
    name: str
    vendor: Optional[str]


@dataclasses.dataclass
class PlasmidFeatureLink:
    """Minimal data for writing a link to a plasmid."""

    sequence_uid: int
    feature_name: str
    plasmid_uid: str
    pKG: str
    plasmid_name: str


def write_sequences(con: sqlite3.Connection, sequence_dir: Path):
    """Generate per-sequence feature pages."""
    template = jinja2_env.get_template("sequence_feature.rst")

    cursor = con.cursor()
    for (uid,) in cursor.execute("SELECT id FROM sequences").fetchall():
        # fetch all matching features
        features = [
            PlasmidFeatureLink(
                sequence_uid=uid, feature_name=f[0], plasmid_uid=f[1], pKG=f[2], plasmid_name=f[3]
            )
            for f in cursor.execute(
                "SELECT features.name, features.plasmid, plasmids.pKG, plasmids.name "
                + "FROM features INNER JOIN plasmids ON plasmids.id=features.plasmid "
                + "WHERE sequence=?",
                (uid,),
            ).fetchall()
        ]

        median_name = Levenshtein.median([f.feature_name for f in features])

        with open(sequence_dir / f"{uid}.rst", "w", encoding="utf-8") as f:
            f.write(
                template.render(
                    title=median_name,
                    links=features,
                )
            )
    with open(sequence_dir / "index.rst", "w", encoding="utf-8") as f:
        f.write(jinja2_env.get_template("sequence_index.rst").render())


def write_plasmids(con: sqlite3.Connection, plasmid_dir: Path):
    """Generate per-plasmid pages."""
    template = jinja2_env.get_template("plasmid.rst")
    cursor = con.cursor()

    result = cursor.execute(
        "SELECT id, pKG, alt_id, vendor, name, species, stock_date, embargo FROM plasmids"
    ).fetchall()

    for uid, pKG, alt_id, vendor, name, species, stock_date, embargo in result:
        errors = [
            x[0]
            for x in cursor.execute(
                "SELECT details FROM diagnostics WHERE plasmid=? AND is_error=1", (uid,)
            ).fetchall()
        ]

        warnings = [
            x[0]
            for x in cursor.execute(
                "SELECT details FROM diagnostics WHERE plasmid=? AND is_error=0", (uid,)
            ).fetchall()
        ]

        title = f"pKG{pKG} - {name}"
        if embargo == 1:
            title = f"pKG{pKG} - EMBARGO"

        if len(warnings) > 0:
            title = "|fa_warning| (W) " + title

        if len(errors) > 0:
            title = "|fa_error| (E) " + title

        resistances = [
            x[0]
            for x in cursor.execute("SELECT resistance FROM resistances WHERE plasmid=?", (uid,)).fetchall()
        ]

        plasmid_types = [
            x[0] for x in cursor.execute("SELECT type FROM plasmid_types WHERE plasmid=?", (uid,)).fetchall()
        ]

        features = [
            PlasmidFeatureLink(
                sequence_uid=f[0], feature_name=f[1], plasmid_uid=uid, pKG=pKG, plasmid_name=name
            )
            for f in cursor.execute("SELECT sequence, name FROM features WHERE plasmid=?", (uid,))
        ]

        with open(plasmid_dir / f"{uid}.rst", "w", encoding="utf-8") as f:
            f.write(
                template.render(
                    title=title,
                    vendor=vendor,
                    alt_name=alt_id,
                    errors=errors,
                    warnings=warnings,
                    species=species,
                    date_stored=stock_date,
                    resistances=resistances,
                    plasmid_types=plasmid_types,
                    features=features,
                )
            )


@dataclasses.dataclass
class LintPlasmidLink:
    """Minimal information required to format a plasmid hyperlink."""

    uid: str
    alt_id: str
    pKG: int


@dataclasses.dataclass
class LintSummary:
    """Summarized plasmid errors/warnings."""

    n_plasmid_errors: int
    n_plasmid_warnings: int
    lint_errors: Dict[str, List[LintPlasmidLink]]
    lint_warnings: Dict[str, List[LintPlasmidLink]]


def summarize_linting(con: sqlite3.Connection, *, subset: Optional[List[str]] = None) -> LintSummary:
    """Group warnings/errors by type and count plasmids."""
    if subset is None:
        db_diagnostics = (
            con.cursor()
            .execute(
                "SELECT diagnostics.is_error, diagnostics.plasmid, "
                + "diagnostics.summary, "
                + "plasmids.pKG, plasmids.alt_id "
                + "FROM diagnostics "
                + "INNER JOIN plasmids ON plasmids.id=diagnostics.plasmid"
            )
            .fetchall()
        )
    else:
        db_diagnostics = (
            con.cursor()
            .execute(
                "SELECT diagnostics.is_error, diagnostics.plasmid, "
                + "diagnostics.summary, "
                + "plasmids.pKG, plasmids.alt_id "
                + "FROM diagnostics "
                + "INNER JOIN plasmids ON plasmids.id=diagnostics.plasmid "
                + "WHERE plasmids.id IN ("
                + ",".join(["?"] * len(subset))
                + ")",
                (*subset,),
            )
            .fetchall()
        )

    result = LintSummary(
        n_plasmid_errors=len([x for x in db_diagnostics if x[0] == 1]),
        n_plasmid_warnings=len([x for x in db_diagnostics if x[0] == 0]),
        lint_errors={},
        lint_warnings={},
    )
    for is_error, uid, summary, pKG, alt_id in db_diagnostics:
        lint_dict = result.lint_errors if is_error else result.lint_warnings
        if summary not in lint_dict:
            lint_dict[summary] = []
        lint_dict[summary].append(LintPlasmidLink(uid=uid, pKG=pKG, alt_id=alt_id))
    return result


def summarize_alt_names(con: sqlite3.Connection) -> Dict[str, List[TOCDetails]]:
    """Compute alternative names for plasmids."""
    result: Dict[str, List[TOCDetails]] = {}
    # Iterate over plasmids, accumulating alternate names
    db_result = con.cursor().execute("SELECT vendor, alt_id, id, pKG, name FROM plasmids")
    for vendor, alt_id, uid, pKG, name in db_result.fetchall():
        # The alternate category is the vendor name, if given
        alt_cat: Optional[str] = None
        if vendor is not None:
            alt_cat = vendor
        else:
            # Try to use a regex to match
            alt_match = re.match(r"^(?P<alt_category>p[a-zA-Z]+)(?P<alt_name>.*)$", alt_id)
            if alt_match is not None:
                alt_cat = alt_match.group("alt_category")
        if alt_cat is None:
            continue
        if alt_cat not in result:
            result[alt_cat] = []
        result[alt_cat].append(TOCDetails(uid=uid, pKG=pKG, alt_id=alt_id, name=name, vendor=vendor))
    return result


def write_alt_name_lists(
    con: sqlite3.Connection, alt_names: Dict[str, List[TOCDetails]], plasmid_path: Path
) -> List[str]:
    """Write table of contents lines for alt-name plasmid lists."""
    template = jinja2_env.get_template("alternative_index.rst")

    alt_indexes: List[str] = []
    for alt_cat, plasmids in alt_names.items():
        title = f"By {alt_cat} ({len(plasmids)} plasmids)"
        idx_filename = f"by_{alt_cat}"
        alt_indexes.append(idx_filename)
        sorted_plasmids = sorted(plasmids, key=lambda p: p.alt_id)

        lint_summary = summarize_linting(con, subset=[p.uid for p in plasmids])

        alt_index = template.render(title=title, plasmids=sorted_plasmids, **dataclasses.asdict(lint_summary))

        with (plasmid_path / f"{idx_filename}.rst").open("w") as f:
            f.write(alt_index)
    return alt_indexes


def build_index_page(con: sqlite3.Connection, alt_indexes: List[str]) -> str:
    """Make the landing page."""
    lint_summary = summarize_linting(con)

    template = jinja2_env.get_template("index.rst")
    return template.render(alt_indexes=alt_indexes, **dataclasses.asdict(lint_summary))


if __name__ == "__main__":
    args = parser.parse_args()
    base = Path(__file__).resolve().parent

    if Path(base / "credentials.json").is_file():
        with open("credentials.json") as cred_file:
            credentials = json.load(cred_file)
    else:
        credentials = {}

    if "WEBDAV_URL" in os.environ and "WEBDAV_USER" in os.environ and "WEBDAV_PASSWORD" in os.environ:
        credentials["webdav_url"] = os.environ["WEBDAV_URL"]
        credentials["webdav_user"] = os.environ["WEBDAV_USER"]
        credentials["webdav_password"] = os.environ["WEBDAV_PASSWORD"]

    if args.webdav and (
        "webdav_url" not in credentials
        or "webdav_user" not in credentials
        or "webdav_password" not in credentials
    ):
        raise ValueError("Cannot find Webdav credentials!")

    # open the database
    db_path = Path("cache/features.db")
    if args.webdav:
        webdav_options = {
            "webdav_hostname": credentials["webdav_url"],
            "webdav_login": credentials["webdav_user"],
            "webdav_password": credentials["webdav_password"],
        }
        cache_client = webdav3.client.Client(webdav_options)
        try:
            cache_client.download_sync(remote_path="plasmids.db", local_path=db_path)
        except webdav3.exceptions.WebDavException:
            pass

    with sqlite3.connect(db_path) as con:
        alt_names_map = summarize_alt_names(con)
        # Filter out alt names with only one entry
        alt_names_map = {k: v for k, v in alt_names_map.items() if len(v) > 1}
        # Sort alt names by # of plasmids
        sorted_alt_names_map = dict(sorted(alt_names_map.items(), key=lambda item: -len(item[1])))

        alt_indexes = write_alt_name_lists(con, sorted_alt_names_map, base / "docs" / "plasmids")

        with (base / "docs" / "index.rst").open("w", encoding="utf-8") as index_file:
            index_file.write(build_index_page(con, alt_indexes))

        plasmid_dir = base / "docs" / "plasmids"
        plasmid_dir.mkdir(exist_ok=True)
        write_plasmids(con, plasmid_dir)

        sequence_dir = base / "docs" / "sequences"
        sequence_dir.mkdir(exist_ok=True)
        write_sequences(con, sequence_dir)

    if args.force_rebuild and (base / "output").is_dir():
        shutil.rmtree(base / "output")
    if not (base / "output").is_dir():
        (base / "output").mkdir()

    python_exe = sys.executable
    ## Calculate docs path:
    docs_path = base / "docs"
    html_path = base / "output" / "html"
    html_args = [
        python_exe,
        "-m",
        "sphinx.cmd.build",
        "-b",
        "html",
        "-j",
        "auto",
        str(docs_path),
        str(html_path),
    ]
    subprocess.run(html_args)
