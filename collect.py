"""
collect.py — Step 1 of the Myntra Wishlist->Purchase Discovery Engine.

Collect PUBLIC user text about Myntra from free sources, normalise into one CSV,
strip PII (no author names/handles are ever stored), and dedup by text hash.

Sources (all free, no paid keys):
  * Google Play reviews  (google-play-scraper)      -- primary, ~2500 rows
  * YouTube comments     (youtube-comment-downloader) -- optional, pass --youtube
  * Reddit               (praw)                      -- optional, needs a free key

Output columns:
  doc_id, source, platform, url, collected_at, posted_date,
  raw_text, language, rating, extra, dedup_hash

Run:
  python collect.py --play-count 2500 -o raw_data.csv
  python collect.py --youtube urls.txt --per-video 300 -o raw_data.csv
  python collect.py --selftest        # offline sanity check, no network
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone

RAW_COLUMNS = [
    "doc_id", "source", "platform", "url", "collected_at", "posted_date",
    "raw_text", "language", "rating", "extra", "dedup_hash",
]

MYNTRA_PLAY_ID = "com.myntra.android"
PLAY_URL = f"https://play.google.com/store/apps/details?id={MYNTRA_PLAY_ID}"


# ---------------------------------------------------------------- pure helpers
def norm(text: str) -> str:
    """Lowercase + collapse whitespace. Used only for dedup, not for storage."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def dedup_hash(text: str) -> str:
    return hashlib.sha256(norm(text).encode("utf-8")).hexdigest()[:16]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean_text(text: str) -> str:
    """Trim and squeeze internal newlines so one review is one CSV cell."""
    return re.sub(r"[ \t]+", " ", (text or "").replace("\r", " ").replace("\n", " ")).strip()


# ---------------------------------------------------------------- collectors
def collect_play(count: int, lang: str = "en", country: str = "in",
                 sort: str = "newest") -> list[dict]:
    """Paginate Google Play reviews. Stores NO author name (PII).

    sort: 'newest' (default, per spec) or 'relevant' (longer, barrier-rich text).
    """
    from google_play_scraper import Sort, reviews

    sort_enum = Sort.MOST_RELEVANT if sort == "relevant" else Sort.NEWEST
    out, token, page = [], None, 200
    while len(out) < count:
        batch, token = reviews(
            MYNTRA_PLAY_ID, lang=lang, country=country, sort=sort_enum,
            count=min(page, count - len(out)), continuation_token=token,
        )
        if not batch:
            break
        for r in batch:
            txt = clean_text(r.get("content"))
            if not txt:
                continue
            at = r.get("at")
            out.append({
                "doc_id": f"play_{r.get('reviewId', '')}",
                "source": "google_play",
                "platform": "android_app_review",
                "url": PLAY_URL,
                "collected_at": now_iso(),
                "posted_date": at.strftime("%Y-%m-%d") if isinstance(at, datetime) else "",
                "raw_text": txt,
                "language": lang,
                "rating": r.get("score", ""),
                # PII-free extras only: helpful votes + app version. No userName.
                "extra": json.dumps({
                    "thumbs_up": r.get("thumbsUpCount", 0),
                    "app_version": r.get("reviewCreatedVersion") or "",
                }, ensure_ascii=False),
                "dedup_hash": dedup_hash(txt),
            })
        print(f"  play: {len(out)}/{count}", file=sys.stderr)
        if token is None:
            break
    return out


def collect_youtube(urls: list[str], per_video: int, lang: str = "en") -> list[dict]:
    """Top comments per video. Stores NO author handle (PII)."""
    from youtube_comment_downloader import SORT_BY_POPULAR, YoutubeCommentDownloader

    dl = YoutubeCommentDownloader()
    out = []
    for url in urls:
        try:
            gen = dl.get_comments_from_url(url, sort_by=SORT_BY_POPULAR)
        except Exception as e:  # noqa: BLE001  -- one bad URL shouldn't kill the run
            print(f"  youtube skip {url}: {e}", file=sys.stderr)
            continue
        n = 0
        for c in gen:
            if n >= per_video:
                break
            txt = clean_text(c.get("text"))
            if not txt:
                continue
            out.append({
                "doc_id": f"yt_{c.get('cid', '')}",
                "source": "youtube",
                "platform": "youtube_comment",
                "url": url,
                "collected_at": now_iso(),
                "posted_date": "",  # library gives relative time ("2 years ago"); drop it
                "raw_text": txt,
                "language": lang,
                "rating": "",
                "extra": json.dumps({"votes": c.get("votes", "")}, ensure_ascii=False),
                "dedup_hash": dedup_hash(txt),
            })
            n += 1
        print(f"  youtube {url}: +{n}", file=sys.stderr)
    return out


