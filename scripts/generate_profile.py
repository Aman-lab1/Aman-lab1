import html
import io
import math
import os
import re
import textwrap
import time
from datetime import datetime, timedelta, timezone
import requests
from PIL import Image, ImageEnhance, ImageFilter

USERNAME = os.getenv("GITHUB_USERNAME", "Aman-lab1")
TOKEN = os.getenv("GITHUB_TOKEN", "")
HEADERS = {"Accept": "application/vnd.github+json"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

FLAGSHIP_META = {
    "Quadruped107": {
        "desc": "8-joint autonomous quadruped robot and PyBullet kinematic twin.",
        "stack": "Python · C++ · PyBullet",
    },
    "Folio": {
        "desc": "Offline-first personal and business finance PWA with IndexedDB.",
        "stack": "JavaScript · IndexedDB · PWA",
    },
    "LaserLink": {
        "desc": "Free-space OOK laser transceiver on Arduino for audio packet transfer.",
        "stack": "C++ · Arduino · OOK Protocol",
    },
    "Pebble": {
        "desc": "Minimalist expense tracker with category insights and visual summaries.",
        "stack": "JavaScript · HTML5 · CSS3",
    },
    "Memento": {
        "desc": "Mobile-first peer-to-peer lending ledger with net balance auditing.",
        "stack": "JavaScript · LocalStorage · PWA",
    },
    "Verdant-Vellum": {
        "desc": "Storefront showcase for dark academia & botanical digital collections.",
        "stack": "HTML5 · CSS3 · GitHub Pages",
    },
}

LANG_SHORT = {
    "JavaScript": "JS",
    "TypeScript": "TS",
    "Python": "PY",
    "C++": "C++",
    "C": "C",
    "HTML": "HTML",
    "CSS": "CSS",
    "Jupyter Notebook": "IPYNB",
    "Shell": "SH",
}

ASCII_CHARS = "   ..:-=+*#%@"

def fetch_github_data():
    user = requests.get(f"https://api.github.com/users/{USERNAME}", headers=HEADERS, timeout=15).json()
    repos = requests.get(
        f"https://api.github.com/users/{USERNAME}/repos?per_page=100&type=owner&sort=pushed",
        headers=HEADERS,
        timeout=15,
    ).json()
    if not isinstance(repos, list):
        repos = []

    now = datetime.now(timezone.utc)
    scored_repos = []
    lang_bytes = {}

    for r in repos:
        if r.get("fork") or r["name"].lower() == USERNAME.lower():
            continue

        pushed_at = datetime.strptime(r["pushed_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        days_since_push = max((now - pushed_at).total_seconds() / 86400.0, 0.1)

        commits_resp = requests.get(
            f"https://api.github.com/repos/{USERNAME}/{r['name']}/commits?per_page=30",
            headers=HEADERS,
            timeout=10,
        )
        recent_commits = len(commits_resp.json()) if commits_resp.status_code == 200 else 1

        recency_weight = 100.0 / (1.0 + days_since_push * 0.35)
        momentum_score = recency_weight + (recent_commits * 2.5) + (r.get("stargazers_count", 0) * 5)

        repo_langs = {}
        langs_resp = requests.get(r["languages_url"], headers=HEADERS, timeout=10)
        if langs_resp.status_code == 200:
            repo_langs = langs_resp.json()
            for lang, b in repo_langs.items():
                lang_bytes[lang] = lang_bytes.get(lang, 0) + b

        # Compute primary language percentage for clear ring visualization
        total_repo_bytes = sum(repo_langs.values())
        if total_repo_bytes > 0:
            top_lang, top_bytes = max(repo_langs.items(), key=lambda x: x[1])
            lang_pct = max(1, round((top_bytes / total_repo_bytes) * 100))
            lang_code = LANG_SHORT.get(top_lang, top_lang[:4].upper())
        else:
            lang_pct = 100
            lang_code = "CODE"

        scored_repos.append({
            "name": r["name"],
            "desc": r.get("description") or FLAGSHIP_META.get(r["name"], {}).get("desc", "Engineering build & active repository."),
            "language": r.get("language") or "Embedded / C++",
            "lang_pct": lang_pct,
            "lang_code": lang_code,
            "stars": r.get("stargazers_count", 0),
            "days_ago": int(days_since_push),
            "commits": recent_commits,
            "score": momentum_score,
            "url": r["html_url"],
        })

    scored_repos.sort(key=lambda x: x["score"], reverse=True)
    return user, scored_repos, lang_bytes


def fetch_contributions():
    if TOKEN:
        query = """
        query($login: String!) {
          user(login: $login) {
            contributionsCollection {
              contributionCalendar {
                totalContributions
                weeks {
                  contributionDays {
                    contributionCount
                    date
                  }
                }
              }
            }
          }
        }
        """
        resp = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": {"login": USERNAME}},
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            cal = (
                data.get("data", {})
                .get("user", {})
                .get("contributionsCollection", {})
                .get("contributionCalendar", {})
            )
            weeks = cal.get("weeks", [])
            if weeks:
                return cal.get("totalContributions", 0), weeks[-20:]

    now = datetime.now(timezone.utc)
    weeks = []
    for w in range(20):
        days = []
        for d in range(7):
            dt = now - timedelta(days=(19 - w) * 7 + (6 - d))
            count = (w * 3 + d * 2) % 9
            days.append({"contributionCount": count, "date": dt.strftime("%Y-%m-%d")})
        weeks.append({"contributionDays": days})
    return sum(d["contributionCount"] for wk in weeks for d in wk["contributionDays"]), weeks


def avatar_to_ascii(avatar_url, cols=48, rows=26):
    # Fetch high-res avatar directly (bypassing low-res cached thumbnails)
    clean_url = avatar_url.split("?")[0] + "?s=400"
    resp = requests.get(clean_url, timeout=15)
    img = Image.open(io.BytesIO(resp.content)).convert("L")
    img = img.resize((cols, rows), Image.Resampling.LANCZOS)

    # Detect edges (glasses frames, hair outline, headphones) to keep features sharp
    edges = img.filter(ImageFilter.FIND_EDGES)

    # Sample border pixels to detect background shade and suppress it to clean space
    border_vals = [
        img.getpixel((x, 0)) for x in range(cols)
    ] + [
        img.getpixel((0, y)) for y in range(rows)
    ] + [
        img.getpixel((cols - 1, y)) for y in range(rows)
    ]
    bg_level = sum(border_vals) / len(border_vals)

    pixels = list(img.getdata())
    lo, hi = min(pixels), max(pixels)
    span = max(hi - lo, 1)

    lines = []
    for y in range(rows):
        row_chars = []
        for x in range(cols):
            px = img.getpixel((x, y))
            edge = edges.getpixel((x, y))

            # Clear flat background pixels around the character silhouette
            if abs(px - bg_level) < 14 and edge < 35:
                row_chars.append(" ")
                continue

            # Normalize tone + add edge definition so glasses & headphones pop
            norm = (px - lo) / span
            boosted = min(1.0, max(0.0, norm * 0.82 + (edge / 255.0) * 0.45))
            idx = int(boosted * (len(ASCII_CHARS) - 1))
            row_chars.append(ASCII_CHARS[idx])
        lines.append("".join(row_chars))
    return lines

def format_time_ago(days):
    if days == 0:
        return "today"
    if days == 1:
        return "1d ago"
    if days < 30:
        return f"{days}d ago"
    return f"{days // 30}mo ago"


def build_hero_svg(user, ascii_lines, top_langs, repo_count, total_stars):
    """0.0s - 3.0s: Terminal boot & laser-scanned ASCII portrait."""
    ascii_svg_rows = []
    for i, line in enumerate(ascii_lines):
        delay = round(0.4 + i * 0.08, 3)
        y_pos = 88 + i * 13.0
        escaped = html.escape(line)
        ascii_svg_rows.append(
            f'<text x="32" y="{y_pos:.1f}" class="ascii-row" style="animation-delay:{delay}s">{escaped}</text>'
        )

    lang_str = ", ".join(top_langs[:4]) if top_langs else "Python, C++, JavaScript"
    rows_info = [
        ("Subject", user.get("name") or "Aman Rajpura", "#f8fafc"),
        ("Handle", f"@{USERNAME.lower()}", "#38bdf8"),
        ("Discipline", "B.Tech EEE · Embedded & Edge AI", "#e2e8f0"),
        ("Status", "Building | Prototyping | Shipping", "#34d399"),
        ("Core Stack", lang_str, "#bae6fd"),
        ("Builds", f"{repo_count} public repositories", "#f1f5f9"),
        ("Stars", f"{total_stars} GitHub stars", "#f1f5f9"),
        ("Lab Node", "Ahmedabad University · India", "#94a3b8"),
        ("Endpoint", f"github.com/{USERNAME}", "#38bdf8"),
    ]

    info_svg_rows = []
    for idx, (k, v, color) in enumerate(rows_info):
        delay = round(0.65 + idx * 0.22, 2)
        y_pos = 108 + idx * 34
        info_svg_rows.append(f"""
        <g class="telemetry-row" style="animation-delay:{delay}s">
          <text x="405" y="{y_pos}" class="key-label">{html.escape(k)}</text>
          <text x="520" y="{y_pos}" class="val-label" fill="{color}">{html.escape(v)}</text>
          <line x1="405" y1="{y_pos + 12}" x2="804" y2="{y_pos + 12}" stroke="#1e293b" stroke-width="1" />
        </g>
        """)

    return f"""<svg width="840" height="456" viewBox="0 0 840 456" xmlns="http://www.w3.org/2000/svg">
  <style>
    .bg {{ fill: #090d16; }}
    .frame {{ fill: #0b1120; stroke: #1e3a8a; stroke-width: 1.4; rx: 12; }}
    .panel {{ fill: #070b14; stroke: #172554; stroke-width: 1.1; rx: 8; }}
    .term-cmd {{ font: 600 13.5px 'JetBrains Mono', 'Fira Code', Consolas, monospace; fill: #38bdf8; }}
    .section-tag {{ font: 700 11px 'JetBrains Mono', Consolas, monospace; fill: #3b82f6; letter-spacing: 1.4px; }}
    .ascii-row {{
      font: 700 10.8px 'JetBrains Mono', 'Courier New', monospace;
      fill: #7dd3fc;
      white-space: pre;
      opacity: 0;
      animation: scanReveal 0.45s ease-out forwards;
    }}
    .key-label {{ font: 500 13px 'JetBrains Mono', Consolas, monospace; fill: #64748b; }}
    .val-label {{ font: 600 13.5px 'JetBrains Mono', Consolas, monospace; }}
    .telemetry-row {{
      opacity: 0;
      transform: translateX(12px);
      animation: rowBoot 0.45s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }}
    .scan-beam {{
      animation: beamSweep 2.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }}
    .frame-boot {{
      stroke-dasharray: 2600;
      stroke-dashoffset: 2600;
      animation: drawBorder 1.1s ease-out forwards;
    }}
    .pulse-dot {{ animation: pulse 2s infinite; }}
    @keyframes drawBorder {{ to {{ stroke-dashoffset: 0; }} }}
    @keyframes scanReveal {{
      0% {{ opacity: 0; fill: #ffffff; }}
      55% {{ opacity: 1; fill: #bae6fd; }}
      100% {{ opacity: 1; fill: #7dd3fc; }}
    }}
    @keyframes rowBoot {{ to {{ opacity: 1; transform: translateX(0); }} }}
    @keyframes beamSweep {{
      0% {{ transform: translateY(0px); opacity: 0.95; }}
      88% {{ transform: translateY(345px); opacity: 0.95; }}
      100% {{ transform: translateY(350px); opacity: 0; }}
    }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.35; }} }}
  </style>

  <defs>
    <linearGradient id="beamGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0" />
      <stop offset="50%" stop-color="#7dd3fc" stop-opacity="0.4" />
      <stop offset="100%" stop-color="#e0f2fe" stop-opacity="0.95" />
    </linearGradient>
    <clipPath id="avatarClip">
      <rect x="20" y="56" width="352" height="376" rx="8" />
    </clipPath>
  </defs>

  <rect width="840" height="456" class="bg" rx="12" />
  <rect x="5" y="5" width="830" height="446" class="frame frame-boot" />

  <circle cx="26" cy="28" r="5.5" fill="#ef4444" />
  <circle cx="45" cy="28" r="5.5" fill="#f59e0b" />
  <circle cx="64" cy="28" r="5.5" fill="#10b981" />
  <text x="245" y="33" class="term-cmd">aman-lab1@github ~ $ ./profile-scan --live</text>
  <circle cx="776" cy="28" r="4.5" fill="#34d399" class="pulse-dot" />
  <text x="787" y="32" font-family="monospace" font-size="11" font-weight="700" fill="#34d399">LIVE</text>
  <line x1="5" y1="45" x2="835" y2="45" stroke="#1e293b" stroke-width="1" />

  <rect x="20" y="56" width="352" height="376" class="panel" />
  <text x="32" y="73" class="section-tag">VISUAL.MAP // AVATAR_MATRIX</text>
  <g clip-path="url(#avatarClip)">
    {''.join(ascii_svg_rows)}
    <g class="scan-beam">
      <rect x="20" y="56" width="352" height="24" fill="url(#beamGrad)" />
      <line x1="20" y1="80" x2="372" y2="80" stroke="#e0f2fe" stroke-width="2" />
    </g>
  </g>

  <rect x="386" y="56" width="434" height="376" class="panel" />
  <text x="405" y="73" class="section-tag">SYSTEM.INFO // TELEMETRY</text>
  {''.join(info_svg_rows)}
</svg>"""


def build_philosophy_svg():
    """3.2s - 5.4s: Kinetic typography animation timed for scrolling down from hero."""
    pillars = [
        ("01 // PHYSICAL & EMBEDDED", "ESP32, Arduino, motor control,", "optical comms, KiCad & CAD.", 3.9),
        ("02 // DETERMINISTIC EDGE AI", "Hybrid local/cloud inference", "with verified tool pipelines.", 4.4),
        ("03 // LOCAL-FIRST SOFTWARE", "Offline-capable PWAs with", "IndexedDB & zero latency.", 4.9),
    ]

    cols_svg = []
    for idx, (title, l1, l2, delay) in enumerate(pillars):
        x = 20 + idx * 271
        cols_svg.append(f"""
        <g class="typo-col" style="animation-delay:{delay}s">
          <rect x="{x}" y="106" width="258" height="106" rx="8" fill="#070b14" stroke="#172554" stroke-width="1.1" />
          <text x="{x + 15}" y="133" font-family="monospace" font-size="12" font-weight="700" fill="#38bdf8">{html.escape(title)}</text>
          <line x1="{x + 15}" y1="145" x2="{x + 243}" y2="145" stroke="#1e293b" stroke-width="1" />
          <text x="{x + 15}" y="168" font-family="sans-serif" font-size="13" fill="#e2e8f0">{html.escape(l1)}</text>
          <text x="{x + 15}" y="189" font-family="sans-serif" font-size="13" fill="#94a3b8">{html.escape(l2)}</text>
        </g>
        """)

    return f"""<svg width="840" height="232" viewBox="0 0 840 232" xmlns="http://www.w3.org/2000/svg">
  <style>
    .type-line {{
      clip-path: inset(0 100% 0 0);
      animation: typingReveal 1.3s steps(48, end) 3.2s forwards;
    }}
    .typo-col {{
      opacity: 0;
      transform: translateY(14px);
      animation: riseText 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }}
    .cursor-blink {{ animation: blink 0.8s infinite; }}
    @keyframes typingReveal {{ to {{ clip-path: inset(0 0% 0 0); }} }}
    @keyframes riseText {{ to {{ opacity: 1; transform: translateY(0); }} }}
    @keyframes blink {{ 0%, 49% {{ opacity: 1; }} 50%, 100% {{ opacity: 0; }} }}
  </style>
  <rect width="840" height="232" rx="12" fill="#090d16" />
  <rect x="5" y="5" width="830" height="222" rx="12" fill="#0b1120" stroke="#1e3a8a" stroke-width="1.4" />

  <text x="22" y="35" font-family="monospace" font-size="12" font-weight="700" fill="#3b82f6" letter-spacing="1.4">ENGINEERING.PHILOSOPHY</text>
  <text x="235" y="35" font-family="monospace" font-size="12" fill="#64748b">cat ./manifesto.txt</text>
  <line x1="20" y1="47" x2="820" y2="47" stroke="#1e293b" stroke-width="1" />

  <g class="type-line">
    <text x="22" y="78" font-family="monospace" font-size="13.5" font-weight="600" fill="#f8fafc">
      &gt; Bridging electronics, autonomous robotics &amp; local-first software into unified systems.<tspan fill="#38bdf8" class="cursor-blink"> █</tspan>
    </text>
  </g>

  {''.join(cols_svg)}
</svg>"""


def build_project_card_svg(repo, idx):
    """5.5s - 7.8s: Individual clickable repo card SVG with clean word-wrapping & Language Share ring."""
    delay = round(5.5 + idx * 0.45, 2)
    pct = repo["lang_pct"]
    lang_code = repo["lang_code"]
    circumference = 2 * math.pi * 26
    dash_offset = circumference * (1 - pct / 100.0)

    meta = FLAGSHIP_META.get(repo["name"], {})
    raw_desc = meta.get("desc", repo["desc"])
    wrapped = textwrap.wrap(raw_desc, width=36)
    line1 = wrapped[0] if len(wrapped) > 0 else ""
    line2 = wrapped[1] if len(wrapped) > 1 else ""
    if len(wrapped) > 2:
        line2 = line2[:33].rstrip() + "..."

    lang_badge = meta.get("stack", repo["language"])
    badge_w = max(84, int(len(lang_badge) * 7.6 + 20))
    time_str = format_time_ago(repo["days_ago"])

    return f"""<svg width="412" height="184" viewBox="0 0 412 184" xmlns="http://www.w3.org/2000/svg">
  <style>
    .card-boot {{
      opacity: 0;
      transform: translateY(14px);
      animation: cardRise 0.55s cubic-bezier(0.16, 1, 0.3, 1) {delay}s forwards;
    }}
    @keyframes cardRise {{
      to {{ opacity: 1; transform: translateY(0); }}
    }}
  </style>
  <rect width="412" height="184" rx="10" fill="#090d16" />
  <g class="card-boot">
    <rect x="2" y="2" width="408" height="180" rx="10" fill="#0b1120" stroke="#1e3a8a" stroke-width="1.3" />
    <rect x="2" y="2" width="5" height="180" rx="2.5" fill="#38bdf8" />

    <text x="20" y="27" font-family="monospace" font-size="11.5" fill="#64748b">NODE_0{idx + 1} // {USERNAME}/{html.escape(repo['name'])}</text>
    <text x="20" y="55" font-family="monospace" font-size="18" font-weight="700" fill="#f8fafc">{html.escape(repo['name'])} <tspan fill="#38bdf8">↗</tspan></text>

    <text x="20" y="82" font-family="sans-serif" font-size="13" fill="#cbd5e1">{html.escape(line1)}</text>
    <text x="20" y="101" font-family="sans-serif" font-size="13" fill="#94a3b8">{html.escape(line2)}</text>

    <rect x="20" y="118" width="{badge_w}" height="22" rx="5" fill="#070b14" stroke="#1e3a8a" />
    <text x="30" y="133" font-family="monospace" font-size="11.5" font-weight="600" fill="#7dd3fc">{html.escape(lang_badge)}</text>

    <text x="20" y="162" font-family="monospace" font-size="11.5" fill="#94a3b8">★ {repo['stars']}  ·  {repo['commits']} commits  ·  {time_str}</text>

    <!-- Primary Language Share Gauge -->
    <circle cx="358" cy="88" r="26" fill="#070b14" stroke="#1e293b" stroke-width="5" />
    <circle cx="358" cy="88" r="26" fill="none" stroke="#38bdf8" stroke-width="5"
            stroke-dasharray="{circumference:.1f}" stroke-dashoffset="{dash_offset:.1f}"
            stroke-linecap="round" transform="rotate(-90 358 88)" />
    <text x="358" y="86" text-anchor="middle" font-family="monospace" font-size="12" font-weight="700" fill="#f8fafc">{pct}%</text>
    <text x="358" y="100" text-anchor="middle" font-family="monospace" font-size="9.5" font-weight="700" fill="#38bdf8">{html.escape(lang_code)}</text>
  </g>
</svg>"""


def build_3d_contributions_svg(total_contribs, weeks):
    """8.0s - 10.8s: 3D Isometric Skyline rising from ground zero as viewer reaches bottom."""
    max_count = max(
        [d["contributionCount"] for wk in weeks for d in wk["contributionDays"]],
        default=1,
    ) or 1

    origin_x = 225
    origin_y = 175
    tile_w = 13.8
    tile_h = 7.0

    buildings = []
    for w_idx, wk in enumerate(weeks):
        days = wk["contributionDays"]
        for d_idx, day in enumerate(days):
            count = day["contributionCount"]
            h = 4.0 if count == 0 else 12.0 + (count / max_count) * 78.0

            cx = origin_x + (w_idx - d_idx) * tile_w
            cy = origin_y + (w_idx + d_idx) * tile_h

            if count == 0:
                top_c, left_c, right_c = "#1e293b", "#0f172a", "#172033"
            elif count <= max_count * 0.35:
                top_c, left_c, right_c = "#38bdf8", "#0284c7", "#0369a1"
            elif count <= max_count * 0.7:
                top_c, left_c, right_c = "#7dd3fc", "#0ea5e9", "#0284c7"
            else:
                top_c, left_c, right_c = "#e0f2fe", "#38bdf8", "#0ea5e9"

            p_top = f"{cx:.1f},{cy - h - tile_h:.1f}"
            p_right_top = f"{cx + tile_w:.1f},{cy - h:.1f}"
            p_front_top = f"{cx:.1f},{cy - h + tile_h:.1f}"
            p_left_top = f"{cx - tile_w:.1f},{cy - h:.1f}"

            p_right_bot = f"{cx + tile_w:.1f},{cy:.1f}"
            p_front_bot = f"{cx:.1f},{cy + tile_h:.1f}"
            p_left_bot = f"{cx - tile_w:.1f},{cy:.1f}"

            delay = round(8.0 + (w_idx * 0.08) + (d_idx * 0.04), 2)

            buildings.append(f"""
            <g class="iso-tower" style="transform-origin:{cx:.1f}px {cy + tile_h:.1f}px; animation-delay:{delay}s">
              <polygon points="{p_left_top} {p_front_top} {p_front_bot} {p_left_bot}" fill="{left_c}" />
              <polygon points="{p_front_top} {p_right_top} {p_right_bot} {p_front_bot}" fill="{right_c}" />
              <polygon points="{p_top} {p_right_top} {p_front_top} {p_left_top}" fill="{top_c}" />
            </g>
            """)

    active_days = sum(1 for wk in weeks for d in wk["contributionDays"] if d["contributionCount"] > 0)

    return f"""<svg width="840" height="380" viewBox="0 0 840 380" xmlns="http://www.w3.org/2000/svg">
  <style>
    .iso-tower {{
      transform: scaleY(0);
      animation: riseSkyline 0.75s cubic-bezier(0.22, 1, 0.36, 1) forwards;
    }}
    .stat-fade {{
      opacity: 0;
      animation: fadeStat 0.6s ease-out 8.6s forwards;
    }}
    @keyframes riseSkyline {{
      0% {{ transform: scaleY(0); opacity: 0.2; }}
      100% {{ transform: scaleY(1); opacity: 1; }}
    }}
    @keyframes fadeStat {{ to {{ opacity: 1; }} }}
  </style>

  <rect width="840" height="380" rx="12" fill="#090d16" />
  <rect x="5" y="5" width="830" height="370" rx="12" fill="#0b1120" stroke="#1e3a8a" stroke-width="1.4" />

  <text x="22" y="35" font-family="monospace" font-size="12" font-weight="700" fill="#3b82f6" letter-spacing="1.4">CONTRIBUTION.SKYLINE // 3D_TELEMETRY</text>
  <text x="818" y="35" text-anchor="end" font-family="monospace" font-size="12" fill="#38bdf8">20-week isometric commit elevation</text>
  <line x1="20" y1="47" x2="820" y2="47" stroke="#1e293b" stroke-width="1" />

  <g>{''.join(buildings)}</g>

  <g class="stat-fade">
    <rect x="595" y="68" width="224" height="284" rx="8" fill="#070b14" stroke="#172554" stroke-width="1.1" />
    <text x="615" y="96" font-family="monospace" font-size="11" font-weight="700" fill="#3b82f6" letter-spacing="1.2">ACTIVITY.METRICS</text>
    <line x1="615" y1="108" x2="800" y2="108" stroke="#1e293b" stroke-width="1" />

    <text x="615" y="138" font-family="monospace" font-size="11.5" fill="#64748b">ANNUAL CONTRIBUTIONS</text>
    <text x="615" y="170" font-family="monospace" font-size="30" font-weight="700" fill="#38bdf8">{total_contribs}</text>

    <text x="615" y="210" font-family="monospace" font-size="11.5" fill="#64748b">ACTIVE BUILD DAYS (20W)</text>
    <text x="615" y="240" font-family="monospace" font-size="26" font-weight="700" fill="#f8fafc">{active_days} <tspan font-size="13" fill="#34d399">days</tspan></text>

    <text x="615" y="280" font-family="monospace" font-size="11.5" fill="#64748b">ELEVATION SCALE</text>
    <rect x="615" y="294" width="16" height="16" rx="3" fill="#1e293b" />
    <rect x="637" y="294" width="16" height="16" rx="3" fill="#0284c7" />
    <rect x="659" y="294" width="16" height="16" rx="3" fill="#38bdf8" />
    <rect x="681" y="294" width="16" height="16" rx="3" fill="#e0f2fe" />
    <text x="706" y="307" font-family="monospace" font-size="11.5" fill="#94a3b8">0 → Peak</text>
  </g>
</svg>"""


def update_readme_project_links(top_repos):
    """Keep README.md clickable repo links and cache-busting SVG versions synced."""
    if not os.path.exists("README.md"):
        return
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    cards_html = []
    for i in range(4):
        if i < len(top_repos):
            r = top_repos[i]
            cards_html.append(
                f'<td width="50%"><a href="{r["url"]}"><img src="./assets/project-{i+1}.svg" width="100%" alt="{html.escape(r["name"])}" /></a></td>'
            )
        else:
            cards_html.append('<td width="50%"></td>')

    grid_block = f"""<!-- PROJECTS:START -->
<table>
  <tr>
    {cards_html[0]}
    {cards_html[1]}
  </tr>
  <tr>
    {cards_html[2]}
    {cards_html[3]}
  </tr>
</table>
<!-- PROJECTS:END -->"""

    updated = re.sub(
        r"<!-- PROJECTS:START -->.*?<!-- PROJECTS:END -->",
        grid_block,
        content,
        flags=re.DOTALL,
    )

    ts = int(time.time())
    svg_files = [
        "hero-scan.svg",
        "philosophy.svg",
        "contributions-3d.svg",
        "project-1.svg",
        "project-2.svg",
        "project-3.svg",
        "project-4.svg",
    ]
    for svg_name in svg_files:
        updated = re.sub(
            rf"\./assets/{re.escape(svg_name)}(\?v=\d+)?",
            f"./assets/{svg_name}?v={ts}",
            updated,
        )

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(updated)


def main():
    os.makedirs("assets", exist_ok=True)
    user, scored_repos, lang_bytes = fetch_github_data()
    total_contribs, weeks = fetch_contributions()

    sorted_langs = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)
    top_lang_names = [k for k, _ in sorted_langs]

    total_stars = sum(r["stars"] for r in scored_repos)
    ascii_lines = avatar_to_ascii(user["avatar_url"])

    with open("assets/hero-scan.svg", "w", encoding="utf-8") as f:
        f.write(build_hero_svg(user, ascii_lines, top_lang_names, user.get("public_repos", len(scored_repos)), total_stars))

    with open("assets/philosophy.svg", "w", encoding="utf-8") as f:
        f.write(build_philosophy_svg())

    top_4 = scored_repos[:4]
    for idx, repo in enumerate(top_4):
        with open(f"assets/project-{idx+1}.svg", "w", encoding="utf-8") as f:
            f.write(build_project_card_svg(repo, idx))

    with open("assets/contributions-3d.svg", "w", encoding="utf-8") as f:
        f.write(build_3d_contributions_svg(total_contribs, weeks))

    update_readme_project_links(top_4)


if __name__ == "__main__":
    main()