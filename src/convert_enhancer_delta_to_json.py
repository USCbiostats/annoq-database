"""Convert ComputeEnhancerDelta *.delta.tsv files into Elasticsearch bulk UPDATE actions.

Each action touches only the 12 PEREGRINE enhancer fields of an existing document
(_id = chr:posref>alt, as assigned by convert_to_json.py); every other field is left as is.
  * fields with a value  -> set to the new value (parsed with the same doc_type.pkl parsers)
  * fields now empty     -> removed from _source, matching what a fresh full load produces
                            (convert_to_json.py omits empty fields)
No upsert: a SNP that is not already in the index fails instead of creating a partial document.

Output mirrors convert_to_json.py: <out_dir>/<delta file stem>/1.json, 2.json, ...
Load with:  python3 -m src.update_es_json <out_dir>

Usage:
    python3 -m src.convert_enhancer_delta_to_json -i delta_dir -o update_json_dir \
        -m data/doc_type.pkl --es_index <index> [--max-rows N]
"""
import argparse
import os
import pickle

from src.peregrine_update_common import (
    DELTA_SUFFIX,
    ENHANCER_FIELDS,
    doc_id,
    list_delta_files,
    read_delta_rows,
)
from src.utils import write_to_json

BATCH_SIZE = 50_000

# Remove fields that became empty, then set the rest. Used only when something must be removed;
# otherwise a plain partial "doc" update is used (faster, no scripting).
REMOVE_AND_SET_SCRIPT = (
    "for (String k : params.remove) { ctx._source.remove(k); } "
    "for (entry in params.doc.entrySet()) { ctx._source[entry.getKey()] = entry.getValue(); }"
)


def load_parsers(doc_type_file):
    with open(doc_type_file, "rb") as fh:
        dtype = pickle.load(fh)
    return {k: eval(dtype[k]) for k in ENHANCER_FIELDS if k in dtype}


def build_action(row, es_index, parsers):
    doc, remove = {}, []
    for f in ENHANCER_FIELDS:
        v = row[f]
        if v == "":
            remove.append(f)
        else:
            doc[f] = parsers.get(f, str)(v)
    action = {"_op_type": "update", "_index": es_index,
              "_id": doc_id(row["chr"], row["pos"], row["ref"], row["alt"])}
    if remove:
        action["script"] = {"source": REMOVE_AND_SET_SCRIPT, "lang": "painless",
                            "params": {"doc": doc, "remove": remove}}
    else:
        action["doc"] = doc
    return action


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", required=True, help="Delta TSV file or directory of *.delta.tsv")
    ap.add_argument("-o", "--output", required=True, help="Output directory for update JSON")
    ap.add_argument("-m", "--doc_type_file", required=True, help="Document type mapping file (data/doc_type.pkl)")
    ap.add_argument("--es_index", required=True, help="Elasticsearch index name")
    ap.add_argument("--max-rows", type=int, default=None, help="Only the first N rows of each delta file (test subsets)")
    args = ap.parse_args()

    parsers = load_parsers(args.doc_type_file)
    for fname in list_delta_files(args.input):
        stem = os.path.basename(fname)[: -len(DELTA_SUFFIX)] if fname.endswith(DELTA_SUFFIX) else os.path.basename(fname)
        out_dir = os.path.join(args.output, stem)
        os.makedirs(out_dir, exist_ok=True)
        batch, part, n, n_script = [], 1, 0, 0
        for row in read_delta_rows(fname, args.max_rows):
            a = build_action(row, args.es_index, parsers)
            n_script += "script" in a
            batch.append(a)
            n += 1
            if len(batch) == BATCH_SIZE:
                write_to_json(batch, os.path.join(out_dir, f"{part}.json"), indent=2)
                batch, part = [], part + 1
        if batch:
            write_to_json(batch, os.path.join(out_dir, f"{part}.json"), indent=2)
        print(f"{os.path.basename(fname)} -> {out_dir}: {n} update actions ({n_script} remove fields)")


if __name__ == "__main__":
    main()
