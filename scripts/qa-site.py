"""QA for the website in docs/: static checks on every generated page, then every page in headless Chrome at phone and desktop widths.
Exits 1 on any problem. Adapted from co-eats/scripts/qa-site.py, with wi-eats' tap-target, contrast and layout-shift checks.

Static (no browser), every HTML file:
- no "every restaurant" / "all N restaurants"-style overclaims and no "checked open" anywhere (text, meta, alt text, JSON-LD), and no
  internal research note ("should be confirmed by geocoding", TODO) in any page
- a Content-Security-Policy meta before any inline block, default-src 'none', whose hashes match exactly this page's inline
  <script>/<style> blocks; the referrer meta; no inline style or on* attributes, no HTML comments, no data: favicon
- titles 50-60 and descriptions 140-160 characters, unique across indexable pages; one <h1>; canonical = its own URL; sitemap = the
  indexable pages (noindex pages stay out); 404 has no canonical; only http(s), mailto, tel or same-site links, and every same-site
  link and #anchor resolves
- JSON-LD parses, has no raw "<", no ratings or reviews; ItemList items point to an anchor on the same page; no empty streetAddress;
  phones are +1 numbers; own sites are sameAs (http/https)
- Idaho: no "google" (pages and data), no star characters, no inspection results or grades; MICHELIN only on the honors page, which
  says Idaho has none; no "James Beard finalist"; a place is never given a James Beard honor its data doesn't have (a semifinalist or
  nominee is never a winner); each guide page lists exactly the hand-checked places of its kind, its count in the title and h1; a guide
  under MIN_LIST places has no page and no links; the inspections page links each district's lookup (as listed here); each region
  page names its district and counties; each place is on one city page only, within 15 miles of that town; place pages carry Restaurant markup with geo, a #p= link
  the web app can open, the hand-check note only when the place is hand-checked, and its own district's lookup
- the web app keeps its localStorage under "ideats-" (every state site shares the github.io origin)
- no other state's app, repo or name in docs/ (allowed: the data's own words, Washington County, the Mountain region, the Denver test);
  privacy.html names every localStorage key explore.js writes; one comment only, the apple-itunes-app placeholder in <head>
- every page links mailto:nick@eatsranked.com, and work-with-nick@gmail.com appears nowhere in docs/; every footer says "Part of Eats
  Ranked" with a link to https://eatsranked.com/, and the #org Organization has that parentOrganization; dish lines are in a fixed order
- Nick's copy decisions (2026-10-13): "Confirmed listing" and "Confirmed only" (any case) nowhere in docs/, and the web app's tier label
  is "High-confidence listing"; nothing promises a TestFlight invite or link (only Nick's internal TestFlight group exists): no "we'll/you'll ... invite,
  TestFlight or beta", no "send you an invite/link", no "early access is by invite", no "ask for an invite and try it", no "a TestFlight
  invite/link" in the copy, no "Get early access" (the button and the panel ask: "Ask for early access")
- no domain or URL from pipeline/website_blocklist.json anywhere in docs/ (any case, www. or not, http or https, subdomains), and the
  blocklist is there and not empty (so the check can't pass by checking nothing)
Browser (Playwright, channel="chrome", one browser at a time): every page at 375 and 1280 px: no horizontal scroll, one <h1>, no console
errors, no CSP violations, no requests to any other host, no broken internal links or images; at 375 px every visible link, button,
input and select is at least 44x44 px (a link inside a sentence is exempt, as in WCAG 2.5.8).
The web app (explore/): loads with no layout shift (CLS < 0.05) and without detail.json; each guide lists exactly its places; a dish
search finds exactly the places that serve it; a place opens with Directions and its district's inspection lookup, as a modal dialog
at every width with the page behind it inert and focus on Close; Save uses the ideats- prefix and survives a reload; Back and Escape close
it (focus back on the row), Forward reopens it; junk under ideats-saved or ideats-guide doesn't stop the app; controls keep the page font,
and the search box and selects are 16px+ on phones;
an emoji search lists nothing; a guide search that lists under 5 places offers "See N matches in All restaurants" when more match
statewide with the same filters, and one click or Enter lists those N (Big Jud's, Boise, from the opening guide) with focus on the first;
the search box's placeholder fits with 8 px to spare at every phone width from 320 to 440 px (scrollWidth vs clientWidth); hostile #g=
hashes and a junk stored guide don't break it; #p= links from place pages open the right
place; Near me sorts by distance, asks for a fresh fix on every tap, and says so plainly from outside Idaho (Pullman, Seattle) but not
from Boise or Moscow; "Nearest" isn't claimed without a location (none yet, or denied); the map draws; the FAQPage markup matches the
visible FAQ; a failed core.json shows a retry that
works; text contrast is 4.5:1 or better in light and dark mode on the web app, its panel and map, and sample pages.

Usage: .venv/bin/python scripts/qa-site.py            (serves docs/ itself on a free port in 8853-8859; exits 1 on any problem)
       .venv/bin/python scripts/qa-site.py --static   (static checks only, a few seconds)
  QA_DOCS=<dir>    check another copy of docs/ (used to prove each check can fail)
  QA_PAGES=<n>     browser-check only the first n pages (the static checks still read every page)
  QA_WIDTHS=375    only these viewport widths (default 375,1280)
  QA_NOAPP=1       skip the web app flows
  QA_PORTS=a-b     serve on the first free port in range(a, b) instead of 8853-8859 (the machine is shared)
Never fetches any third-party site (the districts' lookups, restaurant sites): link checks are for this site's own pages only.
Until the custom domain is live the site sits under /idaho-eats/ on github.io, so the pages are served under that same path here.
"""
import base64
import functools
import glob
import hashlib
import html
import html.parser
import http.server
import json
import os
import re
import socket
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = os.path.abspath(os.environ.get("QA_DOCS") or os.path.join(ROOT, "docs"))
CNAME = os.path.join(DOCS, "CNAME")
DOMAIN = open(CNAME).read().strip() if os.path.exists(CNAME) else "nickstrom5.github.io"
BASE = re.search(r'data-base="([^"]*)"', open(os.path.join(DOCS, "index.html")).read()).group(1)
STORAGE_PREFIX = "ideats-"
OTHER_PREFIXES = ["coeats-", "ce-", "we-", "wae-", "nye-", "fleats-", "cae-", "me-"]   # the other state sites on the same github.io origin
# the public site's contact address (Nick, 2026-10-12); the old one must not appear anywhere in docs/
EMAIL, OLD_EMAILS = "nick@eatsranked.com", ["work-with-nick@gmail.com"]
# every page says it's part of the Eats Ranked family: a footer link to the hub, and the Organization names its parent
HUB, HUB_ORG = "https://eatsranked.com/", "https://eatsranked.com/#organization"
# Nick, 2026-10-13: "High-confidence listing", never "Confirmed listing"; and the site promises no TestFlight invite or link (only his
# internal TestFlight group exists), so the early-access copy ends at an ask ("Ask for early access")
OLD_LABEL = re.compile(r"confirmed\s+listing", re.I)
NEW_LABEL = "High-confidence listing"
OLD_FILTER = re.compile(r"\bconfirmed\s+only\b", re.I)   # the web app's filter is "High-confidence only" (code comments may still say "confirmed")
PROMISES = [re.compile(r"\b(we'll|we will|we'd|we would|you'll|you will|you'd|you would)\b[^.]{0,60}\b(invites?|invitations?|testflight|beta)\b", re.I),
            re.compile(r"\b(send|email|text|mail)(s|ing)? you\b[^.]{0,40}\b(invites?|invitations?|testflight|beta|link)\b", re.I),
            re.compile(r"\bget (early access|an? (testflight|beta|invite|invitation)|the (testflight|beta)( (link|build|app))?|invited)\b", re.I),
            re.compile(r"\b(early access|access|testflight|the beta)\b[^.]{0,20}\bby invit(e|ation)\b", re.I),   # "early access is by invite"
            re.compile(r"\bask for\b[^.]{0,40}\band (then )?(try|get|use|download|install)\b", re.I),         # "ask for an invite and try it"
            re.compile(r"\btestflight\s+(invit|link)", re.I)]   # offering "a TestFlight invite/link" (a mailto body is %20-encoded, so it's left alone)
# other state sites, apps and repos must not be named in this site's public files (comments in the web app's code included). Allowed:
# places' own words from the data (a "New York-style pizza" on a menu), Idaho's Washington County, the James Beard Mountain region and
# the Denver food-license test the listing confidence comes from.
OTHER_STATES = ["Wisconsin", "Colorado", "Florida", "California", "Washington", "Connecticut", "Maine", "New York", "Illinois", "Chicago",
                "Michigan", "Texas", "Denver", "Milwaukee"]
OTHER_SLUGS = [r"\b(?:wi|co|fl|ca|wa|ct|me|ny|chi|mi|tx)-eats\b", r"chicago-restaurants-ranked", r"\b(?:Wisconsin|Colorado|Florida|California|Washington|"
               r"Connecticut|Maine|New York|Michigan|Texas|WI|CO|CT|NY) Eats\b", r"\bChi(?:cago)? Ranked\b", r"\bChicago Restaurants: Ranked\b"]
OTHER_OK = ["Colorado, Montana, Utah and Wyoming", "Denver's full list of food licenses (the same map data, in Colorado)",
            "Denver's full list of food licenses (Colorado, same map data)", "Denver's full food-license list", "Payette and Washington", "Washington County"]
APP_BANNER_TODO = '<!-- <meta name="apple-itunes-app" content="app-id=APP_ID"> fill in once the App Store record exists -->'
MIN_LIST = 4          # make-site.py's MIN_LIST: a statewide list page needs this many places
PORTS = range(*map(int, os.environ["QA_PORTS"].split("-"))) if os.environ.get("QA_PORTS") else range(8853, 8860)   # QA_PORTS=8740-8750 (end exclusive)
# The district lookups (fetched once by hand on 2026-10-08; QA never fetches them). Southwest District Health has no online lookup.
DISTRICTS = {
    "Panhandle Health District": ("https://panhandlehealthdistrict.org/licensing-and-permitting/food-establishments/", "Benewah Bonner Boundary Kootenai Shoshone"),
    "Public Health – Idaho North Central District": ("https://id.healthinspections.us/idaho/food/", "Clearwater Idaho Latah Lewis Nez_Perce"),
    "Southwest District Health": ("https://swdh.id.gov/", "Adams Canyon Gem Owyhee Payette Washington"),
    "Central District Health": ("https://cdh.idaho.gov/licenses-permits-inspections/food-establishments/", "Ada Boise Elmore Valley"),
    "South Central Public Health District": ("https://phd5.idaho.gov/inspections/", "Blaine Camas Cassia Gooding Jerome Lincoln Minidoka Twin_Falls"),
    "Southeastern Idaho Public Health": ("https://inspectionsonline.us/foodsafety/idbannockpocatello/search.htm", "Bannock Bear_Lake Bingham Butte Caribou Franklin Oneida Power"),
    "Eastern Idaho Public Health": ("https://inspectionsonline.us/foodsafety/idbonnevilleidahofalls/search.htm", "Bonneville Clark Custer Fremont Jefferson Lemhi Madison Teton"),
}
COUNTY_DISTRICT = {c.replace("_", " ") + " County": d for d, (_, cs) in DISTRICTS.items() for c in cs.split()}
# the guides: web app key, the page, the tag bits (any of), the guide's section id on area pages (IdahoEats/Models/Guide.swift)
TAGS = ["basque", "fingersteak", "drivein", "spud", "huckleberry", "trout", "taqueria", "historic", "oldest", "resort"]
BIT = {t: 1 << i for i, t in enumerate(TAGS)}
GUIDES = {"basque": ("idaho-basque-restaurants.html", BIT["basque"]), "fingersteaks": ("idaho-finger-steaks-drive-ins.html", BIT["fingersteak"] | BIT["drivein"]),
          "spuds": ("idaho-spud-plates.html", BIT["spud"]), "huckleberry": ("idaho-huckleberry.html", BIT["huckleberry"]),
          "trout": ("idaho-trout-restaurants.html", BIT["trout"]), "taquerias": ("idaho-taquerias.html", BIT["taqueria"]),
          "historic": ("idaho-historic-saloons.html", BIT["historic"])}
