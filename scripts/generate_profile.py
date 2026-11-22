import html
import io
import math
import os
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
        "desc": "8-joint autonomous quadruped robot & PyBullet kinematic twin (RPi 4 + Arduino).",
        "stack": "Python · C++ · PyBullet",
    },
    "Folio": {
        "desc": "Offline-first personal & business ledger PWA with IndexedDB persistence & analytics.",
        "stack": "JavaScript · IndexedDB · PWA",
    },
    "LaserLink": {
        "desc": "Free-space OOK laser data transceiver on Arduino transmitting framed audio packets.",
        "stack": "C++ · Arduino · OOK Protocol",
    },
    "Pebble": {
        "desc": "Minimalist daily expense tracker with granular categorization & spending summaries.",
        "stack": "JavaScript · HTML5 · CSS3",
    },
    "Memento": {
        "desc": "Mobile-first peer-to-peer lending & borrowing tracker with automated balance audits.",
        "stack": "JavaScript · LocalStorage · PWA",
    },
}

# High-contrast density ramp for crisp facial definition on dark backgrounds
ASCII_CHARS = "  ..::--==++**##%%@@"


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

        langs_resp = requests.get(r["languages_url"], headers=HEADERS, timeout=10)
        if langs_resp.status_code == 200:
            for lang, b in langs_resp.json().items():
                lang_bytes[lang] = lang_bytes.get(lang, 0) + b

        scored_repos.append({
            "name": r["name"],
            "desc": r.get("description") or FLAGSHIP_META.get(r["name"], {}).get("desc", "Engineering build & active repository."),
            "language": r.get("language") or "Embedded / C++",
            "stars": r.get("stargazers_count", 0),
            "days_ago": int(days_since_push),
            "commits": recent_commits,
            "score": momentum_score,
        })

    scored_repos.sort(key=lambda x: x["score"], reverse=True)
    return user, scored_repos, lang_bytes


def fetch_contributions():
    """Fetch 22 weeks of daily contribution counts via GitHub GraphQL API."""
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
                return cal.get("totalContributions", 0), weeks[-22:]

    # Fallback if run locally without a GraphQL-scoped token
    now = datetime.now(timezone.utc)
    weeks = []
    for w in range(22):
        days = []
        for d in range(7):
            dt = now - timedelta(days=(21 - w) * 7 + (6 - d))
            count = (w * 3 + d * 2) % 9
            days.append({"contributionCount": count, "date": dt.strftime("%Y-%m-%d")})
        weeks.append({"contributionDays": days})
    return sum(d["contributionCount"] for wk in weeks for d in wk["contributionDays"]), weeks


def avatar_to_ascii(avatar_url, cols=52, rows=26):
    resp = requests.get(avatar_url, timeout=15)
    img = Image.open(io.BytesIO(resp.content)).convert("L")
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(1.75)
    img = ImageEnhance.Brightness(img).enhance(1.12)
    img = img.resize((cols, rows), Image.Resampling.LANCZOS)

    lines = []
    for y in range(rows):
        row_chars = []
        for x in range(cols):
            px = img.getpixel((x, y))
            # Gamma boost midtones so facial contours pop clearly
            norm = (px / 255.0) ** 0.85
            idx = int(norm * (len(ASCII_CHARS) - 1))
            row_chars.append(ASCII_CHARS[idx])
        lines.append("".join(row_chars))
    return lines


def format_time_ago(days):
    if days == 0:
        return "updated today"
    if days == 1:
        return "updated 1d ago"
    if days < 30:
        return f"updated {days}d ago"
    return f"updated {days // 30}mo ago"


