import html
import io
import math
import os
from datetime import datetime, timezone
import requests
from PIL import Image, ImageEnhance

USERNAME = os.getenv("GITHUB_USERNAME", "Aman-lab1")
TOKEN = os.getenv("GITHUB_TOKEN", "")
HEADERS = {"Accept": "application/vnd.github+json"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

FLAGSHIP_META = {
    "Quadruped107": {
        "desc": "8-joint autonomous quadruped robot & PyBullet kinematic twin built with Raspberry Pi 4 & Arduino.",
        "stack": "Python · C++ · PyBullet",
    },
    "Rexy": {
        "desc": "Modular personal AI assistant running a deterministic THINK -> VERIFY -> EXECUTE pipeline (Ollama + Groq).",
        "stack": "Python · FastAPI · WebSockets",
    },
    "Folio": {
        "desc": "Offline-first personal & business ledger PWA with IndexedDB persistence, PIN lock, and analytics.",
        "stack": "JavaScript · IndexedDB · PWA",
    },
    "LaserLink": {
        "desc": "Free-space OOK laser data transceiver on Arduino transmitting framed 25-note audio packets.",
        "stack": "C++ · Arduino · OOK Protocol",
    },
    "Pebble": {
        "desc": "Minimalist daily expense tracker with granular categorization and interactive spending summaries.",
        "stack": "JavaScript · HTML5 · CSS3",
    },
    "Memento": {
        "desc": "Mobile-first peer-to-peer lending & borrowing tracker with automated net balance auditing.",
        "stack": "JavaScript · LocalStorage · PWA",
    },
}

ASCII_CHARS = " .:-=+*#%@"


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
            "url": r["html_url"],
        })

    scored_repos.sort(key=lambda x: x["score"], reverse=True)
    return user, scored_repos, lang_bytes


