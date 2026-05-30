#!/usr/bin/env python3
"""
Take a mobile-viewport screenshot of an essay/note with a passage highlighted.

Uses Playwright (Chromium, headless) to load the real article, find the
passage, wrap it in a yellow <mark>, scroll it into view, and screenshot.

Setup (one-time per machine):
    pip install playwright
    playwright install chromium

Examples:
    # By full URL
    python take_screenshot.py \\
        --url https://cezarbabin.com/essays/chatgpt-is-the-new-browser.html \\
        --text "In the same way that cookies allowed Google" \\
        --out screenshots/quote.png --open

    # By essay slug (resolves against cezarbabin.com)
    python take_screenshot.py \\
        --essay essays/chatgpt-is-the-new-browser.html \\
        --text "memory helps OpenAI own the personalization layer" \\
        --out screenshots/memory-cookie.png

Local-only — never deployed to Vercel.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sys.exit(
        "ERROR: playwright not installed.\n"
        "  pip install playwright && playwright install chromium"
    )


SITE = "https://cezarbabin.com"

# Logical (CSS) pixel viewport presets. Output PNG dimensions are these
# multiplied by --dpi.
VIEWPORTS: dict[str, tuple[int, int]] = {
    "iphone15pro":    (393, 852),
    "iphone15promax": (430, 932),
    "iphone14":       (390, 844),
    "pixel8":         (412, 915),
    "tall":           (430, 1200),
}

# Mobile Safari UA so the site loads its mobile breakpoints (max-width: 600px
# in style.css). Without this, Vercel/CDN may serve a desktop-y experience.
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)

# JS that finds and highlights the passage. Wraps the first matching
# substring in a <mark>, then scrolls it into view. Returns true on success.
HIGHLIGHT_JS = r"""
(args) => {
  const {target, color} = args;
  const SKIP_SEL =
    'script, style, .site-header, .site-nav, .site-footer, .ascii-banner, .meta, .post-nav';

  function* textNodes(root) {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        if (!node.parentElement) return NodeFilter.FILTER_REJECT;
        if (node.parentElement.closest(SKIP_SEL)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    let n;
    while ((n = w.nextNode())) yield n;
  }

  for (const node of textNodes(document.body)) {
    const idx = node.textContent.indexOf(target);
    if (idx === -1) continue;
    const range = document.createRange();
    range.setStart(node, idx);
    range.setEnd(node, idx + target.length);
    const mark = document.createElement('mark');
    mark.setAttribute('data-shot-highlight', '1');
    mark.style.backgroundColor = color;
    mark.style.padding = '2px 1px';
    mark.style.borderRadius = '2px';
    mark.style.boxDecorationBreak = 'clone';
    mark.style.webkitBoxDecorationBreak = 'clone';
    try {
      range.surroundContents(mark);
      mark.scrollIntoView({block: 'center', behavior: 'instant'});
      return true;
    } catch (e) {
      // surroundContents fails if the range crosses element boundaries
      // (e.g. an <em> inside the passage). Fallback: highlight just the
      // first text-node slice — caller may need a tighter --text.
      const span = document.createElement('mark');
      span.style.cssText = mark.style.cssText;
      const sliced = node.splitText(idx);
      sliced.splitText(target.length);
      sliced.parentNode.replaceChild(span, sliced);
      span.appendChild(sliced);
      span.scrollIntoView({block: 'center', behavior: 'instant'});
      return true;
    }
  }
  return false;
}
"""


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="full article URL")
    src.add_argument(
        "--essay",
        help="article path relative to site root (e.g. essays/foo.html)",
    )
    ap.add_argument("--text", required=True, help="substring to highlight")
    ap.add_argument("--out", type=Path, required=True, help="output PNG path")
    ap.add_argument(
        "--viewport", default="iphone15pro", choices=list(VIEWPORTS), help="phone preset"
    )
    ap.add_argument(
        "--dpi", type=int, default=2, choices=[1, 2, 3], help="device scale factor"
    )
    ap.add_argument("--color", default="#FEF08A", help="highlight hex color")
    ap.add_argument(
        "--full-page",
        action="store_true",
        help="screenshot the whole article instead of viewport only",
    )
    ap.add_argument(
        "--open", action="store_true", help="open the PNG in Preview (macOS)"
    )
    args = ap.parse_args()

    target_url = args.url or f"{SITE}/{args.essay.lstrip('/')}"
    width, height = VIEWPORTS[args.viewport]
    out = args.out.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"→ {target_url}")
    print(f"  viewport={width}×{height}  dpi={args.dpi}  color={args.color}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=args.dpi,
            user_agent=MOBILE_UA,
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()
        page.goto(target_url, wait_until="networkidle", timeout=30000)
        # Wait for web fonts to settle so the highlight scroll-into-view
        # lands on stable layout coordinates.
        page.evaluate("() => document.fonts.ready")
        page.wait_for_timeout(250)

        found = page.evaluate(
            HIGHLIGHT_JS, {"target": args.text, "color": args.color}
        )
        if not found:
            browser.close()
            sys.exit(
                f"ERROR: passage not found on the page.\n"
                f"  searched for: {args.text!r}\n"
                f"  on: {target_url}\n"
                f"  tip: try a shorter substring (no internal HTML like <em>)."
            )

        # Brief settle after scrollIntoView
        page.wait_for_timeout(150)
        page.screenshot(path=str(out), full_page=args.full_page)
        browser.close()

    px_w = width * args.dpi
    px_h = (None if args.full_page else height) and height * args.dpi
    print(f"saved: {out}  ({px_w}×{px_h or 'full-page'} px)")

    if args.open and sys.platform == "darwin":
        subprocess.run(["open", str(out)], check=False)


if __name__ == "__main__":
    main()