HON_PATH, OLD_PATH, INS_PATH = "idaho-james-beard-restaurants.html", "idaho-oldest-restaurants.html", "idaho-restaurant-inspections.html"

# claims the lists can't back up: the app lists what was checked, never "every"/"all N" restaurants
OVERCLAIMS = [
    r"\bevery\s+(?:single\s+)?(?:idaho\s+|local\s+|licensed\s+)?(?:restaurant|drive-?in|bar|saloon|caf[eé]|place to eat|eatery|taquer[ií]a)",
    r"\bevery\s+place\s+in\s+(?:idaho|the\s+state)",
    r"\ball\s+(?:of\s+the\s+)?\d[\d,]*\s+(?:\w+\s+){0,2}(?:restaurants|drive-?ins|places|spots|caf[eé]s|bars|saloons|taquer[ií]as)\b",
    r"\b(?:all|every)\s+(?:the\s+)?(?:restaurants|drive-?ins|places)\s+in\s+(?:the\s+state|idaho|town)\b",
    r"\b(?:all|every)\s+(?:of\s+)?idaho'?s\s+(?:restaurants|drive-?ins)\b",
    r"\ball the restaurants?\b", r"\bsearch all\b", r"\bhas all\b",
    r"\b(?:confirmed|checked|verified)\s+open\b",            # a source's date shows when we checked, not that a place is open now
]
# a research note written for us, not for readers ("the address should be confirmed by geocoding"): it must not reach a page
INTERNAL_NOTES = [r"\bshould be (?:confirmed|checked|verified)\b", r"\bto be (?:confirmed|verified)\b", r"\bneeds? (?:confirming|verifying|checking)\b",
                  r"\bgeocod(?:ing|ed?)\b", r"\bplaceholder\b", r"(?-i:\b(?:TODO|TBD|FIXME|XXX)\b)"]
NO_INSPECTION_RESULTS = [r"\binspection (?:score|grade|result:)", r"\bhealth (?:score|grade)\b", r"\bgrade [A-F]\b", r"\bletter grade\b",
                         r"\b(?:passed|failed) (?:its|their) (?:last |latest )?inspection", r'class="(?:ex-)?res-\d']
# area-page words -> the section that backs them
AREA_KEYWORDS = [(r"basque", "basque"), (r"finger steak|drive-in", "finger-steaks"), (r"\bspud", "spuds"), (r"huckleberr", "huckleberry"),
                 (r"\btrout\b", "trout"), (r"taquer|\btacos\b", "taquerias"), (r"saloon|supper club", "historic"),
                 (r"james beard|honoree", "honors"), (r"\boldest\b", "oldest")]
JB_WORDS = {1: "America's Classic", 2: "James Beard winner", 4: "James Beard nominee", 8: "James Beard semifinalist"}


def jb_label(h, jbf):
    return ("America's Classic" if h & 1 else "James Beard winner" if h & 2 else "James Beard nominee" if h & 4
            else "James Beard semifinalist" if h & 8 else "James Beard (restaurateur)" if jbf else None)