def build_hero_svg(user, ascii_lines, top_langs, repo_count, total_stars):
    ascii_svg_rows = []
    for i, line in enumerate(ascii_lines):
        delay = round(0.35 + i * 0.055, 3)
        y_pos = 78 + i * 12.2
        escaped = html.escape(line)
        ascii_svg_rows.append(
            f'<text x="32" y="{y_pos:.1f}" class="ascii-row" style="animation-delay:{delay}s">{escaped}</text>'
        )

    lang_str = ", ".join(top_langs[:4]) if top_langs else "Python, C++, JavaScript, Embedded C"
    rows_info = [
        ("Subject", user.get("name") or "Aman Rajpura", "#f8fafc"),
        ("Handle", f"@{USERNAME.lower()}", "#38bdf8"),
        ("Discipline", "B.Tech EEE · Embedded Systems & Edge AI", "#e2e8f0"),
        ("Status", "Building | Prototyping | Shipping", "#34d399"),
        ("Core Stack", lang_str, "#bae6fd"),
        ("Repositories", f"{repo_count} public builds", "#f1f5f9"),
        ("Recognition", f"{total_stars} GitHub stars", "#f1f5f9"),
        ("Lab Node", "Ahmedabad University · India", "#94a3b8"),
        ("Endpoint", f"github.com/{USERNAME}", "#38bdf8"),
    ]

    info_svg_rows = []
    for idx, (k, v, color) in enumerate(rows_info):
        delay = round(0.55 + idx * 0.14, 2)
        y_pos = 96 + idx * 32
        info_svg_rows.append(f"""
        <g class="telemetry-row" style="animation-delay:{delay}s">
          <text x="415" y="{y_pos}" class="key-label">{html.escape(k)}</text>
          <text x="535" y="{y_pos}" class="val-label" fill="{color}">{html.escape(v)}</text>
          <line x1="415" y1="{y_pos + 11}" x2="862" y2="{y_pos + 11}" stroke="#1e293b" stroke-width="1" />
        </g>
        """)

    return f"""<svg width="900" height="430" viewBox="0 0 900 430" xmlns="http://www.w3.org/2000/svg">
  <style>
    .bg {{ fill: #090d16; }}
    .frame {{ fill: #0b1120; stroke: #1e3a8a; stroke-width: 1.2; rx: 12; }}
    .panel {{ fill: #070b14; stroke: #172554; stroke-width: 1; rx: 8; }}
    .term-cmd {{ font: 600 12.5px 'JetBrains Mono', 'Fira Code', Consolas, monospace; fill: #38bdf8; }}
    .section-tag {{ font: 700 10px 'JetBrains Mono', Consolas, monospace; fill: #3b82f6; letter-spacing: 1.5px; }}
    .ascii-row {{
      font: 700 10.6px 'JetBrains Mono', 'Courier New', monospace;
      fill: #7dd3fc;
      white-space: pre;
      opacity: 0;
      animation: scanReveal 0.4s ease-out forwards;
    }}
    .key-label {{ font: 500 12px 'JetBrains Mono', Consolas, monospace; fill: #64748b; }}
    .val-label {{ font: 600 12.5px 'JetBrains Mono', Consolas, monospace; }}
    .telemetry-row {{
      opacity: 0;
      transform: translateX(10px);
      animation: rowBoot 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }}
    .scan-beam {{
      animation: beamSweep 2.1s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }}
    .frame-boot {{
      stroke-dasharray: 2600;
      stroke-dashoffset: 2600;
      animation: drawBorder 1.0s ease-out forwards;
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
      85% {{ transform: translateY(320px); opacity: 0.95; }}
      100% {{ transform: translateY(325px); opacity: 0; }}
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
      <rect x="22" y="52" width="365" height="352" rx="8" />
    </clipPath>
  </defs>

  <rect width="900" height="430" class="bg" rx="12" />
  <rect x="6" y="6" width="888" height="418" class="frame frame-boot" />

  <circle cx="26" cy="26" r="5" fill="#ef4444" />
  <circle cx="44" cy="26" r="5" fill="#f59e0b" />
  <circle cx="62" cy="26" r="5" fill="#10b981" />
  <text x="275" y="30" class="term-cmd">aman-lab1@github ~ $ ./profile-scan --live</text>
  <circle cx="842" cy="26" r="4" fill="#34d399" class="pulse-dot" />
  <text x="852" y="30" font-family="monospace" font-size="10" fill="#34d399">LIVE</text>
  <line x1="6" y1="42" x2="894" y2="42" stroke="#1e293b" stroke-width="1" />

  <rect x="22" y="52" width="365" height="352" class="panel" />
  <text x="34" y="66" class="section-tag">VISUAL.MAP // AVATAR_MATRIX</text>
  <g clip-path="url(#avatarClip)">
    {''.join(ascii_svg_rows)}
    <g class="scan-beam">
      <rect x="22" y="52" width="365" height="24" fill="url(#beamGrad)" />
      <line x1="22" y1="76" x2="387" y2="76" stroke="#e0f2fe" stroke-width="2" />
    </g>
  </g>

  <rect x="399" y="52" width="479" height="352" class="panel" />
  <text x="415" y="66" class="section-tag">SYSTEM.INFO // TELEMETRY</text>
  {''.join(info_svg_rows)}
</svg>"""


