# Pangram analysis

Compute **word count**, **reading time**, and **Pangram AI-content score**
(`fraction_human` / `fraction_ai` / `fraction_ai_assisted`) for each blog
article. Inject the result into the article's meta line and cache it in
`metadata.json` at the blog root.

## When to invoke (trigger guidance for agents)

Invoke this skill whenever **either** is true:

1. A new `essays/*.html` or `notes/*.html` file is added to the repo.
2. The user explicitly asks for a re-analysis after substantively editing an article.

Do **not** invoke it on incidental edits (nav tweaks, footer changes, typo
fixes, link swaps). Pangram is paid per call; the cache (`metadata.json`)
prevents accidental re-runs.

## How to invoke

```sh
# Single new article (or several)
python skills/pangram-analysis/analyze.py essays/foo.html notes/bar.html

# Catch up on anything not yet in the cache
python skills/pangram-analysis/analyze.py --all

# Force re-analyze (after a substantive prose edit)
python skills/pangram-analysis/analyze.py --all --force
python skills/pangram-analysis/analyze.py essays/foo.html --force

# Just show the cached table
python skills/pangram-analysis/analyze.py --report
```

## What it does to the article HTML

It edits the first `<p class="meta">` after the article's `<h1>`, appending
`· {min} min read · {human}% human` (and `· {ai}% AI` when AI content is
≥ 5%). Example:

```
Before:   <p class="meta">May 28, 2026 · Note</p>
After:    <p class="meta">May 28, 2026 · Note · 5 min read · 97% human</p>
```

Re-runs are idempotent: the old segment is stripped before the fresh one is
appended, so running `--force` won't pile up multiple read-time pills.

## What it writes

- The article HTML (in place — commit it)
- `metadata.json` at the blog root (commit it; it's the cache)

## What it never writes

- **The API key.** The key lives at `~/.pangram_key` (chmod 600) or
  `$PANGRAM_API_KEY`. Both are explicitly gitignored. If the env var is
  unset and the file is missing, the script exits with an error rather than
  proceeding.

## API key setup (one-time per machine)

```sh
printf 'YOUR-KEY-UUID' > ~/.pangram_key
chmod 600 ~/.pangram_key
```

Or set `PANGRAM_API_KEY` in your shell profile. The env var wins if both are set.

## Reading-speed and threshold knobs

- `WORDS_PER_MIN = 225` — average adult prose reading speed.
- AI display threshold: only shown when combined `fraction_ai + fraction_ai_assisted` ≥ 5%.

Change either at the top of `analyze.py`.

## Test fixture

`essays/test-post.html` is skipped automatically (it's local-only and
doesn't represent real content).
