"""Module for interacting with plasmid map files."""

import asyncio
import collections.abc
import warnings
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from httpx import AsyncClient

from .models import Feature, Plasmid


async def fetch_single_plasmid(
    plasmid: Plasmid, c: AsyncClient, sem: asyncio.Semaphore
) -> Tuple[Plasmid, List[Feature]]:
    """Fetch a single plasmid and parse it. Returns empty list on failure."""
    try:
        async with sem:
            if "embargo" in plasmid.technical_details or len(plasmid.attachments) == 0:
                return (plasmid, [])

            response = await c.get(str(plasmid.attachments[0].url))
            suffix = Path(plasmid.attachments[0].file_name).suffix
            stream = BytesIO(response.content)

            return (plasmid, extract_features(suffix, stream))

    except Exception:
        return (plasmid, [])


async def fetch_features(plasmids: List[Plasmid], max_concurrency: int = 5) -> Dict[str, List[Feature]]:
    """Fetch plasmid features simultaneously, returning a plasmid UID -> feature list mapping."""
    sem = asyncio.Semaphore(max_concurrency)
    async with AsyncClient(http2=True) as c:
        tasks = [fetch_single_plasmid(p, c, sem) for p in plasmids]
        raw_plasmid_features = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [r for r in raw_plasmid_features if isinstance(r, BaseException)]
        for error in errors:
            print(f"[FAIL] fetching plasmid features for plasmid {str(error)}", flush=True)

        plasmid_features = [r for r in raw_plasmid_features if not isinstance(r, BaseException)]
        return {p.uid: features for p, features in plasmid_features}


def extract_features(
    suffix: str, stream: BytesIO, *, exclude_list: Optional[List[str]] = None
) -> List[Feature]:
    """Extract feature information from a loaded file."""
    if exclude_list is None:
        exclude_list = ["primer_bind"]

    try:
        if suffix == ".dna":
            plasmid_map: SeqRecord = SeqIO.read(stream, "snapgene")
        elif suffix in [".gb", ".gbk"]:
            plasmid_map: SeqRecord = SeqIO.read(stream, "genbank")
        else:
            warnings.warn(f"Unknown plasmid filetype: {suffix}", stacklevel=1)
            return []
    except Exception as e:
        warnings.warn(f"Exception occured: {str(e)}", stacklevel=1)
        return []

    results = []
    for feature in plasmid_map.features:
        try:
            if feature.type in exclude_list:
                continue
            name = feature.qualifiers.get("label", feature.id)
            if isinstance(name, collections.abc.Iterable):
                name = name[0]
            parsed = Feature(
                name=name, type=feature.type, sequence=str(feature.extract(plasmid_map.seq).upper())
            )
            if "translation" in feature.qualifiers and len(feature.qualifiers["translation"]) > 0:
                parsed.translation = feature.qualifiers["translation"][0]
            results.append(parsed)
        except Exception as e:
            warnings.warn(f"Exception occurred: {str(e)}", stacklevel=1)
    return results
