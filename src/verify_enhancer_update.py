"""Verify an incremental PEREGRINE update against Elasticsearch.

  snapshot : save the current _source of every document listed in the delta (run BEFORE updating)
  check    : after updating, confirm for every listed document that
               - the 12 enhancer fields equal the delta values (compared as ';' sets;
                 empty in the delta => field absent), and
               - every other field is identical to the snapshot (nothing else was touched).

Read-only: it only issues mget requests.

Usage:
    python3 -m src.verify_enhancer_update snapshot -d delta_dir -o before.jsonl [--max-rows N]
    python3 -m src.verify_enhancer_update check    -d delta_dir -b before.jsonl [--max-rows N]
"""
import load_env  # noqa: F401
import argparse
import json
import sys

from src.config.es import es
from src.config.settings import settings
from src.peregrine_update_common import ENHANCER_FIELDS, doc_id, read_delta_rows, to_set

MGET_CHUNK = 1000


def fetch(ids):
    out = {}
    for i in range(0, len(ids), MGET_CHUNK):
        resp = es.mget(index=settings.ANNOQ_ANNOTATIONS_INDEX, ids=ids[i:i + MGET_CHUNK])
        for d in resp["docs"]:
            out[d["_id"]] = d.get("_source") if d.get("found") else None
    return out


def delta_rows(args):
    rows = {}
    for r in read_delta_rows(args.delta, args.max_rows):
        rows[doc_id(r["chr"], r["pos"], r["ref"], r["alt"])] = r
    return rows


def snapshot(args):
    rows = delta_rows(args)
    docs = fetch(list(rows))
    missing = [i for i, s in docs.items() if s is None]
    with open(args.out, "w", encoding="utf-8") as fh:
        for i, s in docs.items():
            if s is not None:
                fh.write(json.dumps({"_id": i, "_source": s}) + "\n")
    print(f"Snapshot of {len(docs) - len(missing)} documents written to {args.out}; {len(missing)} not in index")
    for i in missing[:20]:
        print("  missing:", i)


def check(args):
    rows = delta_rows(args)
    before = {}
    with open(args.before, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            before[d["_id"]] = d["_source"]
    after = fetch(list(rows))
    bad_enh = bad_other = missing = ok = 0
    for i, row in rows.items():
        cur = after.get(i)
        if cur is None:
            missing += 1
            continue
        errs = []
        for f in ENHANCER_FIELDS:
            if to_set(row[f]) != to_set(cur.get(f)):
                errs.append(f"{f}: expected {row[f]!r} got {cur.get(f)!r}")
            if row[f] == "" and f in cur:
                errs.append(f"{f}: should be absent")
        if errs:
            bad_enh += 1
            if bad_enh <= 10:
                print("ENHANCER MISMATCH", i, *errs[:3], sep="\n  ")
        prev = before.get(i)
        if prev is None:
            print("no snapshot for", i)
            bad_other += 1
            continue
        strip = lambda s: {k: v for k, v in s.items() if k not in ENHANCER_FIELDS}
        if strip(prev) != strip(cur):
            bad_other += 1
            if bad_other <= 10:
                a, b = strip(prev), strip(cur)
                diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
                print("OTHER FIELDS CHANGED", i, diff[:10])
        if not errs and strip(prev) == strip(cur):
            ok += 1
    print(f"checked={len(rows)} ok={ok} enhancer_mismatch={bad_enh} other_fields_changed={bad_other} missing={missing}")
    sys.exit(0 if ok == len(rows) else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("-d", "--delta", required=True)
    s.add_argument("-o", "--out", required=True)
    s.add_argument("--max-rows", type=int, default=None)
    c = sub.add_parser("check")
    c.add_argument("-d", "--delta", required=True)
    c.add_argument("-b", "--before", required=True)
    c.add_argument("--max-rows", type=int, default=None)
    args = ap.parse_args()
    snapshot(args) if args.cmd == "snapshot" else check(args)


if __name__ == "__main__":
    main()
