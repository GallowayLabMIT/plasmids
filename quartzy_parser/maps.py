"""Module for interacting with plasmid map files."""

import collections.abc
import urllib.request
import warnings
from pathlib import Path
from typing import List, Optional

from Bio import SeqIO
from Bio.SeqRecord import SeqRecord

from .models import Feature, Plasmid


def cache_plasmids(plasmids: List[Plasmid], cache: Path):
    """Download plasmids by UUID to a cache folder."""
    cache.mkdir(parents=True, exist_ok=True)
    for plasmid in plasmids:
        print(plasmid)
        if "embargo" in plasmid.technical_details:
            continue
        if len(plasmid.attachments) == 0:
            continue
        # try to download the first file
        filename = cache / (plasmid.attachments[0].uuid + Path(plasmid.attachments[0].file_name).suffix)

        print(f"({filename} => {plasmid.attachments[0].url}")
        if not filename.exists():
            urllib.request.urlretrieve(str(plasmid.attachments[0].url), filename=filename)


def extract_features(filename: Path, *, exclude_list: Optional[List[str]]) -> List[Feature]:
    """Extract feature information from a loaded file."""
    if exclude_list is None:
        exclude_list = ["primer_bind"]

    if filename.suffix == ".dna":
        plasmid_map: SeqRecord = SeqIO.read(filename, "snapgene")
    elif filename.suffix in [".gb", ".gbk"]:
        plasmid_map: SeqRecord = SeqIO.read(filename, "genbank")
    else:
        warnings.warn(f"Unknown plasmid filetype: {filename.suffix}", stacklevel=1)
        return []

    results = []
    for feature in plasmid_map.features:
        if feature.type in exclude_list:
            continue
        name = feature.qualifiers.get("label", feature.id)
        if isinstance(name, collections.abc.Iterable):
            name = name[0]
        parsed = Feature(name=name, type=feature.type, sequence=str(feature.extract(plasmid_map.seq).upper()))
        if "translation" in feature.qualifiers:
            parsed.translation = feature.qualifiers["translation"][0]
        results.append(parsed)
    return results