def build_philosophy_svg():
    """Kinetic typography animation (starts at 2.2s as viewer scrolls past hero)."""
    pillars = [
        ("01 // PHYSICAL & EMBEDDED", "ESP32, Arduino, motor control, OOK optical", "transceivers, sensor fusion, KiCad & CAD.", 2.6),
        ("02 // DETERMINISTIC EDGE AI", "Hybrid local/cloud inference (Ollama + Groq)", "with verified tool-execution pipelines.", 3.0),
        ("03 // LOCAL-FIRST SOFTWARE", "Offline-capable PWAs with IndexedDB storage,", "zero-server latency & clean interfaces.", 3.4),
    ]

    cols_svg = []
    for idx, (title, l1, l2, delay) in enumerate(pillars):
        x = 24 + idx * 288
        cols_svg.append(f"""
        <g class="typo-col" style="animation-delay:{delay}s">
          <rect x="{x}" y="98" width="272" height="94" rx="8" fill="#070b14" stroke="#172554" stroke-width="1" />
          <text x="{x + 14}" y="122" font-family="monospace" font-size="11.5" font-weight="700" fill="#38bdf8">{html.escape(title)}</text>
          <line x1="{x + 14}" y1="132" x2="{x + 258}" y2="132" stroke="#1e293b" stroke-width="1" />
          <text x="{x + 14}" y="152" font-family="sans-serif" font-size="11.5" fill="#cbd5e1">{html.escape(l1)}</text>
          <text x="{x + 14}" y="170" font-family="sans-serif" font-size="11.5" fill="#94a3b8">{html.escape(l2)}</text>
        </g>
        """)

    return f"""<svg width="900" height="214" viewBox="0 0 900 214" xmlns="http://www.w3.org/2000/svg">
  <style>
    .type-line {{
      clip-path: inset(0 100% 0 0);
      animation: typingReveal 1.1s steps(48, end) 2.1s forwards;
    }}
    .typo-col {{
      opacity: 0;
      transform: translateY(12px);
      animation: riseText 0.55s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }}
    .cursor-blink {{
      animation: blink 0.8s infinite;
    }}
    @keyframes typingReveal {{
      to {{ clip-path: inset(0 0% 0 0); }}
    }}
    @keyframes riseText {{
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes blink {{
      0%, 49% {{ opacity: 1; }}
      50%, 100% {{ opacity: 0; }}
    }}
  </style>
  <rect width="900" height="214" rx="12" fill="#090d16" />
  <rect x="6" y="6" width="888" height="202" rx="12" fill="#0b1120" stroke="#1e3a8a" stroke-width="1.2" />

  <text x="24" y="34" font-family="monospace" font-size="11" font-weight="700" fill="#3b82f6" letter-spacing="1.4">ENGINEERING.PHILOSOPHY</text>
  <text x="225" y="34" font-family="monospace" font-size="11" fill="#64748b">cat ./manifesto.txt</text>
  <line x1="22" y1="45" x2="878" y2="45" stroke="#1e293b" stroke-width="1" />

  <g class="type-line">
    <text x="24" y="72" font-family="monospace" font-size="13" font-weight="600" fill="#f8fafc">
      &gt; Bridging low-level electronics, autonomous robotics &amp; local-first software into unified systems.<tspan fill="#38bdf8" class="cursor-blink"> █</tspan>
    </text>
  </g>

  {''.join(cols_svg)}
</svg>"""


