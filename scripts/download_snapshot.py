#!/usr/bin/env python3
"""Download one openFDA drug label per seed generic name into data/raw/.

No API key is used. Requests are throttled and already-cached drugs are skipped.
Requires network. Python 3.9 compatible.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from labelpath.paths import MANIFEST_FILE, MISSED_FILE, RAW_DIR, SEED_FILE
from labelpath.textutil import generic_matches_seed, load_name_list, unique_strings

API_URL = "https://api.fda.gov/drug/label.json"
USER_AGENT = (
    "LabelPath/0.2 (local snapshot for a Relate hackathon project; "
    "polite unauthenticated openFDA client)"
)
# Official unauthenticated cap is 240 requests/minute and 1,000/day per IP
# (https://open.fda.gov/apis/authentication/). Stay well under the per-minute cap.
DEFAULT_DELAY_SEC = 0.5
SEARCH_LIMIT = 25
SECTION_FIELDS = (
    "indications_and_usage",
    "contraindications",
    "boxed_warning",
    "drug_interactions",
    "warnings_and_cautions",
)
OPENFDA_FIELDS = (
    "generic_name",
    "brand_name",
    "substance_name",
    "application_number",
)
RECORD_FIELDS = ("set_id", "id", "effective_time") + SECTION_FIELDS


def seed_slug(seed: str) -> str:
    slug = "_".join(seed.lower().split())
    slug = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in slug)
    return slug.strip("_") or "unnamed"


def cache_path(seed: str) -> Path:
    return RAW_DIR / (seed_slug(seed) + ".json")


def trim_record(record: Dict[str, Any]) -> Dict[str, Any]:
    trimmed: Dict[str, Any] = {}
    for key in RECORD_FIELDS:
        if key in record and record[key] not in (None, "", []):
            trimmed[key] = record[key]
    openfda = record.get("openfda") or {}
    kept_openfda = {}
    for key in OPENFDA_FIELDS:
        if key in openfda and openfda[key] not in (None, "", []):
            kept_openfda[key] = openfda[key]
    if kept_openfda:
        trimmed["openfda"] = kept_openfda
    return trimmed


def matching_records(results: List[Dict[str, Any]], seed: str) -> List[Dict[str, Any]]:
    matched = []
    for record in results:
        names = unique_strings((record.get("openfda") or {}).get("generic_name") or [])
        if any(generic_matches_seed(name, seed) for name in names):
            matched.append(record)
    matched.sort(key=lambda rec: rec.get("effective_time") or "", reverse=True)
    return matched


def has_kept_section(record: Dict[str, Any]) -> bool:
    return any(record.get(field) not in (None, "", []) for field in SECTION_FIELDS)


def pick_record(results: List[Dict[str, Any]], seed: str) -> Optional[Dict[str, Any]]:
    matched = matching_records(results, seed)
    if not matched:
        return None
    with_sections = [rec for rec in matched if has_kept_section(rec)]
    # Most recent matching label; if that one has none of the kept sections,
    # use the most recent matching label that does.
    return (with_sections or matched)[0]


def http_get_json(url: str, timeout: int, retries: int) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            payload: Dict[str, Any] = {}
            try:
                payload = json.loads(raw.decode("utf-8")) if raw else {}
            except (ValueError, UnicodeDecodeError):
                payload = {}
            if exc.code == 404:
                return {"error": payload.get("error") or {"code": "NOT_FOUND"}, "results": []}
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = (2 ** attempt) * 2
                print("  HTTP %s; retrying in %ss" % (exc.code, wait), flush=True)
                time.sleep(wait)
                last_error = exc
                continue
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt < retries:
                wait = (2 ** attempt) * 2
                print("  request failed (%s); retrying in %ss" % (exc, wait), flush=True)
                time.sleep(wait)
                last_error = exc
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("request failed without an error")


def search_url(seed: str) -> str:
    query = {
        "search": 'openfda.generic_name:"%s"' % seed,
        "sort": "effective_time:desc",
        "limit": str(SEARCH_LIMIT),
    }
    return API_URL + "?" + urllib.parse.urlencode(query)


def download_seed(seed: str, timeout: int, retries: int) -> Dict[str, Any]:
    url = search_url(seed)
    payload = http_get_json(url, timeout=timeout, retries=retries)
    results = payload.get("results") or []
    record = pick_record(results, seed)
    meta = payload.get("meta") or {}
    if record is None:
        err = (payload.get("error") or {}).get("message") or "no matching generic_name"
        return {
            "ok": False,
            "seed": seed,
            "reason": err,
            "total": (meta.get("results") or {}).get("total"),
            "query": url,
            "api_last_updated": meta.get("last_updated"),
        }
    return {
        "ok": True,
        "seed": seed,
        "query": url,
        "api_last_updated": meta.get("last_updated"),
        "candidates": (meta.get("results") or {}).get("total"),
        "record": trim_record(record),
    }


def load_cached(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (ValueError, OSError):
        return None
    if isinstance(data, dict) and data.get("record") and data.get("seed"):
        return data
    return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download seeds even when a cached file exists.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SEC,
        help="Seconds to wait between API requests (default: 0.5).",
    )
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args(argv)

    seeds = load_name_list(SEED_FILE)
    if not seeds:
        print("No seeds found in %s" % SEED_FILE, file=sys.stderr)
        return 1

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    retrieved_on = date.today().isoformat()
    found: List[Dict[str, Any]] = []
    missed: List[Dict[str, Any]] = []
    skipped_cache = 0
    downloaded = 0

    print("Seeds: %s" % len(seeds), flush=True)
    for index, seed in enumerate(seeds, start=1):
        path = cache_path(seed)
        cached = None if args.force else load_cached(path)
        if cached is not None:
            skipped_cache += 1
            found.append(
                {
                    "seed": seed,
                    "file": path.name,
                    "set_id": (cached.get("record") or {}).get("set_id"),
                    "cached": True,
                    "retrieved_at": cached.get("retrieved_at"),
                }
            )
            print(
                "[%s/%s] cache hit  %s  (%s)" % (index, len(seeds), seed, path.name),
                flush=True,
            )
            continue

        if downloaded and args.delay > 0:
            time.sleep(args.delay)
        print("[%s/%s] download  %s" % (index, len(seeds), seed), flush=True)
        try:
            result = download_seed(seed, timeout=args.timeout, retries=args.retries)
        except Exception as exc:
            missed.append({"seed": seed, "reason": "request error: %s" % exc})
            print("  MISS  %s" % exc, flush=True)
            downloaded += 1
            continue
        downloaded += 1
        if not result.get("ok"):
            missed.append(
                {
                    "seed": seed,
                    "reason": result.get("reason"),
                    "total": result.get("total"),
                    "query": result.get("query"),
                }
            )
            print("  MISS  %s" % result.get("reason"), flush=True)
            continue
        record = result["record"]
        payload = {
            "seed": seed,
            "retrieved_at": retrieved_on,
            "query": result.get("query"),
            "api_last_updated": result.get("api_last_updated"),
            "candidates": result.get("candidates"),
            "record": record,
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        found.append(
            {
                "seed": seed,
                "file": path.name,
                "set_id": record.get("set_id"),
                "cached": False,
                "retrieved_at": retrieved_on,
            }
        )
        generic = unique_strings((record.get("openfda") or {}).get("generic_name") or [])
        print(
            "  OK  set_id=%s  generic=%s  effective_time=%s"
            % (record.get("set_id"), ", ".join(generic) or "?", record.get("effective_time")),
            flush=True,
        )

    manifest = {
        "source": "https://api.fda.gov/drug/label.json",
        "docs": "https://open.fda.gov/apis/drug/label/",
        "terms": "https://open.fda.gov/terms/",
        "retrieved_at": retrieved_on,
        "api_key_used": False,
        "seed_count": len(seeds),
        "found_count": len(found),
        "missed_count": len(missed),
        "cache_hits": skipped_cache,
        "requests": downloaded,
        "found": found,
        "missed": missed,
    }
    with open(MANIFEST_FILE, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    with open(MISSED_FILE, "w", encoding="utf-8") as handle:
        if not missed:
            handle.write("# No missed seed drugs in this snapshot.\n")
        else:
            handle.write("# Seed drugs with no matching openFDA generic_name label\n")
            for item in missed:
                handle.write("%s\t%s\n" % (item["seed"], item.get("reason") or ""))

    print(
        "Done. found=%s missed=%s cache_hits=%s requests=%s retrieved_at=%s"
        % (len(found), len(missed), skipped_cache, downloaded, retrieved_on),
        flush=True,
    )
    print("Manifest: %s" % MANIFEST_FILE)
    if missed:
        print("Missed list: %s" % MISSED_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
