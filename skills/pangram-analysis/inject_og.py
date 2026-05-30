#!/usr/bin/env python3
"""
Inject Open Graph + Twitter Card meta tags into every essay and note.

The tags drive social previews on X, LinkedIn, Facebook, Slack, Discord,
iMessage, etc. og:image points at /api/og?title=…&excerpt=…&subtitle=…
which is rendered by api/og.tsx (Vercel Edge function, @vercel/og).

Idempotent: re-runs replace any prior auto-injected block, so adding
articles or editing title/excerpt re-emits the right tags.

Usage:
  python skills/pangram-analysis/inject_og.py            # all essays + notes
  python skills/pangram-analysis/inject_og.py path …     # specific files

This script does not call any API. It only reads/writes HTML on disk.
"""

from __future__ import annotations

import json
import os
import re
import sys
from html import escape, unescape
from pathlib import Path
from urllib.parse import quote

SITE = "https://cezarbabin.com"
TWITTER_HANDLE = "@sygmo1d"
METADATA_FILE = "metadata.json"

START = "<!-- og:auto-start -->"
END = "<!-- og:auto-end -->"


def find_blog_root() -> Path:
    for d in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
        if (d / "index.html").exists() and (d / "essays").is_dir():
            return d
    raise SystemExit("could not locate blog root")


def extract_title(html: str) -> str | None:
    # The post's <h1>…</h1> inside <main class="content post"> is the article
    # title (the site banner uses a <pre> inside the header <h1>, not text).
    m = re.search(
        r'<main[^>]*class="[^"]*\bpost\b[^"]*"[^>]*>\s*<h1[^>]*>(.*?)</h1>',
        html,
        re.DOTALL,
    )
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1)).strip()


def extract_first_paragraph(html: str) -> str | None:
    # First <p> inside .post that isn't .meta / .post-nav.
    body = re.search(
        r'<main[^>]*class="[^"]*\bpost\b[^"]*"[^>]*>(.*?)</main>',
        html,
        re.DOTALL,
    )
    if not body:
        return None
    chunk = body.group(1)
    for m in re.finditer(r'<p(?:\s+class="([^"]*)")?[^>]*>(.*?)</p>', chunk, re.DOTALL):
        cls = (m.group(1) or "").split()
        if "meta" in cls or "post-nav" in cls:
            continue
        text = re.sub(r"<[^>]+>", "", m.group(2))
        text = unescape(re.sub(r"\s+", " ", text)).strip()
        if text:
            return text
    return None


def article_subtitle(rel: Path) -> str:
    if rel.parts and rel.parts[0] == "notes":
        return "Note"
    return "Essay"


def article_url(rel: Path) -> str:
    # rel like essays/foo.html -> https://cezarbabin.com/essays/foo.html
    return f"{SITE}/{rel.as_posix()}"


def og_image_url(
    title: str,
    excerpt: str,
    subtitle: str,
    path: str,
    readtime: int | None = None,
) -> str:
    parts = [
        f"title={quote(title, safe='')}",
        f"excerpt={quote(excerpt, safe='')}",
        f"subtitle={quote(subtitle, safe='')}",
        f"path={quote(path, safe='/')}",
    ]
    if readtime is not None:
        parts.append(f"readtime={readtime}")
    return f"{SITE}/api/og?{'&'.join(parts)}"


def load_metadata(blog_root: Path) -> dict:
    p = blog_root / METADATA_FILE
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def article_readtime(meta: dict | None) -> int | None:
    if not meta:
        return None
    return meta.get("read_time_min")


def build_meta_block(title: str, description: str, url: str, image: str) -> str:
    # 2-space indent under <head>. Wrapped in the START/END markers for
    # idempotent re-injection.
    e = lambda s: escape(s, quote=True)
    lines = [
        START,
        f'<meta property="og:type" content="article">',
        f'<meta property="og:site_name" content="Cezar Babin">',
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(description)}">',
        f'<meta property="og:url" content="{e(url)}">',
        f'<meta property="og:image" content="{e(image)}">',
        f'<meta property="og:image:width" content="1200">',
        f'<meta property="og:image:height" content="630">',
        f'<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:site" content="{e(TWITTER_HANDLE)}">',
        f'<meta name="twitter:creator" content="{e(TWITTER_HANDLE)}">',
        f'<meta name="twitter:title" content="{e(title)}">',
        f'<meta name="twitter:description" content="{e(description)}">',
        f'<meta name="twitter:image" content="{e(image)}">',
        END,
    ]
    return "\n".join(lines)


AUTO_BLOCK_RE = re.compile(
    re.escape(START) + r".*?" + re.escape(END) + r"\n?",
    re.DOTALL,
)
HEAD_CLOSE_RE = re.compile(r"</head>")


def inject_into_head(html: str, block: str) -> str:
    # Strip any prior auto-block first.
    stripped = AUTO_BLOCK_RE.sub("", html)
    # Insert just before </head>, with a leading newline so indentation reads.
    return HEAD_CLOSE_RE.sub(f"{block}\n</head>", stripped, count=1)


def process(path: Path, blog_root: Path, metadata: dict) -> bool:
    rel = path.relative_to(blog_root)
    if rel.name == "test-post.html":
        print(f"SKIP test fixture: {rel}")
        return False
    html = path.read_text()
    title = extract_title(html)
    excerpt = extract_first_paragraph(html) or ""
    if not title:
        print(f"SKIP (no <h1>): {rel}")
        return False
    subtitle = article_subtitle(rel)
    url = article_url(rel)
    rt = article_readtime(metadata.get(str(rel)))
    article_path = "/" + rel.as_posix()
    image = og_image_url(title, excerpt, subtitle, article_path, rt)
    block = build_meta_block(title, excerpt, url, image)
    new_html = inject_into_head(html, block)
    if new_html != html:
        path.write_text(new_html)
        print(f"INJECTED: {rel}  (rt={rt})")
        return True
    print(f"unchanged: {rel}")
    return False


def discover(blog_root: Path) -> list[Path]:
    out = []
    for sub in ("essays", "notes"):
        d = blog_root / sub
        if d.is_dir():
            out.extend(sorted(d.glob("*.html")))
    return out


def main() -> None:
    blog_root = find_blog_root()
    os.chdir(blog_root)
    metadata = load_metadata(blog_root)
    args = sys.argv[1:]
    targets = (
        [Path(a).resolve() for a in args]
        if args
        else [blog_root / r for r in [p.relative_to(blog_root) for p in discover(blog_root)]]
    )
    changed = 0
    for path in targets:
        if process(path, blog_root, metadata):
            changed += 1
    print(f"\n{changed} file(s) updated.")


if __name__ == "__main__":
    main()