def build_projects_svg(scored_repos):
    """Holographic circuit boot-up cards (starts at 4.0s as viewer scrolls to builds)."""
    top_repos = scored_repos[:4]
    max_score = max([r["score"] for r in top_repos], default=100)

    cards = []
    positions = [(22, 56), (456, 56), (22, 212), (456, 212)]

    for idx, repo in enumerate(top_repos):
        x, y = positions[idx]
        delay = round(4.1 + idx * 0.25, 2)
        pct = min(98, max(38, int((repo["score"] / max_score) * 95)))
        circumference = 2 * math.pi * 21
        dash_offset = circumference * (1 - pct / 100.0)

        meta = FLAGSHIP_META.get(repo["name"], {})
        desc = meta.get("desc", repo["desc"])
        if len(desc) > 84:
            desc = desc[:81].rstrip() + "..."
        line1 = desc[:43]
        line2 = desc[43:]

        lang_badge = meta.get("stack", repo["language"])
        time_str = format_time_ago(repo["days_ago"])

        cards.append(f"""
        <g class="holo-card" style="animation-delay:{delay}s">
          <rect x="{x}" y="{y}" width="422" height="142" rx="8" fill="#070b14" stroke="#1e3a8a" stroke-width="1.1" />
          <rect x="{x}" y="{y}" width="4" height="142" rx="2" fill="#38bdf8" />
          <text x="{x + 18}" y="{y + 23}" font-family="monospace" font-size="10.5" fill="#64748b">NODE_0{idx+1} // {USERNAME}/{html.escape(repo['name'])}</text>
          <text x="{x + 18}" y="{y + 48}" font-family="monospace" font-size="15.5" font-weight="700" fill="#f8fafc">{html.escape(repo['name'])} <tspan fill="#38bdf8">_</tspan></text>
          <text x="{x + 18}" y="{y + 70}" font-family="sans-serif" font-size="11.5" fill="#cbd5e1">{html.escape(line1)}</text>
          <text x="{x + 18}" y="{y + 86}" font-family="sans-serif" font-size="11.5" fill="#94a3b8">{html.escape(line2)}</text>

          <rect x="{x + 18}" y="{y + 101}" width="{len(lang_badge)*6.6 + 14:.0f}" height="18" rx="4" fill="#0f172a" stroke="#1e3a8a" />
          <text x="{x + 25}" y="{y + 113}" font-family="monospace" font-size="10" fill="#7dd3fc">{html.escape(lang_badge)}</text>
          <text x="{x + 18}" y="{y + 132}" font-family="monospace" font-size="10" fill="#64748b">★ {repo['stars']}  ·  {repo['commits']} recent commits  ·  {time_str}</text>

          <circle cx="{x + 376}" cy="{y + 70}" r="21" fill="none" stroke="#1e293b" stroke-width="4.5" />
          <circle cx="{x + 376}" cy="{y + 70}" r="21" fill="none" stroke="#38bdf8" stroke-width="4.5"
                  stroke-dasharray="{circumference:.1f}" stroke-dashoffset="{dash_offset:.1f}"
                  stroke-linecap="round" transform="rotate(-90 {x + 376} {y + 70})" />
          <text x="{x + 376}" y="{y + 74}" text-anchor="middle" font-family="monospace" font-size="10.5" font-weight="700" fill="#f8fafc">{pct}%</text>
        </g>
        """)

    return f"""<svg width="900" height="374" viewBox="0 0 900 374" xmlns="http://www.w3.org/2000/svg">
  <style>
    .holo-card {{
      opacity: 0;
      transform: scale(0.96) translateY(10px);
      animation: holoBoot 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }}
    @keyframes holoBoot {{
      to {{ opacity: 1; transform: scale(1) translateY(0); }}
    }}
  </style>
  <rect width="900" height="374" rx="12" fill="#090d16" />
  <rect x="6" y="6" width="888" height="362" rx="12" fill="#0b1120" stroke="#1e3a8a" stroke-width="1.2" />
  <text x="24" y="34" font-family="monospace" font-size="11" font-weight="700" fill="#3b82f6" letter-spacing="1.4">ACTIVE.BUILDS</text>
  <text x="150" y="34" font-family="monospace" font-size="11" fill="#64748b">./projects.sh --sort=momentum</text>
  <text x="874" y="34" text-anchor="end" font-family="monospace" font-size="11" fill="#38bdf8">ranked by commit velocity</text>
  <line x1="22" y1="45" x2="878" y2="45" stroke="#1e293b" stroke-width="1" />
  {''.join(cards)}
</svg>"""


