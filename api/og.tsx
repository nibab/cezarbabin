// Vercel Edge function: generates a 1200×630 OG image per article.
//
// Each article's <head> points at /api/og?title=…&excerpt=…&subtitle=…
// Twitter / Facebook / LinkedIn / Slack / Discord all read this URL.
//
// Styled to match the Pentalist-derived theme:
//   - Open Sans (fetched from jsDelivr's google/fonts mirror, cached at the edge)
//   - black headline, gray excerpt, green domain footer
//   - hairline divider that echoes the in-site .divider rule

import { ImageResponse } from "@vercel/og";

export const config = {
  runtime: "edge",
};

// Fonts: resolved via Google Fonts' CSS API so we get whichever URL is
// currently published (gstatic version numbers rotate a few times a year).
// We accept WOFF2 / WOFF / TTF — @vercel/og (Satori) handles all three.
async function loadGoogleFont(
  family: string,
  weight: number
): Promise<ArrayBuffer> {
  const cssUrl = `https://fonts.googleapis.com/css2?family=${family.replace(
    / /g,
    "+"
  )}:wght@${weight}`;
  const cssResp = await fetch(cssUrl, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    },
  });
  if (!cssResp.ok) {
    throw new Error(`CSS fetch failed ${cssResp.status} for ${cssUrl}`);
  }
  const css = await cssResp.text();
  const m = css.match(
    /url\((https:\/\/fonts\.gstatic\.com\/[^)]+\.(?:woff2|woff|ttf|otf))\)/i
  );
  if (!m) {
    throw new Error(
      `no font URL in CSS for ${family} ${weight} — first 200 chars: ${css.slice(
        0,
        200
      )}`
    );
  }
  const fontResp = await fetch(m[1]);
  if (!fontResp.ok) {
    throw new Error(`font fetch failed ${fontResp.status} ${m[1]}`);
  }
  return fontResp.arrayBuffer();
}

function trimTo(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max - 1).replace(/\s+\S*$/, "") + "…";
}

export default async function handler(req: Request) {
  const url = new URL(req.url);
  const title = trimTo(
    url.searchParams.get("title") || "Cezar Babin",
    120
  );
  const excerpt = trimTo(
    url.searchParams.get("excerpt") || "",
    220
  );
  const subtitle = (url.searchParams.get("subtitle") || "").slice(0, 40);

  // Optional analytics injected by inject_og.py from metadata.json.
  const readtime = url.searchParams.get("readtime") || "";

  const [regular, semibold] = await Promise.all([
    loadGoogleFont("Open Sans", 400),
    loadGoogleFont("Open Sans", 600),
  ]);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          backgroundColor: "#ffffff",
          padding: "60px 72px",
          fontFamily: '"Open Sans"',
          color: "#000000",
        }}
      >
        {/* Top: site mark */}
        <div
          style={{
            display: "flex",
            fontSize: 28,
            fontWeight: 400,
            color: "#5d5d5d",
            letterSpacing: -0.5,
          }}
        >
          cezar babin
        </div>

        {/* Middle: title + excerpt */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 24,
            marginTop: 12,
            marginBottom: 12,
          }}
        >
          <div
            style={{
              fontSize: title.length > 60 ? 56 : 68,
              fontWeight: 600,
              lineHeight: 1.12,
              letterSpacing: -1.5,
              color: "#000000",
              // Hard-cap to 3 lines so the card always lays out the same
              display: "-webkit-box",
              WebkitLineClamp: 3,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {title}
          </div>
          {excerpt && (
            <div
              style={{
                fontSize: 26,
                lineHeight: 1.5,
                color: "#5d5d5d",
                display: "-webkit-box",
                WebkitLineClamp: 3,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {excerpt}
            </div>
          )}
        </div>

        {/* Bottom: hairline divider + footer row */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div
            style={{
              width: "100%",
              height: 1,
              backgroundColor: "rgba(89, 104, 93, 0.22)",
              display: "flex",
            }}
          />
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              fontSize: 22,
            }}
          >
            <div style={{ display: "flex", color: "#2d993e", fontWeight: 600 }}>
              cezarbabin.com
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 14,
                color: "#5d5d5d",
              }}
            >
              {readtime && (
                <div style={{ display: "flex" }}>{readtime} min read</div>
              )}
              {subtitle && (
                <div style={{ display: "flex", opacity: 0.7 }}>· {subtitle}</div>
              )}
            </div>
          </div>
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
      fonts: [
        { name: "Open Sans", data: regular, weight: 400, style: "normal" },
        { name: "Open Sans", data: semibold, weight: 600, style: "normal" },
      ],
      // 24h cache — the same params always render the same image
      headers: {
        "cache-control": "public, immutable, no-transform, max-age=86400",
      },
    }
  );
}
