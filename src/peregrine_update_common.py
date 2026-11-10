"""Shared helpers for the incremental PEREGRINE (enhancer -> gene) update.

Only these 12 fields are derived from PEREGRINE data; an incremental update touches nothing else.
They are produced by annoq-data-builder java_wgsa_add/add_panther_enhancer
(Snp.COLS_TO_BE_ADDED / logic.EnhancerAnnotator).
"""
import csv
import os
import sys

from src.utils import id_gen

PANTHER_ANNOT_IDS = [
    "GO_molecular_function_complete_list_id",
    "GO_biological_process_complete_list_id",
    "GO_cellular_component_complete_list_id",
    "PANTHER_GO_SLIM_molecular_function_list_id",
    "PANTHER_GO_SLIM_biological_process_list_id",
    "PANTHER_GO_SLIM_cellular_component_list_id",
    "PANTHER_protein_class_list_id",
    "REACTOME_pathway_list_id",
    "PANTHER_pathway_list_id",
]

ENHANCER_FIELDS = ["enhancer_linked_" + i for i in PANTHER_ANNOT_IDS] + [
    "enhancer_linked_assay",
    "enhancer_linked_genes",
    "enhancer_linked_enhancer",
]

KEY_COLS = ["chr", "pos", "ref", "alt"]
DELTA_SUFFIX = ".delta.tsv"
CHANGE_COL = "peregrine_change"

csv.field_size_limit(sys.maxsize)


def to_set(value):
    """Values are ';'-joined Java HashSets, so order is not meaningful. Empty/absent -> empty set.
    Empty items are kept (e.g. an empty assay in '3;'), matching the Java comparison."""
    if value is None or value == "":
        return frozenset()
    return frozenset(str(value).split(";"))


def doc_id(chrom, pos, ref, alt):
    """Same _id convert_to_json.py assigns: id_gen() over the first four VCF columns."""
    return id_gen([str(chrom), str(pos), str(ref), str(alt)])


def list_delta_files(path):
    if os.path.isfile(path):
        return [path]
    return sorted(
        os.path.join(path, f) for f in os.listdir(path) if f.endswith(DELTA_SUFFIX)
    )


def read_delta_rows(path, max_rows=None):
    """Yield dicts from ComputeEnhancerDelta *.delta.tsv files (a file or a directory).
    max_rows limits rows per file, for small test subsets."""
    for fname in list_delta_files(path):
        with open(fname, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE)
            missing = [c for c in KEY_COLS + ENHANCER_FIELDS if c not in reader.fieldnames]
            if missing:
                raise ValueError(f"{fname}: missing columns {missing}")
            for n, row in enumerate(reader):
                if max_rows is not None and n >= max_rows:
                    break
                row["_file"] = os.path.basename(fname)
                yield row
