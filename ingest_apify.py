"""
ingest_apify.py — normalize Apify Actor output into the raw_data.csv schema and merge.

Used when YouTube/Reddit are IP-blocked from the local network (429/403) so collection
runs on Apify's cloud instead. Maps Apify dataset JSON -> the SAME RAW_COLUMNS as collect.py,
strips ALL PII (author/username never read), cleans Reddit HTML + "submitted by" boilerplate,
drops empty/emoji-only text, then dedups against any existing rows (e.g. the Play corpus).

Actors used (pay-per-result, run on Apify cloud):
  YouTube : streamers/youtube-comments-scraper   (fields: comment, pageUrl, title, voteCount, type)
  Reddit  : trudax/reddit-scraper-lite           (fields: title, body, url, communityName, createdAt, dataType)

Run:  python ingest_apify.py --play raw_data.csv --youtube yt.json --reddit reddit.json -o raw_data.csv
      python ingest_apify.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys

from collect import RAW_COLUMNS, clean_text, dedup, dedup_hash, now_iso, write_csv

MIN_LEN = 12  # drop emoji-only / one-word noise like "😍✌🏻" or "nice"

# Reddit link-post boilerplate that trails the body after HTML-unescaping (&#32; -> space)
_RD_BOILER = re.compile(r"\s*submitted by\s*/u/\S+\s*\[link\]\s*\[comments\]\s*", re.I)


def _row(source: str, platform: str, url: str, text: str, posted: str, extra: dict) -> dict | None:
    text = clean_text(text)
    if len(text) < MIN_LEN:
        return None
    return {
        "doc_id": f"{'yt' if source == 'youtube' else 'rd'}_{dedup_hash(text)}",
        "source": source, "platform": platform, "url": url or "",
        "collected_at": now_iso(), "posted_date": posted or "",
        "raw_text": text, "language": "en", "rating": "",
        "extra": json.dumps(extra, ensure_ascii=False), "dedup_hash": dedup_hash(text),
    }


def from_youtube(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        # author/username deliberately NOT read (PII-free)
        r = _row("youtube", "youtube_comment", it.get("pageUrl", ""), it.get("comment", ""),
                 "", {"votes": it.get("voteCount", ""), "kind": it.get("type", "comment"),
                      "video_title": (it.get("title") or "")[:120]})
        if r:
            out.append(r)
    return out


def _clean_reddit(title: str, body: str) -> str:
    body = _RD_BOILER.sub(" ", html.unescape(body or ""))
    title = html.unescape(title or "")
    joined = f"{title}. {body}" if body.strip() else title
    return joined


def from_reddit(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        text = _clean_reddit(it.get("title", ""), it.get("body", ""))
        created = str(it.get("createdAt", ""))[:10]  # ISO date only
        r = _row("reddit", f"reddit_{it.get('dataType', 'post')}", it.get("url", ""), text, created,
                 {"community": it.get("communityName", "")})
        if r:
            out.append(r)
    return out


def load_play(path: str) -> list[dict]:
    """Existing collect.py output (already RAW_COLUMNS) — carried through unchanged."""
    try:
        with open(path, encoding="utf-8") as f:
            return [{k: r.get(k, "") for k in RAW_COLUMNS} for r in csv.DictReader(f)]
    except FileNotFoundError:
        return []


def _read_json(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("items", [])


# ---------------------------------------------------------------- selftest
def _selftest() -> None:
    yt = from_youtube([{"comment": "which size did you order? not sure it fits me",
                        "pageUrl": "u", "voteCount": 3, "type": "comment", "title": "Haul"},
                       {"comment": "😍✌🏻", "pageUrl": "u"}])  # emoji-only dropped
    assert len(yt) == 1 and yt[0]["source"] == "youtube" and yt[0]["doc_id"].startswith("yt_")
    assert "userName" not in yt[0] and "author" not in yt[0]  # no PII fields
    rd = from_reddit([{"title": "Myntra size issue",
                       "body": "tried it but &#39;size&#39; was always an issue &#32; submitted by &#32; /u/x [link] [comments]",
                       "url": "u", "communityName": "r/IndianFashion", "dataType": "post",
                       "createdAt": "2026-04-02T15:17:44.000Z"}])
    assert len(rd) == 1
    assert "submitted by" not in rd[0]["raw_text"] and "/u/" not in rd[0]["raw_text"]  # boilerplate gone
    assert "'size'" in rd[0]["raw_text"] and rd[0]["posted_date"] == "2026-04-02"       # unescaped + date
    # merge + dedup: identical normalized text collapses across sources
    merged = dedup(yt + rd + [dict(rd[0])])
    assert len(merged) == 2
    assert set(yt[0]) == set(RAW_COLUMNS)
    print("selftest OK")


def main() -> None:
    ap = argparse.ArgumentParser(description="Normalize Apify JSON -> raw_data.csv and merge")
    ap.add_argument("--play", default="", help="existing collect.py CSV to carry through (Play rows)")
    ap.add_argument("--youtube", default="", help="Apify youtube-comments-scraper dataset JSON")
    ap.add_argument("--reddit", default="", help="Apify reddit-scraper-lite dataset JSON")
    ap.add_argument("-o", "--out", default="raw_data.csv")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    rows: list[dict] = []
    if args.play:
        rows += load_play(args.play)
    if args.youtube:
        rows += from_youtube(_read_json(args.youtube))
    if args.reddit:
        rows += from_reddit(_read_json(args.reddit))

    before = len(rows)
    rows = dedup(rows)
    write_csv(rows, args.out)
    by_src: dict[str, int] = {}
    for r in rows:
        by_src[r["source"]] = by_src.get(r["source"], 0) + 1
    print(f"Wrote {len(rows)} rows to {args.out} (deduped {before - len(rows)}).")
    print("by source:", by_src)


if __name__ == "__main__":
    main()
