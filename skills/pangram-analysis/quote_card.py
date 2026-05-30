#!/usr/bin/env python3
"""
Generate a shareable mobile-friendly quote card from any paragraph.

Usage:
  # Pipe text in, give an article title
  echo "The paragraph to share." | \\
      python skills/pangram-analysis/quote_card.py \\
        --title "ChatGPT is the new browser and memory is the new cookie"

  # Or pass --text directly (good for short quotes)
  python skills/pangram-analysis/quote_card.py \\
      --title "Some essay" \\
      --text "The text here."

  # Save the PNG locally as well
  python skills/pangram-analysis/quote_card.py --title "..." --out card.png

Prints the share URL to stdout. With --open it opens the PNG in Preview.
With --out PATH it also downloads the PNG to that path.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

SITE = "https://cezarbabin.com"


def build_url(text: str, title: str) -> str:
    parts = [f"text={quote(text, safe='')}"]
    if title:
        parts.append(f"title={quote(title, safe='')}")
    return f"{SITE}/api/quote?{'&'.join(parts)}"


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--title", required=True, help="article title for attribution")
    ap.add_argument("--text", help="quote text (if omitted, reads from stdin)")
    ap.add_argument("--out", type=Path, help="download the PNG to this path")
    ap.add_argument("--open", action="store_true", help="open the PNG in Preview after generating (implies --out to a temp file)")
    args = ap.parse_args()

    text = args.text if args.text is not None else sys.stdin.read()
    text = text.strip()
    if not text:
        ap.error("no text provided (use --text or pipe via stdin)")

    url = build_url(text, args.title)
    print(url)

    out_path = args.out
    if args.open and not out_path:
        out_path = Path("/tmp/quote_card.png")

    if out_path:
        with urlopen(url, timeout=60) as resp:
            out_path.write_bytes(resp.read())
        print(f"saved: {out_path}", file=sys.stderr)
        if args.open and sys.platform == "darwin":
            subprocess.run(["open", str(out_path)], check=False)


if __name__ == "__main__":
    main()
