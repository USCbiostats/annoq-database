"""Extract a slim TSV (chr pos ref alt + the 12 PEREGRINE enhancer fields) from the JSON files
that were bulk-loaded into Elasticsearch (output of convert_to_json.py).

The slim TSV is input for the Java ComputeEnhancerDelta tool, as an alternative to the full
(very large) annotated VCFs. Fields that were empty at load time are absent from the JSON and
are written as empty strings, exactly as they were in the source VCF.

Layout expected (as produced by convert_to_json.py):
    <json_root>/chr21.vcf/1.json, 2.json, ...
    <json_root>/chr22.vcf/1.json, ...
One TSV is written per sub-directory: <out_dir>/chr21.tsv

Usage:
    python3 -m src.extract_enhancer_tsv -i output/HRC_03_07_19 -o /path/slim_tsv [--max-records N] [--only chr21.vcf,chr22.vcf]
"""
import argparse
import os
import re
import time

import ijson

from src.peregrine_update_common import ENHANCER_FIELDS, KEY_COLS, doc_id


def json_files(directory):
    def num(name):
        m = re.match(r"(\d+)\.json$", name)
        return (int(m.group(1)) if m else float("inf"), name)

    return [
        os.path.join(directory, f)
        for f in sorted((f for f in os.listdir(directory) if f.endswith(".json")), key=num)
    ]


def extract_dir(src_dir, out_path, max_records=None):
    count = id_mismatch = 0
    with open(out_path, "w", encoding="utf-8", newline="") as out:
        out.write("\t".join(KEY_COLS + ENHANCER_FIELDS) + "\n")
        for jf in json_files(src_dir):
            with open(jf, "rb") as fh:
                for rec in ijson.items(fh, "item"):
                    src = rec["_source"]
                    key = [str(src.get(c, "")) for c in KEY_COLS]
                    if doc_id(*key) != rec.get("_id"):
                        id_mismatch += 1
                    vals = [str(src.get(f, "")) for f in ENHANCER_FIELDS]
                    out.write("\t".join(key + vals) + "\n")
                    count += 1
                    if max_records is not None and count >= max_records:
                        return count, id_mismatch
    return count, id_mismatch


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", required=True, help="Root directory of loaded JSON (contains chrN.vcf/ dirs)")
    ap.add_argument("-o", "--output", required=True, help="Output directory for slim TSVs")
    ap.add_argument("--max-records", type=int, default=None, help="Stop after N records per chromosome (test subsets)")
    ap.add_argument("--only", default=None, help="Comma-separated sub-directory names to process, e.g. chr21.vcf")
    args = ap.parse_args()

    os.makedirs(args.output, exist_ok=True)
    subdirs = sorted(d for d in os.listdir(args.input) if os.path.isdir(os.path.join(args.input, d)))
    if args.only:
        wanted = set(args.only.split(","))
        subdirs = [d for d in subdirs if d in wanted]
    total_mismatch = 0
    for d in subdirs:
        start = time.time()
        name = re.sub(r"\.vcf$", "", d) + ".tsv"
        n, mism = extract_dir(os.path.join(args.input, d), os.path.join(args.output, name), args.max_records)
        total_mismatch += mism
        print(f"{d} -> {name}: {n} records, {mism} _id mismatches, {time.time() - start:.1f}s")
    if total_mismatch:
        print(f"WARNING: {total_mismatch} records whose _id is not chr:posref>alt; updates for them would miss")


if __name__ == "__main__":
    main()
