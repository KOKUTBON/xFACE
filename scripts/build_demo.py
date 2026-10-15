#!/usr/bin/env python3
"""Render a self-contained Pages demo from exclusively synthetic fixtures.

No xface imports, environment files, network calls, databases or runtime data.
The demo reuses the application's static design assets (stylesheet, icon sprite,
theme script and favicon) so both frontends share one visual system.
"""

# ruff: noqa: E501
import argparse
import hashlib
import json
import shutil
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "demo"
SITE = ROOT / "site"
APP_STATIC = ROOT / "xface" / "web" / "static"
ICON_SPRITE = ROOT / "xface" / "web" / "templates" / "_icons.html"
SHARED_ASSETS = {
    "assets/xface.css": APP_STATIC / "css" / "main.css",
    "assets/theme.js": APP_STATIC / "js" / "theme.js",
    "assets/favicon.svg": APP_STATIC / "img" / "favicon.svg",
    "assets/demo.js": SOURCE / "assets" / "demo.js",
}
SUBJECTS = [
    ("Alex Morgan", "Research team", 4, "#1f3a48", "#2f6b7c", "#edbba0"),
    ("Jamie Chen", "Engineering", 3, "#262f4a", "#4a5f92", "#e9c09a"),
    ("Sam Rivera", "Design studio", 5, "#3a2e36", "#9a6450", "#c38b67"),
    ("Taylor Brooks", "Operations", 3, "#24363a", "#5d7556", "#a76f50"),
    ("Jordan Lee", "Engineering", 4, "#2d2a46", "#73629a", "#e8ba99"),
    ("Casey Patel", "Research team", 2, "#1e3540", "#3a7d92", "#b47e56"),
]
EVENTS = [
    {"time": "10:42:18", "subject": "Alex Morgan", "status": "GRANTED", "similarity": 98.4},
    {"time": "10:40:52", "subject": "Jamie Chen", "status": "GRANTED", "similarity": 96.7},
    {"time": "10:38:09", "subject": "Unknown visitor", "status": "UNKNOWN", "similarity": 42.1},
    {"time": "10:35:41", "subject": "Sam Rivera", "status": "GRANTED", "similarity": 97.2},
    {"time": "10:31:26", "subject": "Taylor Brooks", "status": "DENIED", "similarity": 78.6},
    {"time": "10:28:03", "subject": "Demo operator", "status": "MANUAL_OPEN", "similarity": None},
    {"time": "10:24:17", "subject": "Jordan Lee", "status": "GRANTED", "similarity": 95.8},
    {"time": "10:21:05", "subject": "Casey Patel", "status": "GRANTED", "similarity": 99.1},
]
DATE = "2026-10-05"
STATUS = {
    "GRANTED": ("granted", "check", "Granted", "var(--ok)"),
    "DENIED": ("denied", "x", "Denied", "var(--bad)"),
    "UNKNOWN": ("unknown", "user-unknown", "Unknown", "var(--warn)"),
    "MANUAL_OPEN": ("manual_open", "hand", "Manual", "var(--manual)"),
}


def icon(name, cls=""):
    return f'<svg class="i {cls}" aria-hidden="true" focusable="false"><use href="#i-{name}"/></svg>'


def initials(name):
    return "".join(part[0] for part in name.split()[:2]).upper()


