"""Apply bulk UPDATE actions (from convert_enhancer_delta_to_json.py) to Elasticsearch.

Unlike index_es_json.py this does not stop on the first failure: it counts results
(updated / noop / failed), writes every failure to a file, and exits non-zero if any failed.
A "document_missing_exception" means the SNP is not in the index.

Target index/host come from the environment (.env), as for index_es_json.py:
    ANNOQ_ES_URL, ANNOQ_ANNOTATIONS_INDEX
The index inside each action must match ANNOQ_ANNOTATIONS_INDEX (checked before anything is sent).

Usage:
    python3 -m src.update_es_json <update_json_dir> [--failures failures.jsonl] [--yes]
"""
import load_env  # noqa: F401  (loads .env before settings are read)
import argparse
import collections
import json
import os
import sys
import time

import ijson
from elasticsearch import helpers

from src.config.es import es
from src.config.settings import settings


def iter_actions(directory):
    for root, _dirs, files in os.walk(directory):
        for name in sorted(files):
            if name.endswith(".json"):
                path = os.path.join(root, name)
                print(path, flush=True)
                with open(path, "rb") as fh:
                    yield from ijson.items(fh, "item", use_float=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_dir")
    ap.add_argument("--failures", default="update_failures.jsonl")
    ap.add_argument("--chunk-size", type=int, default=2000)
    ap.add_argument("--yes", action="store_true", help="Do not ask for confirmation")
    args = ap.parse_args()

    index = settings.ANNOQ_ANNOTATIONS_INDEX
    indices = collections.Counter(a.get("_index") for a in iter_actions(args.input_dir))
    total = sum(indices.values())
    if set(indices) != {index}:
        sys.exit(f"Actions target {dict(indices)} but ANNOQ_ANNOTATIONS_INDEX={index}; refusing to run")
    print(f"About to apply {total} updates to index '{index}' at {settings.ANNOQ_ES_URL}")
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        sys.exit("Aborted")

    start = time.time()
    results = collections.Counter()
    with open(args.failures, "w", encoding="utf-8") as fail:
        for ok, info in helpers.streaming_bulk(
            es.options(request_timeout=300), iter_actions(args.input_dir), chunk_size=args.chunk_size,
            raise_on_error=False, raise_on_exception=False, max_retries=5,
        ):
            item = info.get("update", info)
            if ok:
                results[item.get("result", "ok")] += 1
            else:
                results["failed"] += 1
                fail.write(json.dumps(item, default=str) + "\n")
    es.indices.refresh(index=index)
    print(f"Done in {time.time() - start:.1f}s: {dict(results)}")
    if results["failed"]:
        print(f"Failures written to {args.failures}")
        sys.exit(1)


if __name__ == "__main__":
    main()
