#!/usr/bin/env python3
"""
Pangram analysis for blog articles.

For each essay (essays/*.html) or note (notes/*.html) it:
  1. Extracts the body text (paragraphs inside <main class="content post">)
  2. Counts words and computes reading time at 225 wpm
  3. Calls Pangram v3 to get fraction_human / fraction_ai / fraction_ai_assisted
  4. Injects a ` · N min read · H% human` segment into the article's meta line
  5. Caches everything in metadata.json at the blog root so re-runs are cheap

Usage:
  ./analyze.py essays/foo.html [notes/bar.html ...]    # specific files
  ./analyze.py --all                                   # all essays + notes (skip cached)
  ./analyze.py --all --force                           # re-analyze everything
  ./analyze.py --report                                # print cached table

API key (looked up in this order):
  1. $PANGRAM_API_KEY env var
  2. ~/.pangram_key file (one line, chmod 600)

The cache and the injected meta segments are idempotent — re-running on an
already-analyzed file is a no-op unless --force is passed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

PANGRAM_ENDPOINT = "https://text.api.pangram.com/v3"
WORDS_PER_MIN = 225
METADATA_FILE = "metadata.json"
SKILL_VERSION = "1"


# -------- locate blog root + secrets ---------------------------------------

def find_blog_root() -> Path:
    """Walk upward from this script until we find index.html + essays/."""
    for d in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
        if (d / "index.html").exists() and (d / "essays").is_dir():
            return d
    raise SystemExit("ERROR: could not locate blog root (need index.html + essays/ nearby)")


def load_api_key() -> str:
    env = os.environ.get("PANGRAM_API_KEY", "").strip()
    if env:
        return env
    key_path = Path.home() / ".pangram_key"
    if key_path.exists():
        return key_path.read_text().strip()
    raise SystemExit(
        "ERROR: Pangram API key not found.\n"
        "  Set $PANGRAM_API_KEY or write the key to ~/.pangram_key (chmod 600)."
    )


# -------- HTML body extraction ---------------------------------------------

class PostBodyExtractor(HTMLParser):
    """
    Extract human-visible body text from an essay/note page.

    Reads only <p> elements inside <main class="content post"> that are NOT
    .meta (the date line) or .post-nav (the back link), and skips tweet
    blockquotes + the title <h1>.
    """

    SKIP_TAGS = {"script", "style", "blockquote", "h1"}
    SKIP_P_CLASSES = ("meta", "post-nav")

    def __init__(self) -> None:
        super().__init__()
        self.in_main: bool = False
        self.skip_depth: int = 0
        self.in_para: bool = False
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "main" and "post" in d.get("class", "").split():
            self.in_main = True
            return
        if not self.in_main:
            return
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if tag == "p":
            classes = d.get("class", "").split()
            if not any(c in classes for c in self.SKIP_P_CLASSES):
                self.in_para = True

    def handle_endtag(self, tag):
        if not self.in_main:
            return
        if tag in self.SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1
            return
        if tag == "p" and self.in_para:
            self.in_para = False
            self.parts.append("\n")
        elif tag == "main":
            self.in_main = False

    def handle_data(self, data):
        if self.in_main and self.skip_depth == 0 and self.in_para:
            self.parts.append(data)


def extract_body_text(html: str) -> str:
    p = PostBodyExtractor()
    p.feed(html)
    return re.sub(r"[ \t]+", " ", "".join(p.parts)).strip()


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def read_minutes(words: int) -> int:
    return max(1, round(words / WORDS_PER_MIN))


# -------- Pangram client ---------------------------------------------------

def pangram_call(text: str, api_key: str, retries: int = 3) -> dict:
    payload = json.dumps({"text": text}).encode("utf-8")
    headers = {"Content-Type": "application/json", "x-api-key": api_key}
    last_err: dict = {"error": "unreachable"}
    for attempt in range(retries):
        try:
            req = urlrequest.Request(
                PANGRAM_ENDPOINT, data=payload, headers=headers, method="POST"
            )
            with urlrequest.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urlerror.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            last_err = {"error": f"HTTP {e.code}", "body": body[:500]}
            if e.code < 500:  # don't retry 4xx
                return last_err
        except urlerror.URLError as e:
            last_err = {"error": f"URL error: {e}"}
        time.sleep(1 + attempt)
    return last_err


# -------- HTML meta-line injection (idempotent) ----------------------------

INJECT_RE = re.compile(r"\s*·\s*\d+\s*min\s*read[^<]*?(?=</p>|$)", re.IGNORECASE)


def inject_meta_line(
    html: str,
    mins: int,
    human_pct: int | None = None,
    ai_pct: int | None = None,
) -> str:
    """
    Add ` · N min read[ · H% human[ · A% AI]]` to the article's first
    <p class="meta">…</p> after <h1>. Idempotent: any prior injection of this
    same shape is stripped before the new value is appended. When Pangram data
    isn't available (human_pct is None), only the reading-time segment lands.
    """
    tail = f"{mins} min read"
    if human_pct is not None:
        tail += f" · {human_pct}% human"
        if ai_pct is not None and ai_pct >= 5:
            tail += f" · {ai_pct}% AI"

    meta_pat = re.compile(
        r'(<h1>[^<]+</h1>\s*<p class="meta">)([^<]*)(</p>)', re.DOTALL
    )
    m = meta_pat.search(html)
    if not m:
        return html
    existing = INJECT_RE.sub("", m.group(2)).rstrip()
    new_meta = f"{existing} · {tail}"
    return html[: m.start(2)] + new_meta + html[m.end(2) :]


# -------- targets ----------------------------------------------------------

def discover_targets(blog_root: Path) -> list[Path]:
    out: list[Path] = []
    for sub in ("essays", "notes"):
        d = blog_root / sub
        if d.is_dir():
            out.extend(sorted(d.glob("*.html")))
    return out


def is_test_fixture(rel: Path) -> bool:
    return rel.name == "test-post.html"


def normalize_target(blog_root: Path, raw: str) -> Path | None:
    p = Path(raw)
    if not p.is_absolute():
        p = (blog_root / p).resolve()
    try:
        return p.resolve().relative_to(blog_root)
    except ValueError:
        return None


# -------- main -------------------------------------------------------------

def cmd_report(metadata: dict) -> None:
    if not metadata:
        print("(metadata.json is empty — run --all to populate)")
        return
    print(f"{'article':<55} {'words':>6} {'min':>4} {'%human':>7} {'%AI':>5}")
    print("-" * 80)
    for k in sorted(metadata):
        m = metadata[k]
        pg = m.get("pangram", {})
        h = round(100 * pg["fraction_human"]) if pg.get("fraction_human") is not None else "?"
        a = round(100 * ((pg.get("fraction_ai") or 0) + (pg.get("fraction_ai_assisted") or 0))) if pg.get("fraction_ai") is not None else "?"
        print(f"{k:<55} {m.get('words','?'):>6} {m.get('read_time_min','?'):>4} {h:>7} {a:>5}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("paths", nargs="*", help="article paths (relative to blog root, or absolute)")
    parser.add_argument("--all", action="store_true", help="analyze all essays + notes")
    parser.add_argument("--force", action="store_true", help="re-analyze even if cached")
    parser.add_argument("--report", action="store_true", help="print cached metadata table")
    args = parser.parse_args()

    blog_root = find_blog_root()
    os.chdir(blog_root)

    meta_path = blog_root / METADATA_FILE
    metadata: dict = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    if args.report:
        cmd_report(metadata)
        return

    if args.all:
        rel_targets = [t.relative_to(blog_root) for t in discover_targets(blog_root)]
    elif args.paths:
        rel_targets = []
        for raw in args.paths:
            rel = normalize_target(blog_root, raw)
            if rel is None:
                print(f"SKIP (not under blog root): {raw}")
                continue
            rel_targets.append(rel)
    else:
        parser.print_usage()
        sys.exit(1)

    api_key = load_api_key()

    for rel in rel_targets:
        key = str(rel)
        if is_test_fixture(rel):
            print(f"SKIP test fixture: {key}")
            continue
        full = blog_root / rel
        if not full.exists():
            print(f"MISSING:           {key}")
            continue

        cached = metadata.get(key, {})
        pangram_done = (
            "pangram" in cached
            and cached["pangram"].get("fraction_human") is not None
        )

        # Reading-time + word-count are deterministic from the file. Always
        # compute + inject them; Pangram is the slow / paid step that we cache.
        html = full.read_text()
        text = extract_body_text(html)
        wc = word_count(text)
        rm = read_minutes(wc)

        if not args.force and pangram_done and cached.get("words") == wc:
            print(f"SKIP cached:       {key}  (words={wc}, pangram on file)")
            continue

        pangram_data = cached.get("pangram") if pangram_done else None
        h_pct = a_pct = None

        if not pangram_done or args.force:
            print(f"PANGRAM CALL:      {key}  ({wc} words, ~{rm} min)")
            resp = pangram_call(text, api_key)
            if "error" in resp:
                # Word count + read time still land; Pangram retries on next run.
                print(
                    f"  WARN pangram unavailable: {resp.get('error')} "
                    f"body={resp.get('body','')[:120]}"
                )
            else:
                pangram_data = {
                    "fraction_human": resp.get("fraction_human"),
                    "fraction_ai": resp.get("fraction_ai"),
                    "fraction_ai_assisted": resp.get("fraction_ai_assisted"),
                    "prediction_short": resp.get("prediction_short"),
                    "headline": resp.get("headline"),
                }

        if pangram_data and pangram_data.get("fraction_human") is not None:
            h_pct = round(100 * pangram_data["fraction_human"])
            a_pct = round(
                100
                * ((pangram_data.get("fraction_ai") or 0)
                   + (pangram_data.get("fraction_ai_assisted") or 0))
            )

        new_html = inject_meta_line(html, rm, h_pct, a_pct)
        if new_html != html:
            full.write_text(new_html)

        entry = {
            "words": wc,
            "read_time_min": rm,
            "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "skill_version": SKILL_VERSION,
        }
        if pangram_data:
            entry["pangram"] = pangram_data
        metadata[key] = entry

        label = f"{rm} min · {wc} words"
        if h_pct is not None:
            label += f" · {h_pct}% human"
            if a_pct >= 5:
                label += f" · {a_pct}% AI"
        else:
            label += " · pangram pending"
        print(f"  OK  {label}")

    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print(f"\nWrote {meta_path.name}")


if __name__ == "__main__":
    main()