def collect_reddit(per_query: int = 60) -> list[dict]:
    """Optional. Needs REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET env vars (free)."""
    import os

    import praw

    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent="myntra-discovery-engine/1.0 (research)",
    )
    subs = ["IndianFashionAddicts", "OnlineShoppingIndia", "india", "DesiFashion"]
    queries = ["Myntra size", "Myntra fit", "Myntra quality", "Myntra return",
               "Myntra original", "Myntra haul", "Myntra wishlist"]
    out = []
    for sub in subs:
        for q in queries:
            try:
                for post in reddit.subreddit(sub).search(q, limit=per_query, sort="relevance"):
                    body = clean_text(f"{post.title}. {post.selftext}")
                    if body:
                        out.append(_reddit_row(post.id, f"https://reddit.com{post.permalink}", body))
                    post.comments.replace_more(limit=0)
                    for cm in post.comments[:5]:
                        ctxt = clean_text(cm.body)
                        if ctxt and len(ctxt) > 15:
                            out.append(_reddit_row(cm.id, f"https://reddit.com{post.permalink}", ctxt))
            except Exception as e:  # noqa: BLE001
                print(f"  reddit skip {sub}/{q}: {e}", file=sys.stderr)
    return out


def _reddit_row(rid: str, url: str, txt: str) -> dict:
    return {
        "doc_id": f"rd_{rid}", "source": "reddit", "platform": "reddit_post",
        "url": url, "collected_at": now_iso(), "posted_date": "",
        "raw_text": txt, "language": "en", "rating": "",
        "extra": "{}", "dedup_hash": dedup_hash(txt),
    }


# ---------------------------------------------------------------- write / dedup
def dedup(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        h = r["dedup_hash"]
        if h in seen:
            continue
        seen.add(h)
        out.append(r)
    return out


def write_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RAW_COLUMNS)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- selftest
def _selftest() -> None:
    assert norm("  Hello   WORLD ") == "hello world"
    assert dedup_hash("a b") == dedup_hash(" A  B ")  # normalised dedup
    assert dedup_hash("a b") != dedup_hash("a c")
    rows = [_reddit_row("1", "u", "same text"), _reddit_row("2", "u", "SAME  text"),
            _reddit_row("3", "u", "different")]
    assert len(dedup(rows)) == 2, "dedup should collapse normalised duplicates"
    assert set(rows[0]) == set(RAW_COLUMNS), "row schema mismatch"
    print("selftest OK")


# ---------------------------------------------------------------- cli
def main() -> None:
    ap = argparse.ArgumentParser(description="Collect public Myntra user text -> raw_data.csv")
    ap.add_argument("-o", "--out", default="raw_data.csv")
    ap.add_argument("--play-count", type=int, default=2500, help="0 to skip Play Store")
    ap.add_argument("--also-relevant", type=int, default=0,
                    help="extra MOST_RELEVANT reviews to merge (longer, barrier-rich text)")
    ap.add_argument("--youtube", default="", help="file with 1 video URL per line (or comma list)")
    ap.add_argument("--per-video", type=int, default=300)
    ap.add_argument("--reddit", action="store_true", help="needs REDDIT_CLIENT_ID/SECRET")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    rows: list[dict] = []
    if args.play_count > 0:
        print(f"[play] newest target {args.play_count}", file=sys.stderr)
        rows += collect_play(args.play_count, sort="newest")
    if args.also_relevant > 0:
        print(f"[play] relevant target {args.also_relevant}", file=sys.stderr)
        rows += collect_play(args.also_relevant, sort="relevant")

    if args.youtube:
        try:
            with open(args.youtube, encoding="utf-8") as f:
                urls = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        except OSError:
            urls = [u.strip() for u in args.youtube.split(",") if u.strip()]
        print(f"[youtube] {len(urls)} videos", file=sys.stderr)
        rows += collect_youtube(urls, args.per_video)

    if args.reddit:
        print("[reddit] querying", file=sys.stderr)
        rows += collect_reddit()

    before = len(rows)
    rows = dedup(rows)
    write_csv(rows, args.out)
    print(f"\nWrote {len(rows)} rows to {args.out} (deduped {before - len(rows)}).")
    by_src: dict[str, int] = {}
    for r in rows:
        by_src[r["source"]] = by_src.get(r["source"], 0) + 1
    print("by source:", by_src)


if __name__ == "__main__":
    main()
