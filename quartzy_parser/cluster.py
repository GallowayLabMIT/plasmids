"""Helper module for doing simple sequence clustering."""

import dataclasses
import itertools
import math
import time
from pathlib import Path
from typing import Dict, List

import Levenshtein
import matplotlib
import matplotlib.pyplot as plt
import numpy as np


@dataclasses.dataclass
class ClusterResult:
    """Stores a summary of a individual clustered sequence."""

    relative_filename: str
    n_deletes: int
    n_inserts: int
    n_edits: int


def make_cluster_plots(base_path: Path, prefix: str, sequences: Dict[int, str]) -> Dict[int, ClusterResult]:
    """Generate square summary cluster plots from sequences."""
    # Do an approximate multiple sequence alignment: select a median sequence
    # and improve it, then do a pairwise comparison to the reference
    quickref_sequence = Levenshtein.quickmedian(sequences.values())
    if len(quickref_sequence) < 200:
        ref_sequence = Levenshtein.median_improve(quickref_sequence, sequences.values())
    else:
        ref_sequence = quickref_sequence

    edit_strings: Dict[int, List[int]] = {}
    for uid, seq in sequences.items():
        edit_string = [0] * len(seq)
        for op, source_idx, _ in Levenshtein.editops(ref_sequence, seq):
            # approximation of the real edit string, for visualization only
            try:
                if op == "replace":
                    edit_string[source_idx] = 2
                if op == "delete":
                    edit_string[source_idx] = -1
                if op == "insert":
                    edit_string.insert(source_idx, 1)
            except IndexError:
                pass
        edit_strings[uid] = edit_string
    square_size = math.ceil(np.sqrt(max([len(x) for x in edit_strings.values()])))

    cmap = matplotlib.colors.ListedColormap(["red", "white", "green", "blue"])
    bounds = [-2, -0.5, 0.5, 1.5, 2.5]
    norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)

    results: Dict[int, ClusterResult] = {}
    for uid, edit_string in edit_strings.items():
        vals = np.zeros(square_size**2)
        vals[: len(edit_string)] = edit_string
        vals = np.reshape(vals, (square_size, square_size))
        fig = plt.figure(figsize=(1.5, 1.5))
        ax = fig.subplots(1, 1)
        ticks = [x + 0.5 for x in range(square_size)]
        ax.set_xticks(ticks)
        ax.set_yticks(ticks)
        ax.tick_params("both", bottom=False, left=False, labelbottom=False, labelleft=False)
        ax.grid(which="major", color="0.5", linestyle="-", linewidth=0.1)
        ax.imshow(vals, cmap=cmap, norm=norm, interpolation="none")

        filename = f"{prefix}_seq_{uid}.svg"
        fig.savefig(str(base_path / filename))
        plt.close()

        results[uid] = ClusterResult(
            relative_filename=filename,
            n_deletes=np.sum(vals == -1),
            n_inserts=np.sum(vals == 1),
            n_edits=np.sum(vals == 2),
        )
    return results


def cluster_sequences(sequences: Dict[int, str], max_mismatch_frac=4) -> Dict[int, List[int]]:
    """Cluster sequences based on similarity."""
    pre_cluster = time.time()
    adjacency_lists: Dict[int, List[int]] = {}
    for a, b in itertools.pairwise(sequences.items()):
        uid_a, seq_a = a
        uid_b, seq_b = b
        longest = max(len(seq_a), len(seq_b))
        cutoff = np.ceil(longest * (max_mismatch_frac / 100))

        if Levenshtein.distance(seq_a, seq_b, score_cutoff=cutoff) < cutoff + 1:
            if uid_a not in adjacency_lists:
                adjacency_lists[uid_a] = []
            if uid_b not in adjacency_lists:
                adjacency_lists[uid_b] = []
            adjacency_lists[uid_a].append(uid_b)
            adjacency_lists[uid_b].append(uid_b)
    post_cluster = time.time()
    print(f"Clustered {len(sequences)} sequences in {post_cluster - pre_cluster:0.3f} seconds")

    # merge clusters together via BFS
    next_cluster_id = 0
    node_to_cluster: Dict[int, int] = {}
    for start_node in adjacency_lists.keys():
        if start_node in node_to_cluster:
            # already processed
            continue
        # we are in a new cluster
        cluster_idx = next_cluster_id
        next_cluster_id += 1
        node_to_cluster[start_node] = cluster_idx
        to_visit = list(adjacency_lists[start_node])

        while len(to_visit) > 0:
            current = to_visit.pop(0)
            if current in node_to_cluster:
                continue
            node_to_cluster[current] = cluster_idx
            to_visit.extend(adjacency_lists[current])
    cluster_to_nodes: Dict[int, List[int]] = {}
    for k, v in node_to_cluster.items():
        if v not in cluster_to_nodes:
            cluster_to_nodes[v] = []
        cluster_to_nodes[v].append(k)

    return cluster_to_nodes