def build_3d_contributions_svg(total_contribs, weeks):
    """3D Isometric Skyline where bars rise from ground zero to tall buildings (starts at 5.8s)."""
    max_count = max(
        [d["contributionCount"] for wk in weeks for d in wk["contributionDays"]],
        default=1,
    ) or 1

    # Isometric projection parameters
    origin_x = 245
    origin_y = 165
    tile_w = 13.5
    tile_h = 6.8

    buildings = []
    # Painter's algorithm: draw back-to-front (week 0..21, day 0..6)
    for w_idx, wk in enumerate(weeks):
        days = wk["contributionDays"]
        for d_idx, day in enumerate(days):
            count = day["contributionCount"]
            # Base height 4px so empty days look like city foundation pads; active days rise up to 78px
            h = 4.0 if count == 0 else 10.0 + (count / max_count) * 72.0

            cx = origin_x + (w_idx - d_idx) * tile_w
            cy = origin_y + (w_idx + d_idx) * tile_h

            # Color palette scaled by building height
            if count == 0:
                top_c, left_c, right_c = "#1e293b", "#0f172a", "#172033"
            elif count <= max_count * 0.35:
                top_c, left_c, right_c = "#38bdf8", "#0284c7", "#0369a1"
            elif count <= max_count * 0.7:
                top_c, left_c, right_c = "#7dd3fc", "#0ea5e9", "#0284c7"
            else:
                top_c, left_c, right_c = "#e0f2fe", "#38bdf8", "#0ea5e9"

            # 3D isometric prism vertices at full height h
            p_top = f"{cx:.1f},{cy - h - tile_h:.1f}"
            p_right_top = f"{cx + tile_w:.1f},{cy - h:.1f}"
            p_front_top = f"{cx:.1f},{cy - h + tile_h:.1f}"
            p_left_top = f"{cx - tile_w:.1f},{cy - h:.1f}"

            p_right_bot = f"{cx + tile_w:.1f},{cy:.1f}"
            p_front_bot = f"{cx:.1f},{cy + tile_h:.1f}"
            p_left_bot = f"{cx - tile_w:.1f},{cy:.1f}"

            delay = round(5.8 + (w_idx * 0.055) + (d_idx * 0.03), 2)

            buildings.append(f"""
            <g class="iso-tower" style="transform-origin:{cx:.1f}px {cy + tile_h:.1f}px; animation-delay:{delay}s">
              <polygon points="{p_left_top} {p_front_top} {p_front_bot} {p_left_bot}" fill="{left_c}" />
              <polygon points="{p_front_top} {p_right_top} {p_right_bot} {p_front_bot}" fill="{right_c}" />
              <polygon points="{p_top} {p_right_top} {p_front_top} {p_left_top}" fill="{top_c}" />
            </g>
            """)

    # Compute active days in window
    active_days = sum(1 for wk in weeks for d in wk["contributionDays"] if d["contributionCount"] > 0)

    return f"""<svg width="900" height="360" viewBox="0 0 900 360" xmlns="http://www.w3.org/2000/svg">
  <style>
    .iso-tower {{
      transform: scaleY(0);
      animation: riseSkyline 0.65s cubic-bezier(0.22, 1, 0.36, 1) forwards;
    }}
    .stat-fade {{
      opacity: 0;
      animation: fadeStat 0.5s ease-out 6.4s forwards;
    }}
    @keyframes riseSkyline {{
      0% {{ transform: scaleY(0); opacity: 0.2; }}
      100% {{ transform: scaleY(1); opacity: 1; }}
    }}
    @keyframes fadeStat {{
      to {{ opacity: 1; }}
    }}
  </style>

  <rect width="900" height="360" rx="12" fill="#090d16" />
  <rect x="6" y="6" width="888" height="348" rx="12" fill="#0b1120" stroke="#1e3a8a" stroke-width="1.2" />

  <text x="24" y="34" font-family="monospace" font-size="11" font-weight="700" fill="#3b82f6" letter-spacing="1.4">CONTRIBUTION.SKYLINE // 3D_TELEMETRY</text>
  <text x="874" y="34" text-anchor="end" font-family="monospace" font-size="11" fill="#38bdf8">22-week isometric commit elevation</text>
  <line x1="22" y1="45" x2="878" y2="45" stroke="#1e293b" stroke-width="1" />

  <!-- 3D Isometric City Grid -->
  <g>
    {''.join(buildings)}
  </g>

  <!-- Right-hand Telemetry Summary Card -->
  <g class="stat-fade">
    <rect x="655" y="68" width="218" height="262" rx="8" fill="#070b14" stroke="#172554" stroke-width="1" />
    <text x="673" y="94" font-family="monospace" font-size="10" font-weight="700" fill="#3b82f6" letter-spacing="1.2">ACTIVITY.METRICS</text>
    <line x1="673" y1="104" x2="855" y2="104" stroke="#1e293b" stroke-width="1" />

    <text x="673" y="132" font-family="monospace" font-size="11" fill="#64748b">ANNUAL CONTRIBUTIONS</text>
    <text x="673" y="162" font-family="monospace" font-size="28" font-weight="700" fill="#38bdf8">{total_contribs}</text>

    <text x="673" y="198" font-family="monospace" font-size="11" fill="#64748b">ACTIVE BUILD DAYS (22W)</text>
    <text x="673" y="226" font-family="monospace" font-size="24" font-weight="700" fill="#f8fafc">{active_days} <tspan font-size="12" fill="#34d399">days</tspan></text>

    <text x="673" y="262" font-family="monospace" font-size="11" fill="#64748b">ELEVATION SCALE</text>
    <rect x="673" y="274" width="14" height="14" rx="3" fill="#1e293b" />
    <rect x="693" y="274" width="14" height="14" rx="3" fill="#0284c7" />
    <rect x="713" y="274" width="14" height="14" rx="3" fill="#38bdf8" />
    <rect x="733" y="274" width="14" height="14" rx="3" fill="#e0f2fe" />
    <text x="756" y="285" font-family="monospace" font-size="10" fill="#94a3b8">0 → Peak</text>
  </g>
</svg>"""


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

    with open("assets/projects.svg", "w", encoding="utf-8") as f:
        f.write(build_projects_svg(scored_repos))

    with open("assets/contributions-3d.svg", "w", encoding="utf-8") as f:
        f.write(build_3d_contributions_svg(total_contribs, weeks))


if __name__ == "__main__":
    main()