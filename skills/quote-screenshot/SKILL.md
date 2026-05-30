# Quote screenshot (Playwright, local-only)

Generate a mobile-viewport screenshot of an essay or note with a specific
passage highlighted in yellow. Output is a **real screenshot of the
rendered article** — real fonts, real layout, real chrome — not a
synthesized card.

This is the right approach for sharing quotes on X / Instagram /
LinkedIn: it feels like the person actually highlighted something on
their phone and shared the screenshot.

## When to use

When the user wants to share a passage from an article and wants it to
look like an authentic phone screenshot, with their highlight on it.

## When NOT to use

- For link-unfurl preview cards on social media — use `api/og.tsx`
  (auto-injected via `inject_og.py`).
- For synthesized typographic pull-quotes — use `api/quote.tsx` +
  `skills/pangram-analysis/quote_card.py`.

This skill is the third option: real-browser screenshots for the
"highlight + screenshot + post" workflow.

## Local-only

This skill is **never deployed to Vercel**. Playwright is heavy (~300 MB
of browser binaries) and we don't want it in the deploy. It's a
developer-machine tool.

- `package.json` does NOT include playwright.
- Output PNGs land in `screenshots/` at the repo root, which is
  `.gitignore`d. Nothing the skill produces gets committed.

## Setup (one-time per machine)

```sh
pip install playwright
playwright install chromium
```

That's all. Restart not required.

## Usage

```sh
python skills/quote-screenshot/take_screenshot.py \
    --url https://cezarbabin.com/essays/chatgpt-is-the-new-browser.html \
    --text "In the same way that cookies allowed Google" \
    --out screenshots/chatgpt-quote.png
```

`--text` is a substring search against article body text. Pass enough of
the passage to be unique; the first match wins. The whole substring you
pass is what gets wrapped in `<mark>` — so to highlight a full sentence,
paste the full sentence; to highlight one phrase, paste just that.

### Useful flags

| Flag | Default | What |
|---|---|---|
| `--viewport` | `iphone15pro` | Phone preset. Options: `iphone15pro` (393×852), `iphone15promax` (430×932), `iphone14` (390×844), `pixel8` (412×915), `tall` (430×1200, extra vertical room) |
| `--dpi` | `2` | Device scale factor (1–3). Higher = sharper text, bigger file |
| `--color` | `#FEF08A` | Highlight background hex. Try `#DCFCE7` for soft Pentalist green |
| `--full-page` | off | Capture the whole article instead of just the visible viewport |
| `--open` | off | Open the resulting PNG in Preview after generating (macOS) |

### Convenience: pass an essay slug

```sh
python skills/quote-screenshot/take_screenshot.py \
    --essay essays/chatgpt-is-the-new-browser.html \
    --text "memory helps OpenAI own the personalization layer" \
    --out screenshots/memory-cookie.png --open
```

`--essay` resolves to `https://cezarbabin.com/<that path>` automatically,
so you don't have to type the full URL.

### Local preview vs production

By default the skill loads from `cezarbabin.com` (production). To screenshot
a local dev preview (`python3 -m http.server 4000` in this directory):

```sh
python skills/quote-screenshot/take_screenshot.py \
    --url http://localhost:4000/essays/chatgpt-is-the-new-browser.html \
    --text "..." --out screenshots/local.png
```

## How the highlighting works

The script injects JS that walks text nodes inside the article body,
finds the first substring match, wraps it in a `<mark>` with a yellow
background and a sliver of padding, scrolls the `<mark>` into the
vertical center of the viewport, and screenshots.

It deliberately skips text inside `.site-header`, `.site-nav`,
`.site-footer`, and the `.ascii-banner` so the highlight only lands on
real prose, not on nav/branding text.

## Why this skill exists alongside `/api/quote`

| Pipeline | Best for | Visual style |
|---|---|---|
| `api/og.tsx` (Edge function) | Link-unfurl OG previews (auto-fired) | 1200×630 landscape card |
| `api/quote.tsx` (Edge function) | Synthesized pull-quote sharable image | 1080×1350 portrait card on white |
| **This skill** (local Playwright) | "I highlighted this while reading" screenshot for social | Mobile viewport, real article rendering, yellow `<mark>` |

The three serve different goals; this skill rounds out the social-share
toolkit by giving the user an authentic-feeling screenshot.