class Page(html.parser.HTMLParser):
    """The facts the static checks need from one HTML file."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.title, self.desc, self.robots, self.canonical, self.csp, self.referrer = "", None, "", None, None, None
        self.h1s, self.ids, self.section_ids, self.alts = [], [], set(), []
        self.scripts, self.styles, self.ldjson, self.bad_attrs, self.icons = [], [], [], [], []
        self._in, self._buf, self._h1 = None, [], None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for k, v in attrs:
            if k == "style" or k.startswith("on"):
                self.bad_attrs.append(f"<{tag} {k}=…>")
        if "id" in a:
            self.ids.append(a["id"])
            if tag == "section":
                self.section_ids.add(a["id"])
        if tag == "img":
            self.alts.append(a.get("alt"))
        if tag == "meta":
            if a.get("name") == "description":
                self.desc = a.get("content", "")
            elif a.get("name") == "robots":
                self.robots = a.get("content", "")
            elif a.get("name") == "referrer":
                self.referrer = a.get("content", "")
            elif (a.get("http-equiv") or "").lower() == "content-security-policy":
                self.csp = a.get("content", "")
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")
        if tag == "link" and "icon" in (a.get("rel") or ""):
            self.icons.append(a.get("href") or "")
        if tag in ("script", "style", "title"):
            self._in, self._buf = (tag, a.get("type")), []
        if tag == "h1":
            self._h1 = []

    def handle_endtag(self, tag):
        if self._in and tag == self._in[0]:
            text = "".join(self._buf)
            kind, typ = self._in
            if kind == "title":
                self.title = text
            elif kind == "style":
                self.styles.append(text)
            elif typ == "application/ld+json":
                self.ldjson.append(text)
            elif typ in (None, "", "text/javascript", "module"):
                self.scripts.append(text)
            self._in = None
        if tag == "h1" and self._h1 is not None:
            self.h1s.append("".join(self._h1).strip())
            self._h1 = None

    def handle_data(self, data):
        if self._in:
            self._buf.append(data)
        if self._h1 is not None:
            self._h1.append(data)


def sha(s):
    return "'sha256-" + base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode() + "'"


def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield path + "." + k, k, v
            yield from walk(v, path + "." + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{path}[{i}]")


def doc_files():
    return sorted(f for f in glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True) if "/screenshots/" not in f)


def rel(f):
    return os.path.relpath(f, DOCS)


def page_url(path):
    full = f"https://{DOMAIN}{BASE}" if DOMAIN.endswith("github.io") else f"https://{DOMAIN}"
    return full + "/" + ("" if path == "index.html" else path.removesuffix("index.html"))


def file_for(path):
    """The docs/ file a site path (with or without the /idaho-eats prefix) points to, or None."""
    path = urllib.parse.unquote(path.split("#")[0].split("?")[0])
    if BASE and path.startswith(BASE + "/"):
        path = path[len(BASE):]
    f = os.path.join(DOCS, path.lstrip("/"))
    if os.path.isdir(f):
        f = os.path.join(f, "index.html")
    return f if os.path.isfile(f) else None


def sitemap_paths(problems):
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    out = []
    for u in ET.parse(os.path.join(DOCS, "sitemap.xml")).getroot().findall("s:url", ns):
        loc, lastmod = u.find("s:loc", ns).text, u.find("s:lastmod", ns)
        if lastmod is None or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", lastmod.text or ""):
            problems.append(f"sitemap: {loc} has no valid lastmod")
        p = urllib.parse.urlparse(loc)
        if p.netloc != DOMAIN:
            problems.append(f"sitemap: {loc} isn't on {DOMAIN}")
        path = p.path
        if BASE and path.startswith(BASE):
            path = path[len(BASE):]
        path = path.lstrip("/")
        out.append(path + "index.html" if path == "" or path.endswith("/") else path)
    if len(out) != len(set(out)):
        problems.append("sitemap: duplicate URLs")
    for p in out:
        if not os.path.isfile(os.path.join(DOCS, p)):
            problems.append(f"sitemap: {p} has no file")
    return out


def slugify(s):   # make-site.py's slug()
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("'", "").replace("’", "")).strip("-")


def miles(a, b):
    import math
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " " + re.sub(r"[^a-z0-9]+", " ", s.replace("'", "").replace("’", "")).strip() + " "


def load_data():
    core = json.load(open(os.path.join(DOCS, "data", "core.json")))
    detail = json.load(open(os.path.join(DOCS, "data", "detail.json")))
    C = core["cols"]
    places = []
    for i in range(len(C["id"])):
        places.append({"i": i, "id": str(C["id"][i]), "n": C["n"][i], "c": core["cities"][C["c"][i]] if C["c"][i] is not None else None,
                       "co": core["counties"][C["co"][i]] if C["co"][i] is not None else None, "g": C["g"][i] or 0, "hc": C["hc"][i] == 1,
                       "v": C["v"][i] == 1, "h": C["h"][i] or 0, "f": C["f"][i], "jb": C["jb"][i] == 1, "dish": C["dish"][i] or "", "a": C["a"][i] or "",
                       "la": C["la"][i], "lo": C["lo"][i],
                       "jbf": (detail[i] or {}).get("jbf", "")})
    return core, detail, places


BLOCKLIST = os.path.join(ROOT, "pipeline", "website_blocklist.json")


def blocklist_hits():
    """Every blocklisted domain (and its subdomains) or exact URL that still appears in a file under docs/."""
    out = []
    try:
        entries = json.load(open(BLOCKLIST, encoding="utf-8"))
    except FileNotFoundError:
        return [f"{BLOCKLIST}: missing (make-site.py drops the websites listed there)"]
    if not isinstance(entries, list) or not entries:   # an empty list would let this check pass without checking anything
        return [f"{BLOCKLIST}: empty or not a list (it has had entries since 2026-10-12; make-site.py drops the websites listed there)"]
    pats = []
    for b in entries:
        if not isinstance(b, dict) or not b.get("domain") or b.get("match", "domain") not in ("domain", "url") or not b.get("reason"):
            out.append(f"website_blocklist.json: malformed entry {b!r}")
            continue
        if b.get("match", "domain") == "domain":
            d = b["domain"].lower().strip().removeprefix("www.")
            pats.append((b["domain"], re.compile(r"(?<![a-z0-9-])" + re.escape(d) + r"(?![a-z0-9-])", re.I)))
        else:   # one exact page: scheme, www. and a trailing slash don't matter
            u = re.sub(r"^https?://(www\.)?", "", (b.get("url") or b["domain"]).strip(), flags=re.I).rstrip("/")
            pats.append((u, re.compile(r"(?<![a-z0-9-])" + re.escape(u) + r"/?(?![a-z0-9/_-])", re.I)))
    for f in glob.glob(os.path.join(DOCS, "**", "*"), recursive=True):
        if not os.path.isfile(f) or f.endswith((".png", ".webp", ".ico", ".jpg")):
            continue
        raw = open(f, encoding="utf-8", errors="ignore").read()
        flat = html.unescape(raw.replace("\\/", "/"))
        for name, rx in pats:
            if rx.search(flat):
                out.append(f"{rel(f)}: publishes the blocklisted website {name!r} (pipeline/website_blocklist.json)")
    return out


def guide_members(places, bits):
    return [p for p in places if p["hc"] and p["g"] & bits and not p["v"]]


def static_checks():
    problems = []
    pages = {rel(f): open(f, encoding="utf-8").read() for f in doc_files()}
    parsed = {p: Page(t) for p, t in pages.items()}
    in_sitemap = set(sitemap_paths(problems))
    core, detail, places = load_data()
    by_id = {p["id"]: p for p in places}
    titles, descs = {}, {}
    _ids = {}

    def ids_in(path):
        if path not in _ids:
            _ids[path] = set(Page(open(os.path.join(DOCS, path), encoding="utf-8").read()).ids) if path.endswith(".html") else set()
        return _ids[path]

    for path, text in pages.items():
        pg = parsed[path]
        where = path
        indexed = "noindex" not in pg.robots
        # --- overclaims and wording: everything a reader or a crawler sees (CSS aside)
        visible = html.unescape(re.sub(r"<style>.*?</style>", " ", text, flags=re.S))
        visible = re.sub(r"\s+", " ", visible.replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&"))
        for rx in OVERCLAIMS:
            for m in re.finditer(rx, visible, re.I):
                problems.append(f"{where}: overclaim \"{m.group(0)}\" (…{visible[max(0, m.start() - 40):m.end() + 20]}…)")
        prose = " ".join([pg.title, pg.desc or "", re.sub(r"<[^>]+>", " ", re.sub(r"<script>.*?</script>", " ", visible, flags=re.S))])   # text, not markup
        for rx in INTERNAL_NOTES:
            for m in re.finditer(rx, prose, re.I):
                problems.append(f"{where}: an internal research note reached the page: \"{m.group(0)}\" (…{prose[max(0, m.start() - 60):m.end() + 10]}…)")
                break
        for rx in NO_INSPECTION_RESULTS:
            if re.search(rx, visible if not rx.startswith("class") else text, re.I):
                problems.append(f"{where}: inspection results or grades ({rx}); Idaho publishes none")
        low = visible.lower()
        if "google" in low:
            problems.append(f"{where}: mentions Google")
        if re.search("[★☆⭐]", visible):
            problems.append(f"{where}: star characters")
        if "james beard finalist" in low:
            problems.append(f"{where}: says 'James Beard finalist' (the Foundation's word is nominee)")
        if "michelin" in low and path != HON_PATH:
            problems.append(f"{where}: mentions MICHELIN (only the honors page says Idaho has no MICHELIN Guide)")
        # --- CSP
        if not pg.csp:
            problems.append(f"{where}: no Content-Security-Policy meta")
        else:
            m = text.find('http-equiv="Content-Security-Policy"')
            first_inline = min([i for i in (text.find("<style>"), text.find("<script>"), text.find("<script type=")) if i >= 0] or [len(text)])
            if m > first_inline:
                problems.append(f"{where}: the CSP meta comes after an inline block, so it doesn't cover it")
            pol = {d.split()[0]: d.split()[1:] for d in (x.strip() for x in pg.csp.split(";")) if d}
            if pol.get("default-src") != ["'none'"]:
                problems.append(f"{where}: CSP default-src isn't 'none'")
            for name, blocks in (("script-src", pg.scripts), ("style-src", pg.styles)):
                allowed = pol.get(name, [])
                if any(x in allowed for x in ("'unsafe-inline'", "'unsafe-eval'", "*", "https:", "data:", "'self'")):
                    problems.append(f"{where}: CSP {name} is loose: {allowed}")
                need = {sha(b) for b in blocks}
                have = {x for x in allowed if x.startswith("'sha256-")}
                if need - have:
                    problems.append(f"{where}: an inline {name.split('-')[0]} block isn't in the CSP")
                if have - need:
                    problems.append(f"{where}: the CSP {name} allows a hash no block on the page has")
            for need in ("base-uri", "form-action", "connect-src", "img-src", "object-src"):
                if need not in pol:
                    problems.append(f"{where}: CSP has no {need}")
            if pol.get("connect-src") != ["'self'"]:
                problems.append(f"{where}: CSP connect-src isn't 'self'")
        if pg.referrer != "strict-origin-when-cross-origin":
            problems.append(f"{where}: no referrer meta")
        if pg.bad_attrs:
            problems.append(f"{where}: inline style/event attributes break the CSP: {pg.bad_attrs[:3]}")
        # the one comment allowed: the SEO spec's Smart App Banner placeholder in <head>, until the real meta tag replaces it
        comments = re.findall(r"<!--.*?-->", text, re.S)
        if any(c != APP_BANNER_TODO for c in comments) or text.count("<!--") != len(comments):
            problems.append(f"{where}: HTML comment left in the output")
        if 'name="apple-itunes-app"' not in text.replace(APP_BANNER_TODO, ""):
            if comments != [APP_BANNER_TODO] or text.find(APP_BANNER_TODO) > text.find("</head>"):
                problems.append(f"{where}: no apple-itunes-app meta and no commented placeholder for it in <head>")
        if any(i.startswith("data:") for i in pg.icons):
            problems.append(f"{where}: data: favicon")
        # --- contact address and the Eats Ranked family (every page, 404, privacy, terms and the web app included)
        if f"mailto:{EMAIL}" not in text:
            problems.append(f"{where}: no mailto:{EMAIL} link")
        foot = re.search(r"<footer>(.*?)</footer>", text, re.S)
        foot_text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", foot.group(1)))) if foot else ""
        if not foot or not re.search(r'<a href="' + re.escape(HUB) + r'"[^>]*>Eats Ranked</a>', foot.group(1)) \
                or "Part of Eats Ranked, restaurant apps state by state." not in foot_text:
            problems.append(f"{where}: the footer doesn't say 'Part of Eats Ranked' with a link to {HUB}")
        orgs = [b for raw in pg.ldjson for b in ((lambda ld: [ld] + ld.get("@graph", []) if isinstance(ld, dict) else [])(json.loads(raw)))
                if isinstance(b, dict) and b.get("@type") == "Organization" and str(b.get("@id", "")).endswith("/#org")]
        po = (orgs[0].get("parentOrganization") or {}) if orgs else {}
        if not orgs or po.get("@id") != HUB_ORG or po.get("url") != HUB or po.get("name") != "Eats Ranked":
            problems.append(f"{where}: the #org Organization has no parentOrganization {HUB_ORG}")
        # --- FAQPage markup says exactly what the visible questions and answers say, in the same order (Google's rule)
        faqs = [b for raw in pg.ldjson for b in ((lambda ld: [ld] + ld.get("@graph", []) if isinstance(ld, dict) else [])(json.loads(raw)))
                if isinstance(b, dict) and b.get("@type") == "FAQPage"]
        flat = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()   # noqa: E731
        shown = [(flat(q), flat(a)) for q, a in re.findall(r"<details><summary>(.*?)</summary><p>(.*?)</p></details>", text, re.S)]
        for fq in faqs:
            marked = [(flat(m.get("name", "")), flat((m.get("acceptedAnswer") or {}).get("text", ""))) for m in fq.get("mainEntity", [])]
            if marked != shown:
                diff = next(((a, b) for a, b in zip(marked, shown + [("", "")] * len(marked)) if a != b), None)
                problems.append(f"{where}: FAQPage markup doesn't match the visible FAQ ({len(marked)} vs {len(shown)} questions; first difference {diff})")
        if shown and not faqs:
            problems.append(f"{where}: a visible FAQ with no FAQPage markup")
        # --- the "dishes named most often" lines: most first, ties A to Z, so a rebuild of the same data writes the same page
        dish_lines = re.findall(r"(?i)dishes these menus name most: (.*?)\.</p>", text)
        if path in [GUIDES[k][0] for k in ("basque", "fingersteaks", "spuds", "huckleberry", "trout", "taquerias")] and not dish_lines:
            problems.append(f"{where}: no 'Dishes these menus name most' line (the dish-order check can't run)")
        for word, rx in (("Huckleberry", r"huckleberr"), ("Trout", r"trout")):   # a topical guide's dish line names its own food only
            for m in re.finditer(word + r" dishes these menus name most: (.*?)\.</p>", text):
                off = [d for d, _ in re.findall(r"(.+?) \((\d+)\)(?:, |$)", html.unescape(m.group(1))) if not re.search(rx, d)]
                if off:
                    problems.append(f"{where}: the {word.lower()} dish line lists other food: {off[:3]}")
        for m in re.finditer(r"(?i)dishes these menus name most: (.*?)\.</p>", text):
            got = re.findall(r"(.+?) \((\d+)\)(?:, |$)", html.unescape(m.group(1)))
            if got != sorted(got, key=lambda x: (-int(x[1]), x[0])):
                problems.append(f"{where}: the dish line isn't in count-then-name order (the build isn't deterministic): {m.group(1)[:90]}")
        # --- titles, descriptions, headings, sitemap
        if len(pg.h1s) != 1:
            problems.append(f"{where}: {len(pg.h1s)} <h1>")
        if path == "404.html":
            if pg.canonical or 'property="og:url"' in text:
                problems.append("404.html: has a canonical or og:url")
            if 'href="' + BASE + '/explore/"' not in text:
                problems.append("404.html: no search link")
        else:
            if not 50 <= len(pg.title) <= 60:
                problems.append(f"{where}: title is {len(pg.title)} characters: {pg.title}")
            if pg.desc is None or not 140 <= len(pg.desc) <= 160:
                problems.append(f"{where}: description is {len(pg.desc or '')} characters")
        if indexed and path != "404.html":
            if pg.title in titles:
                problems.append(f"{where}: same title as {titles[pg.title]}")
            if pg.desc in descs:
                problems.append(f"{where}: same description as {descs[pg.desc]}")
            titles[pg.title], descs[pg.desc] = path, path
            if path not in in_sitemap:
                problems.append(f"{where}: indexable but not in sitemap.xml")
            if pg.canonical != page_url(path):
                problems.append(f"{where}: canonical {pg.canonical} != {page_url(path)}")
        elif path in in_sitemap:
            problems.append(f"{where}: noindex page is in sitemap.xml")
        for a in pg.alts:
            if not a:
                problems.append(f"{where}: an <img> has no alt text")
        dup_ids = {i for i in pg.ids if pg.ids.count(i) > 1}
        if dup_ids:
            problems.append(f"{where}: duplicate ids {sorted(dup_ids)[:5]}")
        # --- area pages: the title, h1 and description promise only what's on the page
        if (path.startswith("cities/") and path != "cities/index.html") or path.startswith("regions/"):
            promise = " ".join([pg.title, pg.h1s[0] if pg.h1s else "", pg.desc or ""]).lower()
            for rx, sec in AREA_KEYWORDS:
                if re.search(rx, promise) and sec not in pg.section_ids:
                    problems.append(f"{where}: title/h1/description mention {rx!r} but the page has no #{sec} section")
        # --- JSON-LD
        for raw in pg.ldjson:
            try:
                ld = json.loads(raw)
            except ValueError as ex:
                problems.append(f"{where}: bad JSON-LD ({ex})")
                continue
            if "<" in raw:
                problems.append(f"{where}: JSON-LD contains a raw '<'")
            for p, k, v in walk(ld):
                if k in ("aggregateRating", "review", "reviews", "reviewRating", "ratingValue", "reviewCount", "bestRating"):
                    problems.append(f"{where}: JSON-LD has {k} at {p}")
                if k == "streetAddress" and not str(v).strip():
                    problems.append(f"{where}: empty streetAddress at {p}")
                if k == "telephone" and not re.fullmatch(r"\+1\d{10}", str(v)):
                    problems.append(f"{where}: telephone {v!r} isn't a +1 number")
                if k == "sameAs" and isinstance(v, str) and not re.match(r"https?://", v):
                    problems.append(f"{where}: sameAs {v!r} isn't http(s)")
            for block in ([ld] + ld.get("@graph", [])) if isinstance(ld, dict) else []:
                if block.get("@type") != "ItemList":
                    continue
                own_url = pg.canonical or page_url(path)
                items = block.get("itemListElement", [])
                if block.get("numberOfItems") != len(items):
                    problems.append(f"{where}: ItemList numberOfItems {block.get('numberOfItems')} != {len(items)}")
                for li in items:
                    it = li.get("item", {})
                    u = it.get("url", "")
                    if not u.startswith(own_url + "#"):
                        problems.append(f"{where}: ItemList item {it.get('name')!r} url {u!r} isn't on this page")
                    elif u.split("#", 1)[1] not in pg.ids:
                        problems.append(f"{where}: ItemList item {it.get('name')!r} points to #{u.split('#', 1)[1]}, which isn't on the page")
        # --- links: only http(s), mailto and tel leave the site; every same-site link and #anchor resolves
        markup = re.sub(r"<script>.*?</script>", "", text, flags=re.S)     # links the web app builds are checked in the browser
        for tag, ref in re.findall(r'<(a|img|link|source|script)\b[^>]*?\s(?:href|src|srcset)="([^"]*)"', markup):
            ref = html.unescape(ref)
            scheme = urllib.parse.urlsplit(ref).scheme.lower()
            if scheme in ("http", "https"):
                if tag == "a" and urllib.parse.urlsplit(ref).netloc == DOMAIN and not DOMAIN.endswith("github.io"):
                    problems.append(f"{where}: absolute link to our own site {ref}")
                continue
            if scheme == "mailto":
                continue
            if scheme == "tel":
                if not re.fullmatch(r"tel:\+?\d{10,15}", ref):
                    problems.append(f"{where}: bad tel: link {ref}")
                continue
            if scheme:
                problems.append(f"{where}: link with scheme {scheme}: {ref[:60]}")
                continue
            target = urllib.parse.urljoin("/" + (BASE.strip("/") + "/" if BASE else "") + path, ref)
            tpath, _, frag = target.partition("#")
            f = file_for(tpath) if tpath else os.path.join(DOCS, path)
            if not f:
                problems.append(f"{where}: broken link {ref}")
            elif frag and f.endswith(".html") and "/explore/" not in f and frag not in ids_in(rel(f)):
                problems.append(f"{where}: link to a missing anchor {ref}")
        # --- the App Store button has no Apple logo until it's Apple's own badge
        for m in re.finditer(r'<a class="btn store-btn"[^>]*>(.*?)</a>', text, re.S):
            if "<svg" in m.group(1):
                problems.append(f"{where}: the early-access button carries an Apple logo")
        # --- James Beard chips on lists match the data (a semifinalist or nominee is never a winner)
        for m in re.finditer(r'<li id="([^"]+)"><h3><a href="[^"]*/places/([^"/]+)\.html">.*?</li>', text, re.S):
            ppath = f"places/{m.group(2)}.html"
            pid = re.search(r'/explore/#p=([0-9a-zA-Z]+)"', pages.get(ppath, "")) if ppath in pages else None
            if not pid or pid.group(1) not in by_id:
                problems.append(f"{where}: list item {m.group(2)} links a place page with no web-app id")
                continue
            p = by_id[pid.group(1)]
            chips = re.findall(r'<span class="tag tag-jb">([^<]*)</span>', m.group(0))
            want = jb_label(p["h"], p["jbf"])
            if [html.unescape(c) for c in chips] != ([want] if want else []):
                problems.append(f"{where}: {p['n']!r} shows James Beard chip {chips}, data says {want!r}")
    # --- other state sites: no other state's app, repo or (outside the allowed facts) name anywhere in docs/
    names_in_data = set()
    for x in core["cols"]["n"] + core["cols"]["a"] + core["cols"]["dish"] + core["cities"] + core["counties"] + core["cuisines"] + core["brands"] \
            + [v for d in detail for v in (d or {}).values() if isinstance(v, str)]:
        if x and any(st in str(x) for st in OTHER_STATES):
            names_in_data.add(str(x))
    for f in glob.glob(os.path.join(DOCS, "**", "*"), recursive=True):
        if not os.path.isfile(f) or f.endswith((".png", ".webp", ".ico", ".jpg")) or "/licenses/" in f:
            continue
        raw = open(f, encoding="utf-8", errors="ignore").read()
        flat = html.unescape(raw.replace("\\u0026", "&"))
        for rx in OTHER_SLUGS:
            for m in re.finditer(rx, flat):
                problems.append(f"{rel(f)}: names another state's app or repo: {m.group(0)!r}")
        if f.endswith(".json"):
            continue   # the data is the places' own words
        for ok in sorted(names_in_data | set(OTHER_OK), key=len, reverse=True):
            flat = flat.replace(ok, " ")
        for st in OTHER_STATES:
            for m in re.finditer(r"\b" + re.escape(st) + r"\b", flat):
                problems.append(f"{rel(f)}: names {st} (…{flat[max(0, m.start() - 50):m.end() + 30]}…)")
                break
    # --- the old contact address, anywhere in docs/ (pages, data, manifest, license copies)
    for f in glob.glob(os.path.join(DOCS, "**", "*"), recursive=True):
        if os.path.isfile(f) and not f.endswith((".png", ".webp", ".ico", ".jpg")):
            raw = open(f, encoding="utf-8", errors="ignore").read()
            for old in OLD_EMAILS:
                if old in raw:
                    problems.append(f"{rel(f)}: has the old contact address {old} (the site uses {EMAIL})")
    # --- Nick's copy decisions (2026-10-13), over every text file in docs/ (pages, attributes, JSON-LD, the web app's code and data;
    # entities decoded, curly apostrophes straightened): no "Confirmed listing", and no promise of a TestFlight invite or link
    for f in glob.glob(os.path.join(DOCS, "**", "*"), recursive=True):
        if os.path.isfile(f) and f.endswith((".html", ".json", ".txt", ".xml", ".webmanifest", ".js", ".css")):
            flat = html.unescape(open(f, encoding="utf-8", errors="ignore").read()).replace("\u2019", "'")
            if OLD_LABEL.search(flat):
                problems.append(f"{rel(f)}: says \"Confirmed listing\" (the label is \"{NEW_LABEL}\")")
            if OLD_FILTER.search(flat):
                problems.append(f"{rel(f)}: says \"Confirmed only\" (a filter for it would be \"High-confidence only\")")
            for rx in PROMISES:
                m = rx.search(flat)
                if m:
                    problems.append(f"{rel(f)}: promises a TestFlight invite or early access: {m.group(0)!r} (the copy ends at an ask)")
    if not re.search(r'const TIER = \{[^}]*1: "' + re.escape(NEW_LABEL) + '"', pages.get("explore/index.html", "")):
        problems.append(f"explore/index.html: the place panel's tier label isn't \"{NEW_LABEL}\"")
    # --- blocklisted restaurant websites (hacked, expired, another business's or a directory's page; pipeline/website_blocklist.json):
    # never anywhere in docs/, as a link, as text or in the web app's data, in any case, with or without www. or the scheme
    problems += blocklist_hits()
    # --- the web app's storage keys
    ex = parsed.get("explore/index.html")
    if ex:
        js = "\n".join(ex.scripts)
        if not re.search(r'const PREFIX = "' + re.escape(STORAGE_PREFIX) + '";', js):   # the code's own constant, not a comment
            problems.append(f"explore/index.html: localStorage prefix {STORAGE_PREFIX!r} not found")
        for m in re.finditer(r"""localStorage\.(?:get|set|remove)Item\(\s*(["'`])([^"'`]*)\1""", js):
            if not m.group(2).startswith(STORAGE_PREFIX):
                problems.append(f"explore/index.html: localStorage key {m.group(2)!r} doesn't start with {STORAGE_PREFIX!r}")
        for other in OTHER_PREFIXES:
            if re.search(r"""["'`]""" + re.escape(other) + r"""["'`]""", js):
                problems.append(f"explore/index.html: uses another state site's storage prefix {other!r}")
        if re.search(r"michelin", js, re.I):
            problems.append("explore/index.html: the web app mentions MICHELIN")
        keys = [m.group(1) for m in re.finditer(r'store\.set\("([a-z]+)"', js)]
        priv = html.unescape(pages.get("privacy.html", ""))
        for k in dict.fromkeys(keys):
            if STORAGE_PREFIX + k not in priv:
                problems.append(f"privacy.html: doesn't name the web app's localStorage key {STORAGE_PREFIX + k!r}")
        if not keys:
            problems.append("explore/index.html: no store.set(...) keys found (the privacy check needs them)")
    else:
        problems.append("explore/index.html is missing")
    problems += idaho_checks(pages, parsed, core, detail, places, in_sitemap)
    return problems, len(pages)


def idaho_checks(pages, parsed, core, detail, places, in_sitemap):
    problems = []
    rest = [p for p in places if not p["v"]]
    # --- each guide: a page with exactly its places when it has MIN_LIST of them, otherwise no page and no links
    lists = {k: (path, guide_members(places, bits)) for k, (path, bits) in GUIDES.items()}
    lists["honors"] = (HON_PATH, [p for p in rest if p["jb"]])
    lists["oldest"] = (OLD_PATH, [p for p in rest if p["f"] is not None])
    place_id_of = {}
    for path, text in pages.items():
        if path.startswith("places/"):
            m = re.search(r'/explore/#p=([0-9a-zA-Z]+)"', text)
            if m:
                place_id_of[path.removeprefix("places/").removesuffix(".html")] = m.group(1)
    for k, (path, ps) in lists.items():
        if len(ps) >= MIN_LIST:
            if path not in pages:
                problems.append(f"{k}: {len(ps)} places but no page {path}")
                continue
            text = pages[path]
            listed = re.findall(r'<li id="([^"]+)"><h3><a href="[^"]*/places/([^"/]+)\.html">', text)
            got = sorted(place_id_of.get(s, "?" + s) for _, s in listed)
            want = sorted(p["id"] for p in ps)
            if got != want:
                problems.append(f"{path}: lists {len(got)} places, the data has {len(want)} for this guide "
                                f"(extra {sorted(set(got) - set(want))[:4]}, missing {[by['n'] for by in ps if by['id'] not in got][:4]})")
            n = len(ps)
            pg = parsed[path]
            if k not in ("honors", "oldest") and not re.search(rf"\b{n}\b", pg.title):
                problems.append(f"{path}: the title doesn't carry the count {n}: {pg.title!r}")
            if not re.search(rf"\b{n}\b|\b{['zero','one','two','three','four','five','six','seven','eight','nine'][n] if n < 10 else n}\b", pg.desc or "", re.I):
                problems.append(f"{path}: the description doesn't carry the count {n}")
        else:
            if path in pages:
                problems.append(f"{k}: only {len(ps)} places (< {MIN_LIST}) but {path} exists")
            for other, text in pages.items():
                if re.search(r'href="[^"]*/' + re.escape(path) + '[#"]', text):
                    problems.append(f"{other}: links {path}, which has fewer than {MIN_LIST} places and no page")
    # --- the inspections page: each district's own lookup, and no results
    ins = pages.get(INS_PATH)
    if not ins:
        problems.append(f"missing page {INS_PATH}")
    else:
        for d, (url, counties) in DISTRICTS.items():
            if html.escape(d) not in ins and d not in ins:
                problems.append(f"{INS_PATH}: doesn't name {d}")
            if f'href="{html.escape(url)}"' not in ins:
                problems.append(f"{INS_PATH}: doesn't link {d}'s {url}")
            for c in counties.split():
                if c.replace("_", " ") not in ins:
                    problems.append(f"{INS_PATH}: doesn't list {c} County under {d}")
        if "No online lookup" not in ins:
            problems.append(f"{INS_PATH}: doesn't say Southwest District Health has no online lookup")
    for k in ("index.html", "about.html", "privacy.html", "terms.html", "explore/index.html", "cities/index.html", "404.html"):
        if k not in pages:
            problems.append(f"missing page {k}")
    # --- region pages name their district and every county in it
    regions = [p for p in pages if p.startswith("regions/")]
    if len(regions) != len(DISTRICTS):
        problems.append(f"{len(regions)} region pages, want one per district ({len(DISTRICTS)})")
    for r in regions:
        text = html.unescape(pages[r])
        ds = [d for d in DISTRICTS if d in text]
        if not ds:
            problems.append(f"{r}: names no health district")
            continue
        d = max(ds, key=lambda x: text.count(x))
        for c in DISTRICTS[d][1].split():
            if c.replace("_", " ") not in text:
                problems.append(f"{r}: doesn't name {c} County, part of {d}")
    # --- each place is on one city page only (each place on its nearest city page)
    seen = {}
    for c in [p for p in pages if p.startswith("cities/") and p != "cities/index.html"]:
        for s in set(re.findall(r'<h3><a href="[^"]*/places/([^"/]+)\.html">', pages[c])):
            if s in seen:
                problems.append(f"{c}: lists {s}, which is already on {seen[s]}")
            seen[s] = c
        if f'href="{BASE}/{c}"' not in pages.get("cities/index.html", ""):
            problems.append(f"cities/index.html doesn't link {c}")
    by_id = {p["id"]: p for p in places}
    # --- a place on a city page is within 15 miles (make-site.py's RADIUS) of the town's center (the median of its places), so a
    # lodge with a far-off town's mailing address isn't listed "in" that town
    pts = {}
    for p in rest:
        if p["la"] is not None and p["c"]:
            pts.setdefault(p["c"], []).append((p["la"], p["lo"]))
    center = {c: (sorted(a for a, _ in v)[len(v) // 2], sorted(b for _, b in v)[len(v) // 2]) for c, v in pts.items()}
    town_of = {slugify(c): c for c in center}
    for c in [p for p in pages if p.startswith("cities/") and p != "cities/index.html"]:
        town = town_of.get(c.removeprefix("cities/").removesuffix(".html"))
        if not town:
            problems.append(f"{c}: no town in the data has this page's name")
            continue
        for s in set(re.findall(r'<h3><a href="[^"]*/places/([^"/]+)\.html">', pages[c])):
            p = by_id.get(place_id_of.get(s, ""))
            if p and p["la"] is not None and miles(center[town], (p["la"], p["lo"])) > 15:
                problems.append(f"{c}: lists {p['n']!r}, {miles(center[town], (p['la'], p['lo'])):.0f} miles from {town}")
    # --- place pages: Restaurant markup, a #p= link the web app opens, the right hand-check note and district lookup
    core_ids = set(str(x) for x in core["cols"]["id"])
    by_id = {p["id"]: p for p in places}
    for path in [p for p in pages if p.startswith("places/")]:
        s = pages[path]
        lds = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)]
        r = [x for x in lds if x.get("@type") == "Restaurant"]
        if not r or not r[0].get("name") or not r[0].get("address", {}).get("streetAddress") or not r[0].get("geo", {}).get("latitude"):
            problems.append(f"{path}: no Restaurant JSON-LD with name, address and geo")
        m = re.search(r'/explore/#p=([0-9a-zA-Z]+)"', s)
        if not m or m.group(1) not in core_ids:
            problems.append(f"{path}: no #p= link the web app can open")
            continue
        p = by_id[m.group(1)]
        if not (p["hc"] or p["jb"]) or p["v"]:
            problems.append(f"{path}: {p['n']!r} is neither hand-checked nor honored (or isn't a restaurant) but has a page")
        if ("Checked by hand in" in s) != p["hc"]:
            problems.append(f"{path}: the hand-check note {'is missing' if p['hc'] else 'is on a place that is not hand-checked'}")
        d = COUNTY_DISTRICT.get(p["co"] or "")
        url = DISTRICTS[d][0] if d else None
        if d and f'href="{html.escape(url)}"' not in s:
            problems.append(f"{path}: doesn't link its district's ({d}) inspection lookup")
        wrong = [x for x, (u, _) in DISTRICTS.items() if x != d and f'href="{html.escape(u)}"' in s]
        if wrong:
            problems.append(f"{path}: links another district's lookup ({wrong[0]})")
        if html.unescape(parsed[path].h1s[0] if parsed[path].h1s else "") != p["n"]:
            problems.append(f"{path}: h1 isn't the place's name {p['n']!r}")
        # the place's own honor, never a bigger one: the hero and the facts only (nearby places can have their own)
        mine = " ".join(re.findall(r'<section class="hero">.*?</section>|<section id="checked">.*?</section>', s, re.S))
        jbf = p["jbf"].lower()
        if not p["h"] & 2 and "winner" in mine.lower() and "winner" not in jbf:
            problems.append(f"{path}: calls {p['n']!r} a winner; its James Beard honor is {jb_label(p['h'], p['jbf'])!r}")
        if not p["h"] & 1 and "america's classic" in html.unescape(mine).lower() and "classic" not in jbf:
            problems.append(f"{path}: calls {p['n']!r} an America's Classic")
    # --- MICHELIN: the honors page says Idaho has none
    if HON_PATH in pages and "no MICHELIN Guide" not in pages[HON_PATH]:
        problems.append(f"{HON_PATH}: doesn't say Idaho has no MICHELIN Guide")
    # --- the published data: no Google, no ratings, no inspections, only http(s) websites
    for f in glob.glob(os.path.join(DOCS, "data", "*.json")) + [os.path.join(DOCS, "site.webmanifest")]:
        raw = open(f, encoding="utf-8").read()
        if "google" in raw.lower():
            problems.append(f"{rel(f)}: mentions Google")
    for k in ("rating", "reviews", "rv", "r21", "ir", "ipt", "idt", "in", "price"):
        if k in core["cols"]:
            problems.append(f"data: core.json has a {k!r} column (no ratings, reviews, prices or inspections ship)")
    for i, d in enumerate(detail):
        for k in ("in", "rating", "reviews"):
            if (d or {}).get(k) is not None:
                problems.append(f"data: detail.json gives {core['cols']['n'][i]!r} a {k!r} field")
        w = (d or {}).get("w")
        if w and not re.match(r"https?://", w):
            problems.append(f"data: website {w!r} for {core['cols']['n'][i]!r} isn't http(s)")
    if not DOMAIN.endswith("github.io") and not os.path.exists(CNAME):
        problems.append("a custom domain without docs/CNAME")
    return problems


# ---------------------------------------------------------------- the local server
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    """docs/ at /idaho-eats/ (the path GitHub Pages will use), on the first port in 8853-8859 nothing else is listening on."""
    root = DOCS
    if BASE:
        root = tempfile.mkdtemp()
        os.symlink(DOCS, os.path.join(root, BASE.strip("/")))
    for port in PORTS:
        with socket.socket() as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                continue        # someone's listening here: leave it alone
        try:
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Quiet, directory=root))
        except OSError:
            continue
        srv.handle_error = lambda *a: None     # a browser dropping a connection mid-file isn't a site problem
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{port}", srv
    sys.exit(f"no free port in {PORTS.start}-{PORTS.stop - 1}")


INIT = """
window.__csp = [];
document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(e.violatedDirective + ' ' + (e.blockedURI || 'inline') + ' @' + (e.sourceFile || '') + ':' + e.lineNumber));
window.__cls = 0;
try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
  .observe({ type: 'layout-shift', buffered: true }); } catch (e) {}
"""
TAP = """(scope) => {
  const out = [];
  const root = scope ? document.querySelector(scope) : document;
  const blockOf = (el) => { let n = el.parentElement; while (n && getComputedStyle(n).display.startsWith('inline')) n = n.parentElement; return n; };
  for (const el of root.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, summary')) {
    let t = el;
    if (el.matches('input[type=checkbox], input[type=radio]') && el.closest('label')) t = el.closest('label');
    if (t.closest('[hidden], [inert]') && !scope) continue;
    const cs = getComputedStyle(t);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const r = t.getBoundingClientRect();
    if (r.width === 0 || r.height === 0 || r.right + scrollX <= 0 || r.bottom + scrollY <= 0) continue;   // not rendered, or the off-screen skip link
    if (t.tagName === 'A' && cs.display === 'inline') {     // a link inside a sentence is exempt (WCAG 2.5.8)
      const b = blockOf(t), own = t.textContent.replace(/\\s+/g, ' ').trim(), all = (b ? b.textContent : '').replace(/\\s+/g, ' ').trim();
      if (all.length > own.length + 2) continue;
    }
    if (r.width < 43.5 || r.height < 43.5) out.push(`${t.tagName.toLowerCase()}${t.id ? '#' + t.id : ''}${t.className && typeof t.className === 'string' ? '.' + t.className.split(' ')[0] : ''} "${(t.textContent || t.getAttribute('aria-label') || '').trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
  }
  return out;
}"""
CONTRAST = """(scope) => {
  const parse = (c) => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(/[\\s,\\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const bgOf = (el) => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) { const c = parse(getComputedStyle(n).backgroundColor); if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; } }
    let base = parse(getComputedStyle(document.body).backgroundColor) || [255, 255, 255, 1];
    if (base[3] < 1) base = [255, 255, 255, 1];
    if (layers.length && layers[layers.length - 1][3] >= 1) base = layers.pop();
    for (const c of layers.reverse()) base = [0, 1, 2].map((i) => c[i] * c[3] + base[i] * (1 - c[3])).concat(1);
    return base;
  };
  const out = [];
  for (const root of document.querySelectorAll(scope)) {
    for (const el of [root, ...root.querySelectorAll('*')]) {
      if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
      if (el.closest('[hidden], .vh, option, svg') || el.disabled || el.closest(':disabled')) continue;
      const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
      if (!r.width || !r.height || cs.visibility === 'hidden') continue;
      const fg = parse(cs.color), bg = bgOf(el);
      if (!fg) continue;
      const a = lum(fg), b = lum(bg), ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      if (ratio < 4.5) out.push(`${el.tagName.toLowerCase()}.${(el.className || '').toString().split(' ')[0]} "${el.textContent.trim().slice(0, 24)}" ${ratio.toFixed(2)}:1`);
    }
  }
  return out;
}"""


def goto(page, url, problems, until="load"):
    """Navigate, once more with a longer wait if the machine is busy; None if the page never loaded."""
    err = None
    for timeout in (30000, 90000):
        try:
            return page.goto(url, wait_until=until, timeout=timeout)
        except Exception as ex:   # noqa: BLE001 (Playwright's timeout and network errors)
            err = ex
    problems.append(f"{urllib.parse.urlparse(url).path}: didn't load ({str(err).splitlines()[0][:80]})")
    return None


def fresh(page, url, problems):
    """A real page load, even when only the #hash differs from the current URL (which would just fire hashchange)."""
    page.goto("about:blank")
    return goto(page, url, problems, "networkidle")


def rows(page):
    return page.locator(".ex-row").count()


def wait_rows(page):
    page.wait_for_function("() => document.querySelectorAll('.ex-row, .ex-empty').length > 0", timeout=60000)


def count_of(page):
    m = re.match(r"([\d,]+) places?", page.locator("#ex-count").inner_text() or "")
    return int(m.group(1).replace(",", "")) if m else -1


def browser_checks(problems):
    from playwright.sync_api import sync_playwright
    base, srv = serve()
    local = urllib.parse.urlparse(base).netloc
    paths = [rel(f) for f in doc_files()]
    if os.environ.get("QA_PAGES"):
        paths = paths[:int(os.environ["QA_PAGES"])]
    widths = [int(w) for w in os.environ.get("QA_WIDTHS", "375,1280").split(",")]
    urls = [base + BASE + "/" + ("" if p == "index.html" else p.removesuffix("index.html")) for p in paths]
    core, detail, places = load_data()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        for width in widths:
            ctx = browser.new_context(viewport={"width": width, "height": 812 if width < 600 else 900})
            ctx.add_init_script(INIT)
            page = ctx.new_page()
            errors, foreign = [], []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda ex: errors.append(str(ex)))
            page.on("request", lambda r: foreign.append(r.url) if urllib.parse.urlparse(r.url).netloc not in (local, "") and not r.url.startswith(("data:", "about:", "blob:")) else None)
            for url in urls:
                errors.clear(); foreign.clear()
                if not goto(page, url, problems, "networkidle" if "/explore/" in url else "load"):
                    continue
                where = f"{urllib.parse.urlparse(url).path} @{width}"
                if "/explore/" in url:
                    try:
                        wait_rows(page)
                    except Exception:   # noqa: BLE001
                        problems.append(f"{where}: the web app listed nothing")
                over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                if over > 1:
                    problems.append(f"{where}: scrolls sideways by {over}px")
                if page.locator("h1").count() != 1:
                    problems.append(f"{where}: {page.locator('h1').count()} <h1>")
                problems += [f"{where}: CSP violation: {v}" for v in page.evaluate("window.__csp || []")]
                problems += [f"{where}: request to another host: {u}" for u in foreign]
                if width < 600:
                    problems += [f"{where}: tap target under 44px: {t}" for t in page.evaluate(TAP, None)]
                else:   # links are the same at both widths
                    refs = page.evaluate("""[...document.querySelectorAll('a[href],img[src],link[href],source[srcset]')]
                        .map(e => e.getAttribute('href') || e.getAttribute('src') || e.getAttribute('srcset'))""")
                    for ref in refs:
                        full = urllib.parse.urljoin(url, ref)
                        p = urllib.parse.urlparse(full)
                        if p.scheme in ("mailto", "tel", "data"):
                            continue
                        if p.netloc in (local, DOMAIN) and not file_for(p.path):
                            problems.append(f"{where}: broken link {ref}")
                        if p.fragment and p.netloc == local and p.path == urllib.parse.urlparse(url).path and "/explore/" not in p.path:
                            if not page.evaluate("(id) => !!document.getElementById(id)", urllib.parse.unquote(p.fragment)):
                                problems.append(f"{where}: link to missing #{p.fragment}")
                    imgs = page.evaluate("[...document.images].filter(i => i.complete && i.naturalWidth === 0).map(i => i.currentSrc || i.src)")
                    problems += [f"{where}: image didn't load {s}" for s in imgs]
                problems += [f"{where}: console error: {x}" for x in errors]
            ctx.close()
        if not os.environ.get("QA_NOAPP"):
            webapp_checks(browser, base, problems, widths, core, places)
        browser.close()
    srv.shutdown()
    return len(urls)


def slow_core(page):
    """Hold core.json back a little, so the page paints before the list arrives (the case where layout used to jump)."""
    page.route("**/data/core.json", lambda r: (time.sleep(0.6), r.continue_()))


def guide_counts(places):
    rest = [p for p in places if not p["v"]]
    out = {k: len(guide_members(places, bits)) for k, (_, bits) in GUIDES.items()}
    out["honors"] = sum(1 for p in rest if p["jb"])
    out["oldest"] = sum(1 for p in rest if p["f"] is not None)
    out["all"] = len(rest)
    return out


def webapp_checks(browser, base, problems, widths, core, places):
    """The web app's flows. A step that errors (a Playwright timeout when a control is missing) is reported as a problem and the
    rest of the checks still run."""
    for width in widths:
        try:
            webapp_flow(browser, base, problems, width, core, places)
        except Exception as ex:   # noqa: BLE001
            problems.append(f"explore @{width}: the web app flow stopped: {str(ex).splitlines()[0][:160]}")
    try:
        webapp_extras(browser, base, problems, places)
    except Exception as ex:   # noqa: BLE001
        problems.append(f"explore: the layout, retry or contrast checks stopped: {str(ex).splitlines()[0][:160]}")
    for name, check in (("guide search (All restaurants button)", webapp_widen), ("search placeholder", webapp_placeholder)):
        try:
            check(browser, base, problems, places)
        except Exception as ex:   # noqa: BLE001
            problems.append(f"explore: the {name} checks stopped: {str(ex).splitlines()[0][:160]}")


def webapp_flow(browser, base, problems, width, core, places):
    ex = base + BASE + "/explore/"
    want = guide_counts(places)
    fry = [p for p in guide_members(places, GUIDES["fingersteaks"][1]) if " fry sauce " in norm(" ".join([p["n"], p["dish"], p["a"]])) or " fry sauce" in norm(p["dish"])]
    place_pages = sorted(rel(f) for f in glob.glob(os.path.join(DOCS, "places", "*.html")))
    picks = [place_pages[0], place_pages[len(place_pages) // 2], place_pages[-1]] if place_pages else []
    w = f"explore @{width}"
    ctx = browser.new_context(viewport={"width": width, "height": 812 if width < 600 else 720},
                              geolocation={"latitude": 43.6150, "longitude": -116.2023}, permissions=["geolocation"])   # 8th and Main, Boise
    ctx.add_init_script(INIT)
    page = ctx.new_page()
    errors, requests = [], []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda x: errors.append(str(x)))
    page.on("request", lambda r: requests.append(r.url))
    slow_core(page)
    goto(page, base + BASE + "/", problems, "networkidle")      # a page before it, so Back has somewhere to leave to
    goto(page, ex, problems, "networkidle")
    wait_rows(page)
    page.wait_for_timeout(1200)
    cls = page.evaluate("window.__cls")
    if cls >= 0.05:
        problems.append(f"{w}: layout shift (CLS) {cls:.3f} on load")
    if any(u.endswith("/data/detail.json") for u in requests):
        problems.append(f"{w}: detail.json loaded before any place was opened")
    if width < 600:
        problems += [f"{w}: tap target under 44px: {t}" for t in page.evaluate(TAP, None)]
    # the search box's placeholder fits the box (a cut-off hint at 375 px hid "dish")
    fit = page.evaluate("""() => { const q = document.querySelector('#ex-q'), cs = getComputedStyle(q), c = document.createElement('canvas').getContext('2d');
        c.font = cs.font; return [c.measureText(q.placeholder).width, q.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)]; }""")
    if fit[0] > fit[1]:
        problems.append(f"{w}: the search placeholder is cut off ({fit[0]:.0f}px of text in a {fit[1]:.0f}px box)")
    # every control keeps the page's font (an invalid `font` shorthand is dropped, leaving the browser's 13.33px Arial), and on a phone the
    # search box and selects are 16px or more, or iOS Safari zooms the page when one gets focus
    for tag, fam, size in page.evaluate("""() => { const body = getComputedStyle(document.body).fontFamily;
        return [...document.querySelectorAll('#ex-app input[type=search], #ex-app select, #ex-app button')].map(e => { const cs = getComputedStyle(e);
          return [(e.id ? '#' + e.id : e.tagName.toLowerCase() + '.' + (e.className || '')), cs.fontFamily === body, parseFloat(cs.fontSize)]; }); }"""):
        if not fam:
            problems.append(f"{w}: {tag} doesn't use the page's font (an invalid font shorthand?)")
        if width < 600 and tag in ("#ex-q", "#ex-sort", "#ex-town", "#ex-cuisine") and size < 16:
            problems.append(f"{w}: {tag} is {size}px on a phone (under 16px, iOS zooms in on focus)")
    # each guide button lists exactly its places (the same rules as Guide.swift and make-site.py)
    buttons = page.evaluate("[...document.querySelectorAll('.ex-guides button')].map(b => b.dataset.g)")
    for g, n in want.items():
        if n == 0 and g in buttons:
            problems.append(f"{w}: an empty guide {g!r} has a button")
        if n > 0 and g not in buttons:
            problems.append(f"{w}: guide {g!r} ({n} places) has no button")
    for g in buttons:
        if g == "saved":
            continue
        page.locator(f'.ex-guides button[data-g="{g}"]').click()
        page.wait_for_timeout(150)
        if g in want and count_of(page) != want[g]:
            problems.append(f"{w}: guide {g!r} lists {count_of(page)} places, the data has {want[g]}")
    # a dish search inside a guide finds exactly the places that serve it
    page.locator('.ex-guides button[data-g="fingersteaks"]').click()
    search = page.locator("#ex-q")
    search.fill("fry sauce")
    page.wait_for_timeout(500)
    if count_of(page) != len(fry):
        problems.append(f"{w}: 'fry sauce' listed {count_of(page)} finger steak places, expected the {len(fry)} that serve it")
    search.fill("basque boise")
    page.wait_for_timeout(500)
    page.locator('.ex-guides button[data-g="all"]').click()
    page.wait_for_timeout(300)
    if not rows(page):
        problems.append(f"{w}: search 'basque boise' found nothing")
    else:
        page.locator(".ex-row").first.click()
        try:
            page.wait_for_function("() => document.querySelector('#ex-panel .ex-sec')", timeout=30000)
        except Exception:   # noqa: BLE001
            pass
        page.wait_for_timeout(500)
        panel = page.locator("#ex-panel")
        if not panel.is_visible() or not panel.locator("a", has_text="Directions").count():
            problems.append(f"{w}: opening a place showed no details")
        else:
            if not panel.locator("a", has_text="food inspections").count() and "no online inspection lookup" not in (panel.inner_text() or ""):
                problems.append(f"{w}: the place panel has no health district inspection lookup")
            if "MICHELIN" in panel.inner_text():
                problems.append(f"{w}: the place panel mentions MICHELIN")
            st = page.evaluate("""() => ({ role: document.querySelector('#ex-panel').getAttribute('role'), modal: document.querySelector('#ex-panel').getAttribute('aria-modal'),
                label: document.getElementById(document.querySelector('#ex-panel').getAttribute('aria-labelledby'))?.textContent || '',
                app: document.querySelector('#ex-app').inert, footer: document.querySelector('footer').inert, focus: document.activeElement?.id })""")
            # a modal dialog at every width: on a wide screen the side panel covers List, Map and Near me, so they must not stay focusable
            if st["role"] != "dialog" or st["modal"] != "true" or not st["label"] or not st["app"] or not st["footer"]:
                problems.append(f"{w}: the open place panel isn't a labelled modal dialog with the page behind it inert: {st}")
            if st["focus"] != "ex-close":
                problems.append(f"{w}: focus isn't on Close when a place opens: {st['focus']}")
            if not any(u.endswith("/data/detail.json") for u in requests):
                problems.append(f"{w}: opening a place didn't load detail.json")
            if width < 600:
                problems += [f"{w} (panel open): tap target under 44px: {t}" for t in page.evaluate(TAP, "#ex-panel")]
            page.locator("#ex-save").click()
            keys = page.evaluate("Object.keys(localStorage)")
            bad = [k for k in keys if not k.startswith(STORAGE_PREFIX)]
            if bad or not keys:
                problems.append(f"{w}: localStorage keys {keys} (want all to start {STORAGE_PREFIX!r})")
            page.locator("#ex-save").click()
            page.go_back()
            page.wait_for_timeout(600)
            if not page.url.startswith(ex) or panel.is_visible():
                problems.append(f"{w}: Back with a place open didn't just close it (now at {page.url}, panel visible: {panel.is_visible()})")
                fresh(page, ex + "#g=all&q=basque%20boise", problems)   # carry on from the web app, so the checks below still run
                wait_rows(page)
            elif page.evaluate("document.querySelector('#ex-app').inert"):
                problems.append(f"{w}: the page stayed inert after the sheet closed")
            else:   # Forward reopens the same place; Close then steps back over its entry, so the next Back leaves the page
                pname = panel.locator("#ex-pname").text_content() if panel.locator("#ex-pname").count() else ""
                page.go_forward()
                page.wait_for_timeout(600)
                if not panel.is_visible() or (panel.locator("#ex-pname").text_content() or "") != pname:
                    problems.append(f"{w}: Forward after Back didn't reopen the place")
                else:
                    page.locator("#ex-close").click()
                    page.wait_for_timeout(600)
                    here_url = page.url
                    if panel.is_visible() or search.input_value() != "basque boise":
                        problems.append(f"{w}: closing a place reopened by Forward lost the search ({search.input_value()!r})")
                    page.go_back()
                    page.wait_for_timeout(800)
                    if page.url == here_url:
                        problems.append(f"{w}: Back after closing a place reopened by Forward was a dead click (a duplicate history entry)")
                    fresh(page, ex + "#g=all&q=basque%20boise", problems)   # back to the search for the checks below
                    wait_rows(page)
            page.locator(".ex-row").first.click()
            page.wait_for_timeout(300)
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            st = page.evaluate("({ hidden: document.querySelector('#ex-panel').hidden, row: document.activeElement?.classList.contains('ex-row') })")
            if not st["hidden"] or not st["row"]:
                problems.append(f"{w}: Escape didn't close the place and return focus to its row: {st}")
            # a click outside the modal panel (on the dimmed page) closes it, at every width
            page.locator(".ex-row").first.click()
            page.wait_for_selector("#ex-panel:not([hidden])")
            page.mouse.click(8, 8)
            page.wait_for_timeout(400)
            if not page.evaluate("document.querySelector('#ex-panel').hidden"):
                problems.append(f"{w}: a click outside the open place panel didn't close it")
                page.keyboard.press("Escape")
    # a first visit opens on a guide, so a name typed there that's in another guide gets a button to All restaurants, not a dead end
    # (webapp_widen checks the button itself: its count, the click, the focus)
    dg = default_guide()
    if dg in GUIDES:
        inside = {p["n"] for p in guide_members(places, GUIDES[dg][1])}
        other = next((p["n"] for p in sorted(places, key=lambda p: p["n"]) if p["hc"] and not p["v"] and p["n"] not in inside and len(p["n"]) > 6), None)
        if other:
            c2 = browser.new_context(viewport={"width": width, "height": 812 if width < 600 else 720})
            p2 = c2.new_page()
            goto(p2, ex, problems, "networkidle")
            wait_rows(p2)
            p2.locator("#ex-q").fill(other)
            p2.wait_for_timeout(600)
            if not rows(p2) and not (p2.locator("#ex-widen").count() and p2.locator("#ex-widen").is_visible()):
                problems.append(f"{w}: on a first visit, searching {other!r} in the {dg} guide offers no button to All restaurants: "
                                f"{(p2.locator('#ex-list').text_content() or '').strip()[:90]!r}")
            c2.close()
    search.fill("🍕")
    page.wait_for_timeout(400)
    if rows(page):
        problems.append(f"{w}: an emoji search listed places")
    search.fill("")
    page.wait_for_timeout(300)
    # "Nearest" isn't claimed without a location
    fresh(page, ex + "#g=honors&sort=nearest", problems)
    wait_rows(page)
    if "Nearest" in page.locator("#ex-count").inner_text():
        problems.append(f"{w}: says 'Nearest' with no location")
    # Near me (geolocation under the CSP)
    page.locator("#ex-locate").click()
    page.wait_for_timeout(900)
    if "away" not in (page.locator(".ex-row").first.text_content() or ""):
        problems.append(f"{w}: Near me didn't sort by distance")
    if "outside Idaho" in (page.locator("#ex-locmsg").text_content() or ""):
        problems.append(f"{w}: Near me from downtown Boise says it's outside Idaho")
    # Near me from just over the line (Pullman, WA: inside Idaho's bounding box) says plainly that it's outside Idaho; Moscow doesn't
    for town, lat, lon, out in (("Pullman, WA", 46.7298, -117.1817, True), ("Moscow, ID", 46.7324, -116.9992, False), ("Seattle", 47.6062, -122.3321, True)):
        c2 = browser.new_context(viewport={"width": width, "height": 812 if width < 600 else 720}, geolocation={"latitude": lat, "longitude": lon},
                                 permissions=["geolocation"])
        p2 = c2.new_page()
        goto(p2, ex + "#g=basque", problems, "networkidle")
        wait_rows(p2)
        p2.locator("#ex-locate").click()
        p2.wait_for_function("() => /Sorted by|outside Idaho|Location is off/.test(document.querySelector('#ex-locmsg').textContent)", timeout=15000)
        said = "outside Idaho" in (p2.locator("#ex-locmsg").text_content() or "")
        if said != out:
            problems.append(f"{w}: Near me from {town} {'did not say' if out else 'said'} it's outside Idaho")
        c2.close()
    # Near me asks for a fresh fix on every tap (the visitor may have driven 100 miles since the last one) and stays tappable
    c2 = browser.new_context(viewport={"width": width, "height": 812 if width < 600 else 720}, geolocation={"latitude": 43.6150, "longitude": -116.2023},
                             permissions=["geolocation"])
    c2.add_init_script("""(() => { const g = navigator.geolocation; if (!g) return; const get = g.getCurrentPosition.bind(g); window.__geo = [];
        g.getCurrentPosition = (ok, bad, opt) => { window.__geo.push(opt || {}); return get(ok, bad, opt); }; })()""")
    p2 = c2.new_page()
    goto(p2, ex + "#g=huckleberry", problems, "networkidle")
    wait_rows(p2)
    p2.locator("#ex-locate").click()
    p2.wait_for_function("() => /away/.test(document.querySelector('.ex-row')?.textContent || '')", timeout=15000)
    first = p2.locator(".ex-row").first.text_content() or ""
    c2.set_geolocation({"latitude": 47.6777, "longitude": -116.7805})   # Coeur d'Alene, 300 miles north
    if not p2.locator("#ex-locate").is_enabled():
        problems.append(f"{w}: Near me can't be tapped again once it has a location")
    else:
        p2.locator("#ex-locate").click()
        p2.wait_for_timeout(1200)
        if (p2.locator(".ex-row").first.text_content() or "") == first:
            problems.append(f"{w}: a second Near me tap after moving 300 miles kept the old order ({first[:40]!r})")
    stale = [o.get("maximumAge") for o in p2.evaluate("window.__geo || []") if (o.get("maximumAge") or 0) > 60000]
    if stale:
        problems.append(f"{w}: Near me accepts a cached location up to {max(stale) // 1000}s old (want a fresh fix)")
    c2.close()
    # with location denied, nothing claims distance order: not the count line, not the sort menu
    c2 = browser.new_context(viewport={"width": width, "height": 812 if width < 600 else 720})
    p2 = c2.new_page()
    goto(p2, ex + "#g=basque&sort=nearest", problems, "networkidle")
    wait_rows(p2)
    p2.locator("#ex-locate").click()
    p2.wait_for_function("() => /Location is off|can't share/.test(document.querySelector('#ex-locmsg').textContent)", timeout=15000)
    p2.select_option("#ex-sort", "nearest")
    p2.wait_for_timeout(800)
    said = [p2.locator("#ex-count").inner_text(), p2.input_value("#ex-sort")]
    if "Nearest" in said[0] or said[1] == "nearest" or "away" in (p2.locator(".ex-row").first.text_content() or ""):
        problems.append(f"{w}: with location denied the list still claims distance order: {said}")
    c2.close()
    # junk under this site's keys (any page on the shared github.io origin can write them) doesn't stop the app, and Save repairs it
    for key, val in (("saved", '{"x":1}'), ("saved", "not json"), ("saved", '[null, 5, {}, "x"]'), ("saved", '"abc"'), ("guide", '{"x":1}'), ("guide", "not json")):
        c2 = browser.new_context(viewport={"width": width, "height": 812 if width < 600 else 720})
        p2 = c2.new_page()
        errs = []
        p2.on("pageerror", lambda x, errs=errs: errs.append(str(x)))
        goto(p2, base + BASE + "/", problems)
        p2.evaluate("([k, v]) => localStorage.setItem(k, v)", [STORAGE_PREFIX + key, val])
        goto(p2, ex + "#g=all", problems, "networkidle")
        try:
            wait_rows(p2)
            p2.locator(".ex-row").first.click()
            p2.wait_for_selector("#ex-save", timeout=15000)
            p2.locator("#ex-save").click()
            got = json.loads(p2.evaluate(f"localStorage.getItem('{STORAGE_PREFIX}saved')") or "null")
            if not isinstance(got, list) or not got or not all(isinstance(x, str) for x in got):
                problems.append(f"{w}: with {STORAGE_PREFIX}{key} = {val} Save wrote {got!r}")
        except Exception as x:   # noqa: BLE001
            problems.append(f"{w}: {STORAGE_PREFIX}{key} = {val} stopped the web app: {(errs or [str(x).splitlines()[0]])[0][:120]}")
        c2.close()
    # the map draws (canvas pixels), and stays within the page
    page.locator('.ex-view button[data-v="map"]').click()
    page.wait_for_timeout(1500)
    painted = page.evaluate("""() => { const c = document.querySelector('#ex-map'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        let n = 0; for (let i = 3; i < d.length; i += 4 * 7) if (d[i]) n++; return n; }""")
    if painted < 500:
        problems.append(f"{w}: the map didn't draw")
    page.locator('.ex-view button[data-v="list"]').click()
    # a saved place survives a reload
    page.locator(".ex-row").first.click()
    page.wait_for_selector("#ex-save")
    name = page.locator("#ex-pname").text_content()
    page.locator("#ex-save").click()
    page.keyboard.press("Escape")
    fresh(page, ex + "#g=saved", problems)
    wait_rows(page)
    if name not in (page.locator("#ex-list").text_content() or ""):
        problems.append(f"{w}: a saved place wasn't in Saved after a reload")
    # hostile hashes and a junk stored guide
    for h in ("#g=constructor", "#g=__proto__&sort=toString", "#g=toString&sort=__proto__&town=constructor&p=constructor"):
        errors.clear()
        fresh(page, ex + h, problems)
        page.wait_for_timeout(300)
        if errors or not re.match(r"[\d,]+ places? ·", page.locator("#ex-count").text_content() or ""):
            problems.append(f"{w}: {h} broke the web app: {errors[:2]}")
    page.evaluate(f"localStorage.setItem('{STORAGE_PREFIX}guide', JSON.stringify('__proto__'))")
    errors.clear()
    fresh(page, ex, problems)
    page.wait_for_timeout(300)
    if errors or not rows(page):
        problems.append(f"{w}: a junk stored guide broke the web app: {errors[:2]}")
    errors.clear()
    page.evaluate("location.hash = 'g=__proto__&p=constructor'")     # the hashchange path too
    page.wait_for_timeout(300)
    if errors:
        problems.append(f"{w}: a hostile hash change broke the web app: {errors[:2]}")
    # #p= links from place pages open the right place
    for f in picks:
        s = open(os.path.join(DOCS, f), encoding="utf-8").read()
        pid = re.search(r'/explore/#p=([0-9a-zA-Z]+)"', s).group(1)
        want_name = html.unescape(re.search(r"<h1>(.*?)</h1>", s).group(1))
        fresh(page, ex + f"#p={pid}", problems)
        page.wait_for_timeout(600)
        got = page.locator("#ex-pname").text_content() if page.locator("#ex-pname").count() else ""
        if got != want_name:
            problems.append(f"{w}: #p= from {f} opened {got!r}, want {want_name!r}")
    problems += [f"{w}: CSP violation: {v}" for v in page.evaluate("window.__csp || []")]
    problems += [f"{w}: console error: {x}" for x in errors]
    ctx.close()


def webapp_extras(browser, base, problems, places):
    ex = base + BASE + "/explore/"
    place_pages = sorted(rel(f) for f in glob.glob(os.path.join(DOCS, "places", "*.html")))
    picks = [place_pages[0], place_pages[len(place_pages) // 2], place_pages[-1]] if place_pages else []
    # CLS at a few more window sizes, where the footer or the list could jump into view
    for vw, vh in ((1280, 720), (1440, 900), (768, 1024)):
        ctx = browser.new_context(viewport={"width": vw, "height": vh})
        ctx.add_init_script(INIT)
        page = ctx.new_page()
        slow_core(page)
        goto(page, ex, problems, "networkidle")
        wait_rows(page)
        page.wait_for_timeout(1000)
        if page.evaluate("window.__cls") >= 0.05:
            problems.append(f"explore @{vw}x{vh}: CLS {page.evaluate('window.__cls'):.3f}")
        ctx.close()
    # a failed core.json: the error shows in #ex-loading, and retry works
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    page = ctx.new_page()
    page.route("**/data/core.json", lambda r: r.abort())
    goto(page, ex, problems, "networkidle")
    page.wait_for_timeout(500)
    msg = page.locator("#ex-loading").text_content() or ""
    if "couldn" not in msg or not page.locator("#ex-loading #ex-retry").count():
        problems.append(f"explore: a failed core.json didn't show an error with a retry ({msg!r})")
    else:
        page.unroute("**/data/core.json")
        page.locator("#ex-retry").click()
        try:
            page.wait_for_function("() => document.querySelectorAll('.ex-row').length > 0", timeout=60000)
        except Exception:   # noqa: BLE001
            problems.append("explore: retry after a failed core.json didn't load the list")
    ctx.close()
    # contrast of the web app's controls, list, panel and map, and of sample pages, in light and dark mode
    sample_place = "/" + picks[0] if picks else "/"
    for scheme in ("light", "dark"):
        ctx = browser.new_context(viewport={"width": 375, "height": 812}, color_scheme=scheme)
        page = ctx.new_page()
        for url, scope in (("/explore/#g=honors", "header.site, .ex-controls, #ex-list"), ("/explore/#g=oldest", ".ex-controls, #ex-list"),
                           ("/", "header.site, main, footer"), ("/" + INS_PATH, "main"), (sample_place, "main"),
                           ("/" + next((p for p, _ in GUIDES.values() if os.path.exists(os.path.join(DOCS, p))), "about.html"), "main")):
            goto(page, base + BASE + url, problems, "networkidle")
            if url.startswith("/explore"):
                wait_rows(page)
            for t in page.evaluate(CONTRAST, scope):
                problems.append(f"{url} ({scheme}): text contrast under 4.5:1: {t}")
            if url == "/explore/#g=honors":
                page.locator('.ex-view button[data-v="map"]').click()
                page.wait_for_timeout(300)
                for t in page.evaluate(CONTRAST, ".ex-view, #ex-maphint, .ex-zoom"):
                    problems.append(f"{url} map ({scheme}): text contrast under 4.5:1: {t}")
                page.locator('.ex-view button[data-v="list"]').click()
                page.locator(".ex-row").first.click()
                page.wait_for_function("() => document.querySelector('#ex-panel .ex-sec')", timeout=30000)
                page.locator("#ex-save").click()     # the pressed Save state
                page.wait_for_timeout(300)
                for t in page.evaluate(CONTRAST, "#ex-panel"):
                    problems.append(f"{url} panel ({scheme}): text contrast under 4.5:1: {t}")
        ctx.close()


def default_guide():
    """The guide a first visit opens on (make-site.py's DEFAULT_GUIDE, in the web app's data-default)."""
    m = re.search(r'data-default="([^"]*)"', open(os.path.join(DOCS, "explore", "index.html"), encoding="utf-8").read())
    return m.group(1) if m else "all"


# A famous Idaho place that isn't in the guide the web app opens on (Finger Steaks & Drive-Ins): Big Jud's, the Boise burger joint known
# for its pound burger. FEW_QUERY lists a few places in that guide and many more statewide (both counted in the browser, so the check
# can't pass by finding nothing).
FAMOUS_ELSEWHERE = ("big jud's", "Big Jud's", "Boise")
FEW_QUERY = "meridian"
FEW = 5     # explore.js offers All restaurants when a guide search lists fewer places than this
WIDEN = re.compile(r"See ([\d,]+) match(?:es)? in All restaurants")


def webapp_widen(browser, base, problems, places):
    """ME-V08 / WI-V-03: the web app opens on a guide and a search there looks only in that guide, so a first visit typing a famous
    restaurant from elsewhere found nothing. A guide search that lists none or only a few (under FEW) offers the same search and filters
    in All restaurants, with its count ("See N matches in All restaurants", never "search all", which OVERCLAIMS bans); one click (or
    Enter) switches there, lists those N places, the famous one among them, and moves focus to the first result."""
    ex = base + BASE + "/explore/"
    dg = default_guide()
    q, name, town = FAMOUS_ELSEWHERE
    if dg not in GUIDES:
        problems.append(f"explore: the guide search check expects the web app to open on a hand-checked guide, not {dg!r}")
        return
    inside = {p["id"] for p in guide_members(places, GUIDES[dg][1])}
    target = [p for p in places if p["n"] == name and p["c"] == town and not p["v"]]
    if not target or any(p["id"] in inside for p in target):
        problems.append(f"explore: the guide search check needs {name} ({town}) in the data and outside the {dg} guide; pick another famous place")
        return
    listed = "[...document.querySelectorAll('.ex-row')].map(r => (r.querySelector('b')?.textContent || '') + ' | ' + (r.querySelector('.ex-town')?.textContent || ''))"
    state = """() => ({ g: document.querySelector('.ex-guides button[aria-pressed=true]')?.dataset.g, q: document.querySelector('#ex-q').value,
        town: document.querySelector('#ex-town').value, hash: location.hash,
        focus: !!document.activeElement && document.activeElement === document.querySelector('.ex-row') })"""
    for vw, vh, scheme, how in ((375, 812, "light", "click"), (1280, 800, "dark", "Enter")):
        w = f"explore @{vw} {scheme} (guide search)"
        ctx = browser.new_context(viewport={"width": vw, "height": vh}, color_scheme=scheme)
        ctx.add_init_script(INIT)
        page = ctx.new_page()
        errors = []
        page.on("console", lambda m, errors=errors: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda x, errors=errors: errors.append(str(x)))
        goto(page, ex, problems, "networkidle")      # no hash, nothing stored: a first visit, on the opening guide
        wait_rows(page)
        if page.evaluate("document.querySelector('.ex-guides button[aria-pressed=true]')?.dataset.g") != dg:
            problems.append(f"{w}: a first visit didn't open on the {dg} guide")
        page.locator("#ex-q").fill(q)
        page.wait_for_timeout(500)
        btn = page.locator("#ex-widen")
        if rows(page) or not btn.count() or not btn.is_visible():
            problems.append(f"{w}: “{q}” in the {dg} guide listed {rows(page)} and offered no All restaurants button: "
                            f"{(page.locator('#ex-list').text_content() or '').strip()[:100]!r}")
        else:
            m = WIDEN.fullmatch((btn.text_content() or "").strip())
            if not m:
                problems.append(f"{w}: the All restaurants button says {btn.text_content()!r}")
            if vw < 600:
                problems += [f"{w}: tap target under 44px: {t}" for t in page.evaluate(TAP, "#ex-list")]
            problems += [f"{w}: text contrast under 4.5:1: {t}" for t in page.evaluate(CONTRAST, "#ex-list")]
            over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if over > 1:
                problems.append(f"{w}: scrolls sideways by {over}px with the All restaurants button showing")
            if how == "click":
                btn.click()
            else:   # keyboard only: Tab reaches it like any button, Enter presses it
                btn.focus()
                page.keyboard.press("Enter")
            page.wait_for_timeout(400)
            st = page.evaluate(state)
            if st["g"] != "all" or st["q"] != q or "g=all" not in st["hash"]:
                problems.append(f"{w}: the button didn't switch to All restaurants with the same search: {st}")
            if m and count_of(page) != int(m.group(1).replace(",", "")):
                problems.append(f"{w}: the button promised {m.group(1)} matches, All restaurants lists {count_of(page)}")
            found = page.evaluate(listed)
            if not any(r.startswith(f"{name} | {town}") for r in found):
                problems.append(f"{w}: one {how} didn't find {name} ({town}): {found[:3]}")
            if not st["focus"]:
                problems.append(f"{w}: focus didn't move to the first result after the {how}")
            if page.locator("#ex-widen").count():
                problems.append(f"{w}: All restaurants still offers the button")
        # the same filters go along: with a town picked, the count and the list are that town's
        fresh(page, ex + f"#g={dg}&town={urllib.parse.quote(town)}", problems)
        wait_rows(page)
        page.locator("#ex-q").fill(q)
        page.wait_for_timeout(500)
        btn = page.locator("#ex-widen")
        m = WIDEN.fullmatch((btn.text_content() or "").strip()) if btn.count() and btn.is_visible() else None
        if not m:
            problems.append(f"{w}: “{q}” in the {dg} guide with the town {town} offered no All restaurants button")
        else:
            btn.click()
            page.wait_for_timeout(400)
            st, found = page.evaluate(state), page.evaluate(listed)
            if st["g"] != "all" or st["town"] != town or "town=" not in st["hash"]:
                problems.append(f"{w}: the button dropped the town filter: {st}")
            if count_of(page) != int(m.group(1).replace(",", "")) or not found or not all(f" | {town}" in r for r in found):
                problems.append(f"{w}: with the town {town} the button said {m.group(0)!r}, All restaurants lists {count_of(page)}: {found[:3]}")
        # a few in the guide and more statewide: the button follows the short list
        fresh(page, ex + f"#g={dg}", problems)
        wait_rows(page)
        page.locator("#ex-q").fill(FEW_QUERY)
        page.wait_for_timeout(500)
        n_guide, btn = count_of(page), page.locator("#ex-widen")
        offered = (btn.text_content() or "").strip() if btn.count() and btn.is_visible() else None
        after_rows = page.evaluate("!!document.querySelector('#ex-list li:last-child #ex-widen') && document.querySelectorAll('.ex-row').length > 0")
        page.locator('.ex-guides button[data-g="all"]').click()
        page.wait_for_timeout(300)
        n_all = count_of(page)
        if not 0 < n_guide < FEW or n_all <= n_guide:
            problems.append(f"{w}: pick another few-matches query (“{FEW_QUERY}”: {n_guide} in the {dg} guide, {n_all} in All restaurants)")
        elif offered != f"See {n_all:,} match{'' if n_all == 1 else 'es'} in All restaurants" or not after_rows:
            problems.append(f"{w}: “{FEW_QUERY}” found {n_guide} in the {dg} guide and {n_all} in All restaurants, but the guide offered {offered!r} "
                            f"(after the rows: {after_rows})")
        # nothing anywhere: no button, the plain message
        page.locator(f'.ex-guides button[data-g="{dg}"]').click()
        page.locator("#ex-q").fill("qqzxv")
        page.wait_for_timeout(500)
        if page.locator("#ex-widen").count() or "No places match" not in (page.locator("#ex-list").text_content() or ""):
            problems.append(f"{w}: a search nothing matches offered a button or lost its message: {(page.locator('#ex-list').text_content() or '')[:80]!r}")
        problems += [f"{w}: CSP violation: {v}" for v in page.evaluate("window.__csp || []")]
        problems += [f"{w}: console error: {x[:160]}" for x in errors]
        ctx.close()


# phone widths: iPhone SE (1st gen) 320, common Androids 360 and 412, iPhone mini 375, iPhone 390/393, the iPhone 17 Pro 402, Plus and
# Pro Max 414-440
PHONE_WIDTHS = (320, 360, 375, 390, 393, 402, 412, 414, 430, 440)
PLACEHOLDER = """() => {
  // the placeholder's own width: the same text as the value of a plain text field with the search box's computed font, padding, border
  // and width (a search field holding text adds a clear button that the placeholder never has), so scrollWidth > clientWidth means cut off
  const i = document.querySelector('#ex-q'), cs = getComputedStyle(i), c = document.createElement('input');
  c.type = 'text';
  for (const k of ['font', 'letterSpacing', 'wordSpacing', 'textIndent', 'boxSizing', 'width', 'paddingLeft', 'paddingRight', 'borderLeftWidth', 'borderRightWidth', 'borderStyle'])
    c.style[k] = cs[k];
  c.style.position = 'absolute'; c.style.visibility = 'hidden';
  i.parentElement.appendChild(c);
  c.value = i.placeholder;
  const cv = document.createElement('canvas').getContext('2d');
  cv.font = cs.font;
  const out = { ph: i.placeholder, sw: c.scrollWidth, cw: c.clientWidth, same: Math.abs(c.offsetWidth - i.offsetWidth) <= 1,
    text: Math.ceil(cv.measureText(i.placeholder).width), box: i.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight),
    px: parseFloat(getComputedStyle(i, '::placeholder').fontSize), inputPx: parseFloat(cs.fontSize) };
  c.remove();
  return out;
}"""


def webapp_placeholder(browser, base, problems, places=None):
    """The search box's placeholder fits at every common phone width, 320-440 px (California's read "…zip or d" at 375 px; here it was
    cut at 320 px, and had 3 px to spare at 360): scrollWidth <= clientWidth with the placeholder as the box's text, and 8 px to spare
    for other browsers' font metrics; its text is 16px or more (under that, iOS Safari zooms in on focus); the page doesn't scroll
    sideways, and the search row's controls stay 44 px tap targets."""
    for vw in PHONE_WIDTHS:
        w = f"explore @{vw} (placeholder)"
        ctx = browser.new_context(viewport={"width": vw, "height": 812})
        page = ctx.new_page()
        goto(page, base + BASE + "/explore/", problems, "networkidle")
        wait_rows(page)
        r = page.evaluate(PLACEHOLDER)
        if not r["ph"]:
            problems.append(f"{w}: the search box has no placeholder")
        if not r["same"]:
            problems.append(f"{w}: the placeholder measure didn't copy the search box's width (fix PLACEHOLDER in qa-site.py)")
        if r["sw"] > r["cw"] or r["box"] - r["text"] < 8:
            problems.append(f"{w}: the search placeholder {r['ph']!r} is cut off or nearly: {r['text']}px of text in a {r['box']:.0f}px box "
                            f"(scrollWidth {r['sw']} vs clientWidth {r['cw']})")
        if min(r["px"], r["inputPx"]) < 16:
            problems.append(f"{w}: the search box's text is {min(r['px'], r['inputPx'])}px (16px or more, or iOS zooms in)")
        over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        if over > 1:
            problems.append(f"{w}: scrolls sideways by {over}px")
        problems += [f"{w}: tap target under 44px: {t}" for t in page.evaluate(TAP, ".ex-row1")]
        ctx.close()


def main():
    problems, n = static_checks()
    n_static = len(problems)
    if "--static" in sys.argv:
        print(f"{n} pages, static checks")
    else:
        m = browser_checks(problems)
        print(f"static: {n} HTML files, {n_static} problems | browser: {m} pages × {os.environ.get('QA_WIDTHS', '375,1280')} px"
              + ("" if os.environ.get("QA_NOAPP") else " + the web app"))
    for p in problems:
        print("  ✗", p)
    print("OK" if not problems else f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
