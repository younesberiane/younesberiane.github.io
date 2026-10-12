"""Fetch drakeo338's merged PRs in other people's repos, with star counts.

Writes data.json and refreshes the list baked into index.html, so the page
paints the full list at once and never calls the GitHub API from a browser.
"""
import datetime, json, os, re, urllib.parse, urllib.request

Q = "is:pr is:merged author:drakeo338 -user:drakeo338 -user:younesberiane"
TOKEN = os.environ.get("GITHUB_TOKEN", "")


def get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


merged, page = [], 1
while True:
    s = get("https://api.github.com/search/issues?per_page=100&page=%d&q=%s" % (page, urllib.parse.quote(Q)))
    for i in s["items"]:
        at = (i.get("pull_request") or {}).get("merged_at")
        if at:
            merged.append({"repo": i["repository_url"].split("/repos/")[1], "n": i["number"], "at": at})
    if len(s["items"]) < 100 or page * 100 >= s["total_count"]:
        break
    page += 1

stars = {}
for rp in sorted({m["repo"] for m in merged}):
    try:
        stars[rp] = get("https://api.github.com/repos/" + rp)["stargazers_count"]
    except Exception:
        pass

now = datetime.datetime.now(datetime.timezone.utc)
data = {"t": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "merged": merged, "stars": stars}
with open("data.json", "w") as f:
    json.dump(data, f, separators=(",", ":"))

rows = sorted(merged, key=lambda m: (-stars.get(m["repo"], 0), m["repo"].lower(), m["n"]))
baked = json.dumps([[m["repo"], m["n"], stars.get(m["repo"], 0), m["at"]] for m in rows], separators=(",", ":"))
html = open("index.html").read()
html = re.sub(r'var SNAP = "[^"]*";', 'var SNAP = "%s";' % now.strftime("%Y-%m-%d"), html, count=1)
html = re.sub(r"var list = \[\[.*?\]\]", lambda _: "var list = " + baked, html, count=1)
# The headline numbers in the HTML show before the script runs; keep them current.
projects = {m["repo"].lower(): stars.get(m["repo"], 0) for m in merged}
total = sum(projects.values())
# Same as fmt() in index.html.
if total >= 1e6:
    k = ("%.1f" % (round(total / 1e5) / 10)).removesuffix(".0") + "M"
elif total >= 1000:
    k = ("%.1f" % (round(total / 100) / 10)).removesuffix(".0") + "k"
else:
    k = str(total)
html = re.sub(r'(data-count="prs">)\d+', lambda m: m.group(1) + str(len(merged)), html)
html = re.sub(r'(data-count="projects">)\d+', lambda m: m.group(1) + str(len(projects)), html)
html = re.sub(r'(data-count="stars" data-fmt="k">)[^<]*', lambda m: m.group(1) + k, html)
open("index.html", "w").write(html)
print(len(merged), "merged PRs,", len(stars), "repos")
