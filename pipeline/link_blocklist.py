"""pipeline/website_blocklist.json (hacked, taken-over, expired or another business's sites, confirmed by hand in the link sweeps)
applied to the app export. A "domain" entry covers the domain and its subdomains; a "url" entry only that page. scrub() drops every
link on the list from the exported data, whatever the field ("w", a researched source "src" or any other), so a new entry needs no
code change; scripts/make-site.py applies the same list to the website, and a unit test fails if a blocklisted host is bundled."""
import os, re, json, collections, urllib.parse

ENTRIES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "website_blocklist.json"), encoding="utf-8"))
BARE_URL = re.compile(r"(?i)^\s*https?://\S+\s*$")


def _host(u):
    return (u.hostname or "").lower().rstrip(".").removeprefix("www.")


def blocked(url):
    """The blocklist entry that covers this link, or None."""
    try:
        u = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return None
    host = _host(u)
    for b in ENTRIES:
        if b.get("match", "domain") == "url":
            v = urllib.parse.urlsplit(str(b.get("url") or ""))
            if host and host == _host(v) and u.path.rstrip("/") == v.path.rstrip("/"):
                return b
        else:
            d = re.sub(r"^[a-z]+://", "", str(b.get("domain") or "").lower()).split("/")[0].removeprefix("www.")
            if d and (host == d or host.endswith("." + d)):
                return b
    return None


def scrub(obj, drops=None):
    """Remove, in place, every blocklisted link anywhere in obj (dicts and lists, any depth). Returns a Counter of drops by field."""
    drops = collections.Counter() if drops is None else drops
    if isinstance(obj, dict):
        for k in list(obj):
            v = obj[k]
            if isinstance(v, str) and BARE_URL.match(v) and blocked(v):
                del obj[k]
                drops[k] += 1
            else:
                scrub(v, drops)
    elif isinstance(obj, list):
        for i in range(len(obj) - 1, -1, -1):
            v = obj[i]
            if isinstance(v, str) and BARE_URL.match(v) and blocked(v):
                del obj[i]
                drops["[list]"] += 1
            else:
                scrub(v, drops)
    return drops