def avatar(index):
    _, _, _, bg, shirt, skin = SUBJECTS[index]
    hair = ["#343d3c", "#252e3c", "#55372d", "#2d2625", "#47342b", "#302723"][index]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 240" role="img" aria-label="Illustrated synthetic avatar">
    <defs><radialGradient id="g" cx=".5" cy=".35" r=".75"><stop offset="0" stop-color="{bg}" stop-opacity=".55"/><stop offset="1" stop-color="{bg}"/></radialGradient></defs>
    <rect width="320" height="240" fill="#0b1118"/><rect width="320" height="240" fill="url(#g)"/>
    <g stroke="#5ce1ff" stroke-opacity=".08"><path d="M0 60h320M0 120h320M0 180h320M80 0v240M160 0v240M240 0v240"/></g>
    <path d="M61 240c8-57 47-80 99-80s91 23 99 80" fill="{shirt}"/>
    <path d="M142 143h36v40l-18 19-18-19" fill="{skin}"/>
    <ellipse cx="160" cy="101" rx="48" ry="61" fill="{hair}"/>
    <ellipse cx="160" cy="112" rx="42" ry="51" fill="{skin}"/>
    <path d="M115 94q-7-57 44-57 52 0 46 63l-15-23q-36 15-61-1z" fill="{hair}"/>
    <path d="M136 111h9m30 0h9" stroke="#343533" stroke-width="4" stroke-linecap="round"/>
    <path d="M149 136q11 8 22 0" fill="none" stroke="#8b5447" stroke-width="3" stroke-linecap="round"/>
    <path d="M159 113l-3 13h7" fill="none" stroke="#a97257" stroke-width="2"/>
    <path d="M126 182l34 20 34-20" fill="none" stroke="white" opacity=".25" stroke-width="3"/>
    </svg>'''


def tag(status):
    cls, ic, label, _ = STATUS[status]
    return f'<span class="tag {cls}">{icon(ic)}{label}</span>'


def stat(label, value, note, ic, tone=""):
    return f'''<article class="stat {tone}"><span class="stat-label">{label}</span><span class="stat-icon">{icon(ic)}</span><span class="stat-value">{value}</span><span class="stat-note">{note}</span></article>'''


def rows():
    out = []
    for i, e in enumerate(EVENTS):
        sim = e["similarity"]
        anon = e["status"] in ("UNKNOWN", "MANUAL_OPEN")
        who = (
            f'<div class="who"><span class="avatar unknown">{icon("user-unknown", "i-sm")}</span><div class="cell-stack"><span class="muted">{escape(e["subject"])}</span><small>Entrance 01</small></div></div>'
            if anon
            else f'<div class="who"><span class="avatar">{initials(e["subject"])}</span><div class="cell-stack"><strong>{escape(e["subject"])}</strong><small>Entrance 01</small></div></div>'
        )
        score = (
            f'<div class="score"><span>{sim}%</span><span class="meter"><span style="width:{sim}%;background:{STATUS[e["status"]][3]}"></span></span></div>'
            if sim is not None
            else '<span class="muted">—</span>'
        )
        relay = (
            f'<span class="relay-yes">{icon("door-open", "i-sm")} Simulated</span>'
            if e["status"] in ("GRANTED", "MANUAL_OPEN")
            else f'<span class="relay-no">{icon("lock", "i-sm")} Locked</span>'
        )
        out.append(
            f'''<tr data-status="{e["status"]}" data-subject="{escape(e["subject"].lower())}" data-name="{escape(e["subject"])}" data-time="{e["time"]}" data-similarity="{sim if sim is not None else ""}">
    <td><div class="cell-stack"><span class="mono">{e["time"]}</span><small class="mono">#{len(EVENTS) - i:03d} · {DATE}</small></div></td>
    <td>{who}</td><td>{tag(e["status"])}</td><td>{score}</td><td>{relay}</td></tr>'''
        )
    return "".join(out)


def subjects_page():
    cards = "".join(
        f'''<article class="subject-card" data-name="{name.lower()} {team.lower()}">
    <div class="portrait reticle"><span class="r-t"></span><span class="r-b"></span><img src="assets/avatar-{i}.svg" alt="Illustrated avatar for fictional subject {name}"><span class="scanline"></span><span class="portrait-badge">{icon("fingerprint")} SYN-{i + 1:03d}</span></div>
    <div class="subject-body"><div class="subject-title"><h3>{name}</h3><span class="dot live" title="Demo enrolled"></span></div>
    <div class="subject-meta"><span>{icon("face-id", "i-sm")} {samples} samples</span><span>{icon("subjects", "i-sm")} {team}</span></div>
    <div class="subject-actions"><button class="btn btn-sm" type="button" data-samples="{i}" aria-label="View synthetic samples for {name}">{icon("gallery", "i-sm")} View samples</button></div></div></article>'''
        for i, (name, team, samples, *_) in enumerate(SUBJECTS)
    )
    total = sum(s[2] for s in SUBJECTS)
    return (
        '<div class="stats">'
        + stat("Enrolled subjects", f"{len(SUBJECTS):02d}", "Fictional identities", "subjects")
        + stat("Face samples", str(total), f"Avg. {total / len(SUBJECTS):.1f} per subject · illustrations", "face-id", "ok")
        + stat("Recognition engine", f'<span class="tag ok">{icon("activity")} Ready</span>', "Synthetic scenario player", "neural", "manual")
        + stat("Match threshold", "85%", '<span class="meter" style="width:100%"><span style="width:85%;background:var(--warn)"></span></span>', "gauge", "warn")
        + "</div>"
        + f"""
    <div class="toolbar"><div class="input-icon">{icon("search")}<input id="subject-search" class="input" type="search" data-search placeholder="Search subjects or teams" aria-label="Search subjects or teams"><span class="kbd" aria-hidden="true">/</span></div><span class="count" id="subject-count">{len(SUBJECTS)} total</span></div>
    <div class="subject-grid">{cards}<div id="subject-empty" class="empty" hidden><div class="empty-icon">{icon("search")}</div><h3>No matching subjects</h3><p>No synthetic subjects match your search.</p></div></div>
    <dialog class="modal wide" id="sample-dialog" aria-labelledby="sample-title"><div class="modal-head"><span class="m-icon">{icon("gallery")}</span><div style="min-width:0"><h2 id="sample-title">Synthetic face samples</h2><p>Illustrated placeholders. No biometric templates are stored.</p></div><button class="btn btn-ghost btn-icon btn-sm" type="button" data-close aria-label="Close samples">{icon("x")}</button></div><div class="modal-body"><div class="gallery" id="sample-gallery"></div></div></dialog>"""
    )


def monitor_page():
    feed = "".join(
        f'''<li class="feed-item {STATUS[e["status"]][0]}"><span class="f-icon">{icon(STATUS[e["status"]][1])}</span><div style="min-width:0"><strong>{escape(e["subject"])}</strong><small>{STATUS[e["status"]][2]}{f" · {e['similarity']}%" if e["similarity"] is not None else ""}</small></div><time>{e["time"]}</time></li>'''
        for e in EVENTS[:5]
    )
    return f"""<div class="kiosk">
    <section class="stage" id="stage" aria-label="Synthetic camera scene">
        <img class="feed" id="monitor-avatar" src="assets/avatar-0.svg" alt="Illustrated synthetic visitor">
        <video class="feed mirror" id="monitor-video" playsinline muted hidden aria-label="Your local camera preview"></video>
        <div class="feed-grid"></div><div class="vignette"></div><div class="sweep"></div>
        <div class="frame-corners"><i></i><i></i><i></i><i></i></div>
        <svg class="faces" id="face-overlay" viewBox="0 0 320 240" preserveAspectRatio="xMidYMid meet" aria-hidden="true"></svg>
        <div class="hud hud-top"><span class="hud-pill rec"><span class="dot"></span> <span id="feed-label">DEMO FEED</span></span><span class="hud-pill hide-sm" id="feed-meta">320×240 · SYNTHETIC</span>
            <div class="end"><button class="btn btn-sm" type="button" data-camera-toggle>{icon("camera", "i-sm")} <span>Use my camera</span></button><button class="btn btn-sm" id="fullscreen" type="button">{icon("expand", "i-sm")} <span>Fullscreen</span></button></div></div>
        <div class="hud hud-bottom"><div class="hud-brand">{icon("logo")}<div>xFACE Gateway<small id="feed-source">Entrance 01 · illustrated scene</small></div></div><div class="end"><span class="hud-clock" data-clock>10:42:18</span></div></div>
    </section>
    <aside class="side">
        <section class="decision" id="decision" data-state="authorized" aria-live="polite">
            <span class="d-label">Recognition</span>
            <div class="ring"><svg viewBox="0 0 120 120" aria-hidden="true"><circle class="r-ticks" cx="60" cy="60" r="56"/><circle class="r-track" cx="60" cy="60" r="50"/><circle class="r-val" id="ring-value" cx="60" cy="60" r="50" pathLength="100" style="stroke-dasharray:98.4 100"/><circle class="r-thresh" cx="60" cy="60" r="50" pathLength="100" style="stroke-dashoffset:-84.3;opacity:.75"/></svg>
                <div class="ring-core"><svg class="i" id="decision-icon" aria-hidden="true"><use href="#i-check"/></svg></div></div>
            <h2 id="decision-title">Welcome, Alex Morgan</h2>
            <p class="d-msg" id="decision-subject">Access granted</p>
            <div class="d-score"><strong id="decision-score">98.4%</strong><small>similarity · threshold 85%</small></div>
        </section>
        <section class="door open" id="door-panel">
            <div class="door-row"><div class="door-icon"><svg class="i" aria-hidden="true"><use id="door-icon" href="#i-door-open"/></svg></div>
                <div class="door-text"><small>Door relay · simulated</small><strong id="door-state">Unlocked</strong></div>
                <span class="tag ok" id="door-tag">{icon("unlock")} Open</span></div>
            <p class="hint">All decisions and relay states are simulated.</p>
        </section>
        <section class="panel feed"><div class="panel-head"><h2>{icon("history")} Recent demo events</h2><a href="logs.html" class="btn btn-ghost btn-sm">Audit trail {icon("arrow-up-right", "i-sm")}</a></div><ul class="feed-list">{feed}</ul></section>
    </aside></div>
    <section class="panel scenario"><div><h2>Explore a recognition scenario</h2><p>Play a pre-rendered outcome, or turn on your camera to see yourself at the door. Video stays in your browser; nothing is recorded, uploaded or recognised.</p></div>
    <div class="actions"><button class="btn btn-ok" type="button" data-camera-toggle>{icon("camera")} <span>Use my camera</span></button><button class="btn" type="button" data-scenario="granted" aria-pressed="true">{icon("check")} Recognised</button><button class="btn" type="button" data-scenario="denied" aria-pressed="false">{icon("x")} Below threshold</button><button class="btn" type="button" data-scenario="unknown" aria-pressed="false">{icon("user-unknown")} Unknown visitor</button><button class="btn btn-primary" type="button" id="play-scenarios" aria-pressed="false">{icon("play")} <span>Auto-play</span></button></div></section>"""


def logs_page():
    counts = {k: sum(e["status"] == k for e in EVENTS) for k in STATUS}
    total = len(EVENTS)
    rejected = counts["DENIED"] + counts["UNKNOWN"]
    ok_pct = counts["GRANTED"] / total * 100
    bad_pct = rejected / total * 100
    top = sorted(
        {e["subject"] for e in EVENTS if e["status"] == "GRANTED"},
        key=lambda n: -next(e["similarity"] for e in EVENTS if e["subject"] == n),
    )[:5]
    rank = "".join(
        f'''<li><span class="pos">{i + 1:02d}</span><span class="who"><span class="avatar">{initials(n)}</span><span>{n}</span></span><span class="n">{next(e["similarity"] for e in EVENTS if e["subject"] == n)}%</span><span class="bar"><span style="width:{next(e["similarity"] for e in EVENTS if e["subject"] == n)}%"></span></span></li>'''
        for i, n in enumerate(top)
    )
    return (
        '<div class="stats">'
        + stat("Sample events", f"{total:02d}", "Fixed synthetic dataset", "activity")
        + stat("Granted", f"{counts['GRANTED']:02d}", f"{ok_pct:.1f}% of sample events", "door-open", "ok")
        + stat("Denied / unknown", f"{rejected:02d}", "Illustrative outcomes", "user-x", "warn")
        + stat("Manual open", f"{counts['MANUAL_OPEN']:02d}", "Simulated operator action", "hand", "manual")
        + "</div>"
        + f"""
    <div class="logs-layout"><section class="panel">
    <div class="filters compact"><div class="field"><label class="label" for="log-search">Subject</label><div class="input-icon">{icon("search")}<input id="log-search" class="input" type="search" data-search placeholder="Search a name"></div></div>
    <div class="field"><label class="label" for="log-status">Decision</label><select id="log-status" class="select"><option value="">All decisions</option><option value="GRANTED">Granted</option><option value="DENIED">Denied</option><option value="UNKNOWN">Unknown</option><option value="MANUAL_OPEN">Manual open</option></select></div>
    <div class="filter-actions"><button class="btn" type="button" id="reset-filters">{icon("x")} Reset</button><button class="btn btn-primary" type="button" id="export-csv">{icon("download")} Export CSV</button></div></div>
    <div class="table-wrap"><table class="table"><caption class="sr-only">Synthetic access events on {DATE}</caption><thead><tr><th scope="col">Event (UTC)</th><th scope="col">Subject</th><th scope="col">Decision</th><th scope="col">Similarity</th><th scope="col">Relay</th></tr></thead><tbody>{rows()}</tbody></table></div>
    <div id="log-empty" class="empty" hidden><div class="empty-icon">{icon("audit")}</div><h3>No events found</h3><p>No events match these filters.</p></div>
    <div class="panel-foot"><span id="log-count" aria-live="polite">{total} sample events</span><span>All events are fictional. Export includes only the filtered rows.</span></div></section>
    <aside class="insight"><section class="panel"><div class="panel-head"><h2>{icon("gauge")} Decision mix</h2></div><div class="panel-body donut-wrap"><div class="donut-center"><svg class="donut" viewBox="0 0 120 120" aria-hidden="true"><circle class="track" cx="60" cy="60" r="50"/><circle class="seg-ok" cx="60" cy="60" r="50" pathLength="100" stroke-dasharray="{ok_pct:.1f} 100"/><circle class="seg-bad" cx="60" cy="60" r="50" pathLength="100" stroke-dasharray="{bad_pct:.1f} 100" stroke-dashoffset="-{ok_pct:.1f}"/></svg><div class="val"><strong>{ok_pct:.0f}%</strong><small>granted</small></div></div>
    <div class="legend"><div><i style="background:var(--ok)"></i> Granted <b>{counts["GRANTED"]}</b></div><div><i style="background:var(--warn)"></i> Rejected <b>{rejected}</b></div><div><i style="background:var(--surface-3)"></i> Manual <b>{counts["MANUAL_OPEN"]}</b></div></div></div></section>
    <section class="panel"><div class="panel-head"><h2>{icon("subjects")} Best matches</h2></div><div class="panel-body"><ol class="rank">{rank}</ol></div></section></aside></div>"""
    )


def document(page, title, subtitle, eyebrow, body, sprite):
    current = 'aria-current="page"'
    nav = "".join(
        f'<a href="{url}" {current if page == key else ""}>{icon(ic)} {label}</a>'
        for key, url, ic, label in [
            ("subjects", "index.html", "subjects", "Subjects &amp; faces"),
            ("monitor", "monitor.html", "scan-face", "Live monitor"),
            ("logs", "logs.html", "audit", "Access logs"),
        ]
    )
    health = "".join(
        f'<div class="health-row">{icon(ic)} {label} <span class="state"><span class="dot live"></span> mock</span></div>'
        for ic, label in [("camera", "Camera"), ("neural", "Recognition AI"), ("relay", "Door relay")]
    )
    return f'''<!doctype html><html lang="en" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="Explore xFACE access control with a pre-rendered, fully synthetic biometric dashboard."><meta name="theme-color" content="#070a0f"><meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"><title>{title} · xFACE demo</title><link rel="icon" href="assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/xface.css"><script src="assets/theme.js"></script><script defer src="assets/demo.js"></script></head>
    <body data-page="{page}">{sprite}<a class="skip-link" href="#main">Skip to content</a><div class="shell">
    <aside class="sidebar" id="sidebar" aria-label="Primary"><a class="brand" href="index.html"><span class="brand-mark">{icon("logo")}</span><span><span class="brand-name">x<b>FACE</b></span><span class="brand-sub">Synthetic demo</span></span></a>
    <div class="nav-label">Operations</div><nav class="nav" aria-label="Demo pages">{nav}</nav>
    <section class="health" aria-label="System health"><div class="health-title"><span>System health</span><span class="dot live"></span></div>{health}</section>
    <div class="sidebar-foot"><span class="version">v2.0 · MIT</span><button class="btn btn-ghost btn-icon btn-sm" type="button" data-theme-toggle aria-label="Toggle color theme"><svg class="i" aria-hidden="true"><use href="#i-sun"/></svg></button><a class="btn btn-ghost btn-icon btn-sm" href="https://github.com/KOKUTBON/xFACE" title="Source on GitHub" aria-label="Source on GitHub">{icon("github")}</a></div></aside>
    <div class="scrim" data-nav-close></div>
    <div class="main"><header class="topbar"><button class="btn btn-ghost btn-icon menu-btn" type="button" data-nav-toggle aria-controls="sidebar" aria-expanded="false" aria-label="Open navigation">{icon("menu")}</button><div class="crumbs"><span>xFACE</span><span class="sep">/</span><strong>{title}</strong></div>
    <div class="topbar-right"><span class="clock" data-clock>10:42:18</span><button id="open-door" class="btn btn-ok" type="button">{icon("unlock")} <span>Simulate unlock</span></button></div></header>
    <main class="content" id="main"><div class="demo-banner"><span class="tag demo">{icon("info")} Synthetic demo</span><span>Illustrated people. Fictional events. No biometric service or hardware connection. The optional camera preview never leaves your browser.</span></div>
    <div class="page-head"><div><span class="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{subtitle}</p></div></div>{body}
    <footer class="site-foot"><span>Pre-rendered for GitHub Pages</span><span>100% synthetic · No backend required</span></footer><noscript><p class="panel panel-body">The dashboard is pre-rendered. Enable JavaScript for filtering, sample previews, scenario playback and CSV export.</p></noscript></main></div></div>
    <div class="toasts" id="toasts" aria-live="polite"></div></body></html>'''


def build(check=False):
    sprite = ICON_SPRITE.read_text()
    # Explicit allowlist: never copy application data, uploads, secrets or screenshots.
    rendered = {
        name: document(key, title, subtitle, eyebrow, body(), sprite)
        for name, key, title, subtitle, eyebrow, body in [
            (
                "index.html",
                "subjects",
                "Subjects &amp; faces",
                "A clear view of your enrolled identities and face samples.",
                "Enrollment",
                subjects_page,
            ),
            (
                "monitor.html",
                "monitor",
                "Live monitor",
                "Follow the journey from a face detection to an access decision.",
                "Entrance 01",
                monitor_page,
            ),
            ("logs.html", "logs", "Access logs", "Every decision, in one inspectable audit trail.", "Audit trail", logs_page),
        ]
    }
    rendered.update({f"assets/avatar-{i}.svg": avatar(i) for i in range(len(SUBJECTS))})
    rendered[".nojekyll"] = ""
    rendered["assets/fixtures.json"] = (
        json.dumps(
            {
                "synthetic": True,
                "date": DATE,
                "subjects": [{"name": s[0], "team": s[1], "samples": s[2]} for s in SUBJECTS],
                "events": EVENTS,
            },
            indent=2,
        )
        + "\n"
    )
    for name, source in SHARED_ASSETS.items():
        rendered[name] = source.read_text()
    if check:
        mismatches = [
            name
            for name, content in rendered.items()
            if not (SITE / name).is_file() or (SITE / name).read_text() != content
        ]
        extras = [
            str(p.relative_to(SITE))
            for p in SITE.rglob("*")
            if p.is_file() and str(p.relative_to(SITE)) not in rendered
        ]
        if mismatches or extras:
            raise SystemExit(f"Rebuild required. Changed: {mismatches}; unexpected: {extras}")
        print(f"Verified {len(rendered)} deterministic static files.")
        return
    SITE.mkdir(exist_ok=True)
    for path in SITE.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    for name, content in rendered.items():
        path = SITE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    digest = hashlib.sha256("".join(rendered.values()).encode()).hexdigest()[:12]
    print(f"Built {len(rendered)} static files in {SITE} ({digest}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify committed output matches sources")
    build(parser.parse_args().check)