def avatar_to_ascii(avatar_url, cols=44, rows=24):
    resp = requests.get(avatar_url, timeout=15)
    img = Image.open(io.BytesIO(resp.content)).convert("L")
    img = ImageEnhance.Contrast(img).enhance(1.45)
    img = ImageEnhance.Brightness(img).enhance(1.05)
    img = img.resize((cols, rows))

    lines = []
    for y in range(rows):
        row_chars = []
        for x in range(cols):
            px = img.getpixel((x, y))
            idx = int((px / 255) * (len(ASCII_CHARS) - 1))
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
        delay = round(0.45 + i * 0.055, 3)
        y_pos = 76 + i * 13.2
        escaped = html.escape(line)
        ascii_svg_rows.append(
            f'<text x="34" y="{y_pos:.1f}" class="ascii-row" style="animation-delay:{delay}s">{escaped}</text>'
        )

    lang_str = ", ".join(top_langs[:4]) if top_langs else "Python, C++, JavaScript, Embedded C"
    rows_info = [
        ("Subject", user.get("name") or "Aman Rajpura", "#f8fafc"),
        ("Handle", f"@{USERNAME.lower()}", "#38bdf8"),
        ("Discipline", "B.Tech EEE · Embedded Systems & Edge AI", "#cbd5e1"),
        ("Status", "Building | Prototyping | Shipping", "#34d399"),
        ("Core Stack", lang_str, "#93c5fd"),
        ("Repositories", f"{repo_count} public builds", "#e2e8f0"),
        ("Recognition", f"{total_stars} GitHub stars", "#e2e8f0"),
        ("Lab Node", "Ahmedabad University · India", "#94a3b8"),
        ("Endpoint", f"github.com/{USERNAME}", "#38bdf8"),
    ]

    info_svg_rows = []
    for idx, (k, v, color) in enumerate(rows_info):
        delay = round(0.65 + idx * 0.14, 2)
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
      font: 700 11.2px 'JetBrains Mono', 'Courier New', monospace;
      fill: #38bdf8;
      white-space: pre;
      opacity: 0;
      animation: scanReveal 0.35s ease-out forwards;
    }}
    .key-label {{ font: 500 12px 'JetBrains Mono', Consolas, monospace; fill: #64748b; }}
    .val-label {{ font: 600 12.5px 'JetBrains Mono', Consolas, monospace; }}
    .telemetry-row {{
      opacity: 0;
      transform: translateX(8px);
      animation: rowBoot 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }}
    .scan-beam {{
      animation: beamSweep 2.1s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }}
    .frame-boot {{
      stroke-dasharray: 2600;
      stroke-dashoffset: 2600;
      animation: drawBorder 1.1s ease-out forwards;
    }}
    .pulse-dot {{
      animation: pulse 2s infinite;
    }}
    @keyframes drawBorder {{
      to {{ stroke-dashoffset: 0; }}
    }}
    @keyframes scanReveal {{
      0% {{ opacity: 0; fill: #e0f2fe; }}
      60% {{ opacity: 1; fill: #7dd3fc; }}
      100% {{ opacity: 0.95; fill: #2563eb; }}
    }}
    @keyframes rowBoot {{
      to {{ opacity: 1; transform: translateX(0); }}
    }}
    @keyframes beamSweep {{
      0% {{ transform: translateY(0px); opacity: 0.95; }}
      85% {{ transform: translateY(320px); opacity: 0.95; }}
      100% {{ transform: translateY(325px); opacity: 0; }}
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.35; }}
    }}
  </style>

  <defs>
    <linearGradient id="beamGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0" />
      <stop offset="50%" stop-color="#38bdf8" stop-opacity="0.35" />
      <stop offset="100%" stop-color="#60a5fa" stop-opacity="0.9" />
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
      <line x1="22" y1="76" x2="387" y2="76" stroke="#7dd3fc" stroke-width="2" />
    </g>
  </g>

  <rect x="399" y="52" width="479" height="352" class="panel" />
  <text x="415" y="66" class="section-tag">SYSTEM.INFO // TELEMETRY</text>
  {''.join(info_svg_rows)}
</svg>"""


def build_projects_svg(scored_repos):
    top_repos = scored_repos[:4]
    max_score = max([r["score"] for r in top_repos], default=100)

    cards = []
    positions = [(22, 54), (456, 54), (22, 206), (456, 206)]

    for idx, repo in enumerate(top_repos):
        x, y = positions[idx]
        delay = round(0.3 + idx * 0.18, 2)
        pct = min(98, max(38, int((repo["score"] / max_score) * 95)))
        circumference = 2 * math.pi * 20
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
        <g class="proj-card" style="animation-delay:{delay}s">
          <rect x="{x}" y="{y}" width="422" height="138" rx="8" fill="#070b14" stroke="#1e3a8a" stroke-width="1" />
          <text x="{x + 16}" y="{y + 22}" font-family="monospace" font-size="10.5" fill="#64748b">• {USERNAME}/{html.escape(repo['name'])}</text>
          <text x="{x + 16}" y="{y + 46}" font-family="monospace" font-size="15" font-weight="700" fill="#38bdf8">{html.escape(repo['name'])} <tspan fill="#60a5fa">_</tspan></text>
          <text x="{x + 16}" y="{y + 68}" font-family="sans-serif" font-size="11.5" fill="#94a3b8">{html.escape(line1)}</text>
          <text x="{x + 16}" y="{y + 84}" font-family="sans-serif" font-size="11.5" fill="#94a3b8">{html.escape(line2)}</text>

          <rect x="{x + 16}" y="{y + 98}" width="{len(lang_badge)*6.6 + 14:.0f}" height="18" rx="4" fill="#0f172a" stroke="#1e293b" />
          <text x="{x + 23}" y="{y + 110}" font-family="monospace" font-size="10" fill="#7dd3fc">{html.escape(lang_badge)}</text>
          <text x="{x + 16}" y="{y + 129}" font-family="monospace" font-size="10" fill="#64748b">★ {repo['stars']}  ·  {repo['commits']} recent commits  ·  {time_str}</text>

          <circle cx="{x + 378}" cy="{y + 68}" r="20" fill="none" stroke="#1e293b" stroke-width="4.5" />
          <circle cx="{x + 378}" cy="{y + 68}" r="20" fill="none" stroke="#38bdf8" stroke-width="4.5"
                  stroke-dasharray="{circumference:.1f}" stroke-dashoffset="{dash_offset:.1f}"
                  stroke-linecap="round" transform="rotate(-90 {x + 378} {y + 68})" />
          <text x="{x + 378}" y="{y + 72}" text-anchor="middle" font-family="monospace" font-size="10.5" font-weight="700" fill="#f8fafc">{pct}%</text>
        </g>
        """)

    return f"""<svg width="900" height="364" viewBox="0 0 900 364" xmlns="http://www.w3.org/2000/svg">
  <style>
    .proj-card {{
      opacity: 0;
      transform: translateY(10px);
      animation: cardIn 0.45s ease-out forwards;
    }}
    @keyframes cardIn {{
      to {{ opacity: 1; transform: translateY(0); }}
    }}
  </style>
  <rect width="900" height="364" rx="12" fill="#090d16" />
  <rect x="6" y="6" width="888" height="352" rx="12" fill="#0b1120" stroke="#1e3a8a" stroke-width="1.2" />
  <text x="24" y="34" font-family="monospace" font-size="11" font-weight="700" fill="#3b82f6" letter-spacing="1.2">ACTIVE.BUILDS</text>
  <text x="145" y="34" font-family="monospace" font-size="11" fill="#64748b">./projects.sh --sort=momentum</text>
  <text x="874" y="34" text-anchor="end" font-family="monospace" font-size="11" fill="#38bdf8">auto-synced via commit velocity</text>
  <line x1="22" y1="44" x2="878" y2="44" stroke="#1e293b" stroke-width="1" />
  {''.join(cards)}
</svg>"""


def main():
    os.makedirs("assets", exist_ok=True)
    user, scored_repos, lang_bytes = fetch_github_data()

    sorted_langs = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)
    top_lang_names = [k for k, _ in sorted_langs]

    total_stars = sum(r["stars"] for r in scored_repos)
    ascii_lines = avatar_to_ascii(user["avatar_url"])

    with open("assets/hero-scan.svg", "w", encoding="utf-8") as f:
        f.write(build_hero_svg(user, ascii_lines, top_lang_names, user.get("public_repos", len(scored_repos)), total_stars))

    with open("assets/projects.svg", "w", encoding="utf-8") as f:
        f.write(build_projects_svg(scored_repos))


if __name__ == "__main__":
    main()