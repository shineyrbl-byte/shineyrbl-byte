"""Refresh the auto-generated sections of the profile README.

Fills two marker blocks:
  <!-- RECENT-ACTIVITY:START --> ... <!-- RECENT-ACTIVITY:END -->
  <!-- LATEST-REPOS:START -->    ... <!-- LATEST-REPOS:END -->
Uses only the public GitHub REST API (GITHUB_TOKEN raises the rate limit).
"""
import json, os, re, urllib.request
from datetime import datetime

USER = os.environ.get("GH_USER", "shineyrbl-byte")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = "README.md"
ACTIVITY_COUNT = 6
REPO_COUNT = 15


def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}",
                                 headers={"Accept": "application/vnd.github+json",
                                          "User-Agent": "profile-readme-updater"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


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
if new != text:
    open(README, "w", encoding="utf-8").write(new)
    print("README updated")
else:
    print("No changes")
