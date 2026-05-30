// Vercel Edge function: renders a 1080×1350 portrait card from a paragraph.
// Designed for sharing on X / Instagram / LinkedIn — portrait orientation
// reads well on phones, the size works on every platform.
//
// URL pattern:
//   /api/quote?text=<url-encoded paragraph>&title=<article title>
//
// Auto-scales font size to text length so short quotes feel like pull-quotes
// and long passages still fit cleanly.

import { ImageResponse } from "@vercel/og";

export const config = {
  runtime: "edge",
};

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
    throw new Error(`CSS fetch failed ${cssResp.status}`);
  }
  const css = await cssResp.text();
  const m = css.match(
    /url\((https:\/\/fonts\.gstatic\.com\/[^)]+\.(?:woff2|woff|ttf|otf))\)/i
  );
  if (!m) throw new Error(`no font URL in CSS for ${family} ${weight}`);
  const fontResp = await fetch(m[1]);
  if (!fontResp.ok) throw new Error(`font fetch failed ${fontResp.status}`);
  return fontResp.arrayBuffer();
}

function fontSizeForLength(len: number): number {
  if (len <= 180) return 50;
  if (len <= 280) return 44;
  if (len <= 400) return 38;
  if (len <= 550) return 34;
  if (len <= 750) return 30;
  return 26;
}

export default async function handler(req: Request) {
  const url = new URL(req.url);
  const text = (url.searchParams.get("text") || "").slice(0, 1200);
  const title = (url.searchParams.get("title") || "").slice(0, 140);

  const fontSize = fontSizeForLength(text.length);

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
          backgroundColor: "#ffffff",
          padding: "80px",
          fontFamily: '"Open Sans"',
          color: "#000000",
        }}
      >
        {/* Top: domain */}
        <div
          style={{
            display: "flex",
            fontSize: 30,
            fontWeight: 600,
            color: "#2d993e",
            letterSpacing: -0.3,
          }}
        >
          cezarbabin.com
        </div>

        {/* Divider under the header */}
        <div
          style={{
            width: "100%",
            height: 1,
            backgroundColor: "rgba(89, 104, 93, 0.22)",
            display: "flex",
            marginTop: 22,
          }}
        />

        {/* Highlighted quote — wrapped in a soft yellow "marker stroke"
            block so the card reads like a screenshot of a highlighted
            passage. Padding gives the text room inside the highlight. */}
        <div
          style={{
            display: "flex",
            flex: 1,
            flexDirection: "column",
            justifyContent: "center",
            paddingTop: 36,
            paddingBottom: 36,
          }}
        >
          <div
            style={{
              display: "flex",
              backgroundColor: "#FEF08A",
              padding: "36px 42px",
              borderRadius: 4,
            }}
          >
            <div
              style={{
                fontSize,
                fontWeight: 400,
                lineHeight: 1.45,
                color: "#000000",
                letterSpacing: -0.2,
                display: "-webkit-box",
                WebkitLineClamp: 18,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {text}
            </div>
          </div>
        </div>

        {/* Attribution: divider + "from <title>" */}
        {title && (
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div
              style={{
                width: "100%",
                height: 1,
                backgroundColor: "rgba(89, 104, 93, 0.22)",
                display: "flex",
                marginBottom: 24,
              }}
            />
            <div
              style={{
                display: "flex",
                fontSize: 24,
                color: "#5d5d5d",
                fontStyle: "italic",
                lineHeight: 1.3,
              }}
            >
              from “{title}”
            </div>
          </div>
        )}
      </div>
    ),
    {
      width: 1080,
      height: 1350,
      fonts: [
        { name: "Open Sans", data: regular, weight: 400, style: "normal" },
        { name: "Open Sans", data: semibold, weight: 600, style: "normal" },
      ],
      headers: {
        "cache-control": "public, immutable, no-transform, max-age=86400",
      },
    }
  );
}
