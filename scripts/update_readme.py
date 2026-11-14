"""Refresh the auto-generated parts of the profile README.

Marker blocks filled in README.md:
  NOW-BUILDING     most recently pushed repo of mine
  THIS-MONTH       contributions / repos / merged PRs this month
  RECENT-ACTIVITY  latest public activity, one line per repo
  LATEST-REPOS     newest repos not already featured
Also writes profile/trend-dark.svg and profile/trend-light.svg (last 30 days).
Uses only the GitHub API with GITHUB_TOKEN (public data).
"""
import html, json, os, re, urllib.request
from datetime import datetime, timedelta, timezone

USER = os.environ.get("GH_USER", "shineyrbl-byte")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = "README.md"
ACTIVITY_COUNT = 6
REPO_COUNT = 15


def api(path, body=None):
    req = urllib.request.Request(f"https://api.github.com{path}",
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Accept": "application/vnd.github+json",
                                          "User-Agent": "profile-readme-updater"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def graphql(query, **variables):
    out = api("/graphql", {"query": query, "variables": variables})
    if out.get("errors"):
        raise RuntimeError(out["errors"])
    return out["data"]


def now_building():
    for r in api(f"/users/{USER}/repos?sort=pushed&direction=desc&per_page=20&type=owner"):
        if r["fork"] or r["archived"] or r["name"] == USER:
            continue
        desc = html.escape(re.sub(r"\s+", " ", (r["description"] or "").strip()))
        return (f'<p align="center">\n  🚧 <b>Now building:</b> '
                f'<a href="{r["html_url"]}">{html.escape(r["name"])}</a>'
                + (f": {desc}" if desc else "") + "\n</p>")
    return ""


def this_month():
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    c = graphql("""query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){
        contributionsCollection(from:$f,to:$t){contributionCalendar{totalContributions}
        totalRepositoriesWithContributedCommits totalRepositoriesWithContributedPullRequests}}}""",
                u=USER, f=start.isoformat(), t=now.isoformat())["user"]["contributionsCollection"]
    merged = api(f"/search/issues?q=type:pr+author:{USER}+is:merged+merged:%3E%3D{start:%Y-%m-%d}&per_page=1")["total_count"]
    total = c["contributionCalendar"]["totalContributions"]
    repos = max(c["totalRepositoriesWithContributedCommits"], c["totalRepositoriesWithContributedPullRequests"])
    plural = lambda n, w: f"{n:,} {w}{'s' if n != 1 else ''}"
    return (f'<p align="center"><b>📅 {start:%B %Y} so far:</b> '
            f'{plural(total, "contribution")} · {plural(repos, "repo")} · {plural(merged, "PR")} merged</p>')


def trend_svgs():
    now = datetime.now(timezone.utc)
    cal = graphql("""query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){
        contributionsCollection(from:$f,to:$t){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}""",
                  u=USER, f=(now - timedelta(days=29)).isoformat(), t=now.isoformat())
    days = [d for w in cal["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
            for d in w["contributionDays"]][-30:]
    W, H, L, R, T, B = 820, 230, 48, 20, 52, 36
    peak = max([d["contributionCount"] for d in days] + [1])
    xs = [L + i * (W - L - R) / max(len(days) - 1, 1) for i in range(len(days))]
    ys = [H - B - d["contributionCount"] / peak * (H - T - B) for d in days]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = f"{L},{H - B} {line} {xs[-1]:.1f},{H - B}"
    total = sum(d["contributionCount"] for d in days)
    fmt = lambda d: datetime.strptime(d, "%Y-%m-%d").strftime("%b %d")
    themes = {"dark": dict(bg="#1a1b27", text="#a9b1d6", title="#70a5fd", line="#bf91f3", grid="#2a2c3d"),
              "light": dict(bg="#ffffff", text="#57606a", title="#2f80ed", line="#7c3aed", grid="#e5e7eb")}
    for name, c in themes.items():
        grid = "".join(f'<line x1="{L}" x2="{W - R}" y1="{T + k * (H - T - B) / 2:.1f}" y2="{T + k * (H - T - B) / 2:.1f}" stroke="{c["grid"]}"/>'
                       for k in range(3))
        dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{c["line"]}"><title>{fmt(d["date"])}: {d["contributionCount"]}</title></circle>'
                       for x, y, d in zip(xs, ys, days))
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{total} contributions in the last 30 days">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["line"]}" stop-opacity=".35"/><stop offset="1" stop-color="{c["line"]}" stop-opacity="0"/></linearGradient></defs>
<rect width="{W}" height="{H}" rx="6" fill="{c["bg"]}"/>
<g font-family="Segoe UI, Ubuntu, Helvetica, Arial, sans-serif">
<text x="{L}" y="30" fill="{c["title"]}" font-size="18" font-weight="600">Contributions · last 30 days</text>
<text x="{W - R}" y="30" fill="{c["text"]}" font-size="14" text-anchor="end">{total:,} total · peak {peak}/day</text>
{grid}
<text x="{L - 8}" y="{T + 4}" fill="{c["text"]}" font-size="11" text-anchor="end">{peak}</text>
<text x="{L - 8}" y="{H - B + 4}" fill="{c["text"]}" font-size="11" text-anchor="end">0</text>
<polygon points="{area}" fill="url(#g)"/>
<polyline points="{line}" fill="none" stroke="{c["line"]}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
{dots}
<text x="{L}" y="{H - 12}" fill="{c["text"]}" font-size="11">{fmt(days[0]["date"])}</text>
<text x="{W - R}" y="{H - 12}" fill="{c["text"]}" font-size="11" text-anchor="end">{fmt(days[-1]["date"])}</text>
</g></svg>
"""
        os.makedirs("profile", exist_ok=True)
        open(f"profile/trend-{name}.svg", "w", encoding="utf-8").write(svg)


def day(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").strftime("%b %d")


def link(full):
    return f"[{full.split('/', 1)[1] if full.startswith(USER + '/') else full}](https://github.com/{full})"


def recent_activity():
    """One summary line per repo, most recently active first.

    Event payloads are trimmed by GitHub, so URLs are built from repo + number.
    """
    events = sorted(api(f"/users/{USER}/events/public?per_page=100"),
                    key=lambda e: e["created_at"], reverse=True)
    repos = {}
    for e in events:
        repo, p, t = e["repo"]["name"], e.get("payload", {}), e["type"]
        if repo == f"{USER}/{USER}":
            continue
        r = repos.setdefault(repo, {"date": e["created_at"], "merged": [], "opened": [],
                                    "pushed": False, "created": False, "issues": [], "release": None})
        if t == "PushEvent":
            r["pushed"] = True
        elif t == "PullRequestEvent":
            pr = p.get("pull_request", {})
            n, action = pr.get("number") or p.get("number"), p.get("action")
            if action == "closed" and pr.get("merged"):
                action = "merged"
            if n and action in ("merged", "opened") and n not in r["merged"] + r["opened"]:
                r[action].append(n)
        elif t == "CreateEvent" and p.get("ref_type") == "repository":
            r["created"] = True
        elif t == "ReleaseEvent" and p.get("action") == "published":
            r["release"] = r["release"] or p.get("release", {}).get("tag_name")
        elif t == "IssuesEvent" and p.get("action") == "opened":
            n = p.get("issue", {}).get("number")
            if n:
                r["issues"].append(n)

    def prs(nums, kind):
        nums = sorted(nums, reverse=True)
        refs = ", ".join(f"[#{n}](https://github.com/{repo}/{kind}/{n})" for n in nums[:3])
        return f"{len(nums)} {'PR' if kind == 'pull' else 'issue'}{'s' if len(nums) != 1 else ''} ({refs}{', …' if len(nums) > 3 else ''})"

    lines = []
    for repo, r in repos.items():
        if r["created"]:
            line = f"🌱 Created {link(repo)}"
        elif r["release"]:
            line = f"🚀 Released {r['release']} in {link(repo)}"
        elif r["merged"]:
            line = f"🎉 Merged {prs(r['merged'], 'pull')} in {link(repo)}"
        elif r["opened"]:
            line = f"💪 Opened {prs(r['opened'], 'pull')} in {link(repo)}"
        elif r["issues"]:
            line = f"❗ Opened {prs(r['issues'], 'issues')} in {link(repo)}"
        elif r["pushed"]:
            line = f"🔨 Pushed to {link(repo)}"
        else:
            continue
        lines.append(f"- {line} · <sub>{day(r['date'])}</sub>")
        if len(lines) >= ACTIVITY_COUNT:
            break
    return "\n".join(lines) or "- Nothing public yet this week."


def latest_repos(readme_outside_markers):
    repos = api(f"/users/{USER}/repos?sort=created&direction=desc&per_page=100&type=owner")
    out = []
    for r in repos:
        url = r["html_url"]
        if r["fork"] or r["archived"] or r["name"] == USER:
            continue
        if f"{url})" in readme_outside_markers:  # already featured above
            continue
        desc = re.sub(r"\s+", " ", (r["description"] or "").strip())
        lang = f" · <sub>{r['language']}</sub>" if r["language"] else ""
        out.append(f"- [**{r['name']}**]({url})" + (f": {desc}" if desc else "") + lang)
        if len(out) >= REPO_COUNT:
            break
    return "\n".join(out)


def fill(text, name, body):
    pat = re.compile(rf"(<!-- {name}:START -->).*?(<!-- {name}:END -->)", re.S)
    return pat.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text)


text = open(README, encoding="utf-8").read()
outside = re.sub(r"<!-- (\w|-)+:START -->.*?<!-- (\w|-)+:END -->", "", text, flags=re.S)
new = fill(text, "RECENT-ACTIVITY", recent_activity())
new = fill(new, "LATEST-REPOS", latest_repos(outside))
new = fill(new, "NOW-BUILDING", now_building())
new = fill(new, "THIS-MONTH", this_month())
trend_svgs()
if new != text:
    open(README, "w", encoding="utf-8").write(new)
    print("README updated")
else:
    print("No changes")
