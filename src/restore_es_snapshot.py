"""Roll back an incremental PEREGRINE update by restoring documents from a snapshot.

The snapshot is the file written by `verify_enhancer_update snapshot` BEFORE the update. Each
document in it is written back in full (index operation, replacing the current document), then
read back and compared with the snapshot. This also reverts any other change made to those
documents after the snapshot was taken.

Target index/host come from the environment (.env): ANNOQ_ES_URL, ANNOQ_ANNOTATIONS_INDEX.

Usage:
    python3 -m src.restore_es_snapshot -b before_all.jsonl [-d delta_dir [--max-rows N]] [--yes]

  -d / --max-rows  restore only the documents listed in these delta files (e.g. only the subset
                   that was applied); without -d every document in the snapshot is restored.
"""
import load_env  # noqa: F401  (loads .env before settings are read)
import argparse
import json
import sys
import time

from elasticsearch import helpers

from src.config.es import es
from src.config.settings import settings
from src.peregrine_update_common import doc_id, read_delta_rows

MGET_CHUNK = 500


def load_snapshot(path):
    docs = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                d = json.loads(line)
                docs[d["_id"]] = d["_source"]
    return docs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-b", "--before", required=True, help="Snapshot written by verify_enhancer_update snapshot")
    ap.add_argument("-d", "--delta", default=None, help="Only restore documents listed in these delta files")
    ap.add_argument("--max-rows", type=int, default=None, help="With -d: first N rows of each delta file")
    ap.add_argument("--failures", default="restore_failures.jsonl")
    ap.add_argument("--chunk-size", type=int, default=500)
    ap.add_argument("--yes", action="store_true", help="Do not ask for confirmation")
    args = ap.parse_args()

    index = settings.ANNOQ_ANNOTATIONS_INDEX
    snap = load_snapshot(args.before)
    if args.delta:
        wanted = {doc_id(r["chr"], r["pos"], r["ref"], r["alt"]) for r in read_delta_rows(args.delta, args.max_rows)}
        not_in_snapshot = wanted - set(snap)
        if not_in_snapshot:
            sys.exit(f"{len(not_in_snapshot)} delta documents are not in the snapshot (e.g. {sorted(not_in_snapshot)[0]}); refusing to run")
        snap = {i: snap[i] for i in wanted}
    if not snap:
        sys.exit("Nothing to restore")

    print(f"About to restore {len(snap)} documents from {args.before} into index '{index}' at {settings.ANNOQ_ES_URL}")
    print("Each document is replaced in full by its snapshot copy.")
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        sys.exit("Aborted")

    start = time.time()
    actions = ({"_op_type": "index", "_index": index, "_id": i, "_source": s} for i, s in snap.items())
    ok = failed = 0
    with open(args.failures, "w", encoding="utf-8") as fail:
        for success, info in helpers.streaming_bulk(
            es.options(request_timeout=300), actions, chunk_size=args.chunk_size,
            raise_on_error=False, raise_on_exception=False, max_retries=5,
        ):
            if success:
                ok += 1
            else:
                failed += 1
                fail.write(json.dumps(info, default=str) + "\n")
    es.indices.refresh(index=index)
    print(f"Restored {ok} documents, {failed} failed, in {time.time() - start:.1f}s")

    # Read back and compare with the snapshot
    ids = list(snap)
    differ = 0
    for i in range(0, len(ids), MGET_CHUNK):
        for d in es.mget(index=index, ids=ids[i:i + MGET_CHUNK])["docs"]:
            if not d.get("found") or d["_source"] != snap[d["_id"]]:
                differ += 1
                if differ <= 10:
                    print("  NOT RESTORED:", d["_id"])
    print(f"Verify: {len(ids) - differ} of {len(ids)} documents identical to the snapshot, {differ} differ")
    if failed:
        print(f"Failures written to {args.failures}")
    sys.exit(1 if failed or differ else 0)


if __name__ == "__main__":
    main()
