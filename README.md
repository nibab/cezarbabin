# cezarbabin.com

Personal blog. Static HTML/CSS, no build step.

## Local dev

```sh
python3 -m http.server 4000
# open http://localhost:4000/
```

## Deploy

Hosted on Vercel. Production deploys land on `https://cezarbabin.com`.
Pushing to `main` triggers a deploy. Pull requests get preview URLs.

## Layout

- `index.html` — essays list (landing)
- `about.html`, `projects.html` — top-level pages
- `essays/*.html` — one file per post (sluggified filename)
- `style.css` — single stylesheet, all tokens centralized
- `vercel.json`, `robots.txt`, `sitemap.xml` — host config + SEO
- `essays/test-post.html` — local-only test fixture (hidden via `.local-only`
  CSS class on the index entry, and redirected to `/` when accessed on any
  non-local hostname)

## Adding a post

1. Copy any file in `essays/`, edit `<title>`, `<h1>`, `<p class="meta">`, body.
2. Add a matching `<li>` to the essays list in `index.html`.
3. Add a `<url>` entry to `sitemap.xml`.

## Analytics

Vercel Analytics. Page views are auto-tracked. Outbound link clicks fire an
`outbound_click` custom event (see the inline script at the end of each page).
