"""Writes the public website in docs/ from the same data file the app ships (data/app/places.json).

Pages: the landing page; one statewide page per hand-checked Idaho guide that has at least MIN_LIST places (Basque, finger steaks &
drive-ins, spud plates, huckleberry, Idaho trout, taquerías, historic saloons), the James Beard honors page and the oldest places
page (same minimum); "How to look up an Idaho restaurant inspection" (the seven public health districts and their lookups); one
page per big town plus a cities hub; one page per public health district (the regions); one page per hand-checked or honored place;
about (methodology, sources, licenses in /licenses/), privacy, terms, the web app (/explore/), 404, plus sitemap.xml, robots.txt and
site.webmanifest. Adapted from co-eats/scripts/make-site.py, with wi-eats' about, place, region and license pages.

Rules the copy keeps (scripts/qa-site.py checks them):
- Every number is counted from the data here, never typed in, and no sentence claims "every" or "all N" restaurants: the lists are
  what we checked, not the whole state. The research is still coming in, so a guide with fewer than MIN_LIST places gets no page
  and no links (the web app still lists it, as the app's Home does); a guide page that drops below the minimum is deleted.
- "Hand-checked" only for places with hc (each checked against a 2025-26 source); "checked open" never (a source's date isn't a
  promise that a place is open today).
- No inspection results anywhere: Idaho's public health districts publish none in bulk and issue no grade, placard or score. The
  inspections page and each place link the district's own lookup; QA never fetches those third-party pages.
- James Beard: a semifinalist or nominee is never called a winner, and JBF's finalist stage is "nominee", as the Foundation says.
  Idaho has no MICHELIN Guide: said once, on the honors page, and nowhere else.
- No ratings, reviews or Google data anywhere, no analytics, no third-party scripts, fonts or images.
- Every page carries a hash-pinned Content-Security-Policy; inline scripts and styles are hashed after the page is final, and the
  build fails on an inline style= or on…= attribute.

Usage (from id-eats/): .venv/bin/python scripts/make-site.py
Re-run it after every data rebuild, then check the pages with scripts/qa-site.py. Never hand-edit docs/*.html.
"""
import base64
import hashlib
import html
import json
import math
import os
import re
import shutil
import struct
import unicodedata
from collections import Counter, defaultdict
from urllib.parse import quote

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = f"{ROOT}/docs"
# Where the site lives. Until Nick's Cloudflare record (CNAME idaho -> nickstrom5.github.io, DNS only) resolves, GitHub Pages serves
# the project address. When `dig idaho.eatsranked.com` shows the CNAME, run with ID_DOMAIN=idaho.eatsranked.com and push: this
# writes docs/CNAME, and GitHub then forwards the old github.io links (the ones inside shipped app builds, IdahoEats/App/Links.swift).
CUSTOM_DOMAIN = os.environ.get("ID_DOMAIN", "").strip()
REPO = "idaho-eats"
DOMAIN = f"https://{CUSTOM_DOMAIN}" if CUSTOM_DOMAIN else f"https://nickstrom5.github.io/{REPO}"
BASE = "" if CUSTOM_DOMAIN else f"/{REPO}"     # path prefix for root-relative links
BRAND = "Idaho Eats"
APP_NAME = "Idaho Eats: Restaurants"
TAGLINE = "Finger steaks, Basque & spud guide"
EMAIL = "nick@eatsranked.com"   # the public site's contact (Nick, 2026-10-12: Cloudflare Email Routing). The app's Links.swift follows in its next build
AUTHOR = "Nicholas Soderstrom"     # the app's maker; name only in public markup, never a personal email or phone
PUBLISHED = "2026-10-08"        # the site's first publication (Article datePublished)
SITE_REV = "2026-10-12"         # the last change to this generator's own copy or code: bump it when you change the words
POLICY_UPDATED = "2026-10-12"   # privacy policy and terms: bump only when their text changes
PRIVACY_UPDATED = "2026-10-26"   # the privacy policy alone: the app's data updates (OTA-DATA.md)
CHECKED = "October 2026"        # when the hand checks behind hc=1 were done, each against a 2025 or 2026 source
MIN_LIST = 4                    # a statewide list page needs at least this many places (the research is still coming in)
OG_COUNT = 4000                 # docs/og.png says "4,000+ Idaho restaurants" (scripts/make-brand.swift): re-run it if the count drops

# The App Store listing. None until the app is live. When it is: set APP_STORE_URL (https://apps.apple.com/app/id...), APP_ID, and
# put Apple's official "Download on the App Store" badge artwork at docs/img/app-store-badge.svg first (from Apple's marketing
# resources; never redraw it). Every page then links the badge, gets the Smart App Banner meta tag, and the MobileApplication
# JSON-LD gets offers, installUrl and sameAs. The build fails if the badge file is missing.
APP_STORE_URL = None
APP_ID = ""
APP_STORE_BADGE = "/img/app-store-badge.svg"
if APP_STORE_URL:
    assert APP_ID and os.path.exists(DOCS + APP_STORE_BADGE), f"set APP_ID and add Apple's badge at docs{APP_STORE_BADGE} before setting APP_STORE_URL"

D = json.load(open(f"{ROOT}/data/app/places.json"))
TODAY = max(str(D.get("generated") or SITE_REV)[:10], SITE_REV)   # sitemap lastmod and dateModified move with the data or the copy
LIQUOR_DATE = D.get("liquor_updated") or ""
ABC = D.get("abc_licenses") or 0
OVERTURE = D.get("overture_release") or ""
CENSUS = os.path.exists(f"{ROOT}/data/id/geocode_census.json")   # the pipeline placed some addresses with the Census geocoder
CITIES, CUISINES, COUNTIES = D["cities"], D["cuisines"], D["counties"]
TAGS = ["basque", "fingersteak", "drivein", "spud", "huckleberry", "trout", "taqueria", "historic", "oldest", "resort"]
assert D["tags"] == TAGS, f"the data's tag order changed ({D['tags']}): update TAGS here and the bits in scripts/explore.js"
BIT = {t: 1 << i for i, t in enumerate(TAGS)}
GUIDE_BITS = sum(BIT[t] for t in TAGS if t != "resort")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
NUM_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def hdate(iso):
    """2026-09-24 -> September 24, 2026"""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(iso or ""))
    return f"{MONTHS[int(m[2]) - 1]} {int(m[3])}, {m[1]}" if m else str(iso or "")


def plural(n, one, many=None):
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def words_num(n):
    return NUM_WORDS[n] if 0 <= n < len(NUM_WORDS) else f"{n:,}"


def safe_url(u):
    """Only http(s) links leave the site; a bare host ("example.com/menu") gets https://. Anything else is dropped."""
    u = str(u or "").strip()
    if re.fullmatch(r"https?://[^\s\"'<>\\]+", u, re.I):
        return u
    if re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,}(?:[/?#][^\s\"'<>\\]*)?", u, re.I):
        return "https://" + u
    return ""


# Restaurant websites that must never be linked (hacked with hidden casino links, expired, another business's page or a directory listing):
# pipeline/website_blocklist.json, [{"domain", "match": "domain" (it and every subdomain) | "url" (that page only), "place", "reason",
# "severity", "evidence", "found"}]. The link is dropped everywhere this script publishes it, static pages and the web app's data; the
# place stays, shown like any place without a website. qa-site.py fails if a listed domain or URL is anywhere in docs/.
BLOCKLIST = json.load(open(f"{ROOT}/pipeline/website_blocklist.json", encoding="utf-8"))
_bare = lambda u: re.sub(r"^https?://(www\.)?", "", str(u).strip(), flags=re.I).rstrip("/").lower()   # noqa: E731


def blocked_site(u):
    host = re.sub(r"^https?://", "", u, flags=re.I).split("/")[0].split("?")[0].split("#")[0].split(":")[0].lower().rstrip(".")
    for b in BLOCKLIST:
        if b.get("match", "domain") == "url":
            if _bare(u) == _bare(b.get("url") or b["domain"]):
                return True
        else:
            d = b["domain"].lower().strip().removeprefix("www.")
            if host == d or host.endswith("." + d):
                return True
    return False


def site_url(u):
    """A place's own website for the public site: safe_url, minus anything on the blocklist."""
    u = safe_url(u)
    return "" if u and blocked_site(u) else u


def safe_tel(ph):
    """A +1 number for tel: links and JSON-LD, or "" (digits only; anything that isn't a 10-digit US number is dropped)."""
    d = re.sub(r"\D", "", str(ph or ""))
    if len(d) == 11 and d[0] == "1":
        d = d[1:]
    return "+1" + d if len(d) == 10 else ""


def phone_text(tel):
    d = tel[2:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}"


class P:
    """One place, with the same meaning the app gives each field (IdahoEats/Models/Place.swift)."""

    def __init__(self, r):
        self.r = r
        self.id = str(r["id"])
        self.name = str(r["n"])
        self.city = CITIES[r["c"]] if r.get("c") is not None else ""
        self.county_full = COUNTIES[r["co"]] if r.get("co") is not None else ""
        self.county = self.county_full.replace(" County", "") or None
        self.cuisine = CUISINES[r["cu"]] if r.get("cu") is not None else ""
        self.addr = r.get("a") or ""
        self.zip = str(r.get("z") or "")
        self.lat, self.lon = r.get("la"), r.get("lo")
        self.tags = r.get("g") or 0
        self.chain = (r.get("ch") or 0) >= 5
        self.venue = r.get("v") == 1
        self.ip = r.get("ip")
        self.founded = r.get("f") if isinstance(r.get("f"), int) else None
        self.fn = r.get("fn") or ""
        self.dish_list = [x.strip() for x in str(r.get("dish") or "").split(";") if x.strip()]
        self.dishes = ", ".join(self.dish_list)
        self.season = r.get("seas") or ""
        self.note = r.get("note") or ""
        self.site = site_url(r.get("w"))
        self.tel = safe_tel(r.get("ph"))
        self.jbf = r.get("jbf") or ""
        self.h = r.get("h") or 0
        self.hc = r.get("hc") == 1   # hand-checked against a 2025-26 source; the only places the Idaho guides list
        self.slug = None             # set for places with their own page

    def featured_key(self):
        # the app's "Featured first": honored places, then documented founding year, then name
        return (-(self.ip if self.ip is not None else -1), self.founded or 9999, self.name.lower())

    def jb_label(self):
        return ("America's Classic" if self.h & 1 else "James Beard winner" if self.h & 2 else "James Beard nominee" if self.h & 4
                else "James Beard semifinalist" if self.h & 8 else "James Beard (restaurateur)" if self.jbf else None)

    def jb_rank(self):
        return 4 if self.h & 1 else 3 if self.h & 2 else 2 if self.h & 4 else 1 if self.h & 8 else 0


PLACES = [P(r) for r in D["places"]]
REST = [p for p in PLACES if not p.venue]
N_REST = len(REST)
N_TOWNS = len({p.city for p in REST if p.city})
N_COUNTIES = len({p.county for p in REST if p.county})
if N_REST < OG_COUNT:
    print(f"WARNING: docs/og.png says {OG_COUNT:,}+ restaurants but the data has {N_REST:,}: re-run swift scripts/make-brand.swift with a new count")

# ---------------------------------------------------------------- the guides (IdahoEats/Models/Guide.swift)
# key (the web app's #g=), the tags it takes (any of), its page, its words. A guide lists only hand-checked places.
GUIDES = [
    dict(key="basque", tags=("basque",), path="idaho-basque-restaurants.html", app="Basque", sec="basque", chip="Basque",
         name="Idaho Basque restaurants", short="Basque", nav="Basque", noun="Basque spot", nouns="Basque spots",
         sub="Boise's Basque Block and Basque kitchens around the state, hand-checked"),
    dict(key="fingersteaks", tags=("fingersteak", "drivein"), path="idaho-finger-steaks-drive-ins.html", app="Finger Steaks & Drive-Ins",
         sec="finger-steaks", chip="Finger steaks", name="Idaho finger steaks & drive-ins", short="Finger Steaks", nav="Finger steaks",
         noun="finger steak or drive-in spot", nouns="finger steak and drive-in spots", sub="Finger steaks, fry sauce and drive-in burgers, hand-checked"),
    dict(key="spuds", tags=("spud",), path="idaho-spud-plates.html", app="Spud Plates", sec="spuds", chip="Spud plate",
         name="Idaho spud plates", short="Spuds", nav="Spuds", noun="spud plate spot", nouns="spud plate spots",
         sub="Potato plates named on the menu, hand-checked"),
    dict(key="huckleberry", tags=("huckleberry",), path="idaho-huckleberry.html", app="Huckleberry", sec="huckleberry", chip="Huckleberry",
         name="Idaho huckleberry: where to eat it", short="Huckleberry", nav="Huckleberry", noun="huckleberry spot", nouns="huckleberry spots",
         sub="Huckleberry shakes, pies and pancakes, hand-checked"),
    dict(key="trout", tags=("trout",), path="idaho-trout-restaurants.html", app="Idaho Trout", sec="trout", chip="Trout",
         name="Idaho trout restaurants", short="Trout", nav="Trout", noun="place for Idaho trout", nouns="places for Idaho trout",
         sub="Idaho rainbow trout on the menu, hand-checked"),
    dict(key="taquerias", tags=("taqueria",), path="idaho-taquerias.html", app="Taquerías", sec="taquerias", chip="Taquería",
         name="Idaho taquerías", short="Taquerías", nav="Tacos", noun="taquería", nouns="taquerías",
         sub="Taquerías with a fixed address, hand-checked"),
    dict(key="historic", tags=("historic",), path="idaho-historic-saloons.html", app="Historic Saloons", sec="historic", chip="Historic saloon",
         name="Idaho historic saloons & supper clubs", short="Historic Saloons", nav="Saloons", noun="historic saloon or supper club",
         nouns="historic saloons and supper clubs", sub="Old saloons and supper clubs, hand-checked"),
]
GUIDE = {g["key"]: g for g in GUIDES}
for g in GUIDES:
    g["bits"] = sum(BIT[t] for t in g["tags"])
    g["places"] = sorted([p for p in REST if p.hc and p.tags & g["bits"]], key=P.featured_key)
    g["page"] = len(g["places"]) >= MIN_LIST
HON_L = sorted([p for p in REST if p.jbf], key=lambda p: (-p.jb_rank(), p.name.lower()))   # the app's honors order
OLD_L = sorted([p for p in REST if p.founded], key=lambda p: (p.founded, p.name.lower()))
OLD_ALL_HC = bool(OLD_L) and all(p.hc for p in OLD_L)
HON_PATH, OLD_PATH, INS_PATH = "idaho-james-beard-restaurants.html", "idaho-oldest-restaurants.html", "idaho-restaurant-inspections.html"
HON_PAGE, OLD_PAGE = len(HON_L) >= MIN_LIST, len(OLD_L) >= MIN_LIST
PAGED = [g for g in GUIDES if g["page"]]
SKIPPED = [g for g in GUIDES if not g["page"]]
HC_L = sorted([p for p in REST if p.hc], key=lambda p: (p.city, p.name.lower(), p.id))
PICKS = [p for p in HC_L if p.tags & GUIDE_BITS]   # on at least one Idaho guide


def guides_of(p):
    return [g for g in GUIDES if p.hc and p.tags & g["bits"]]


# ---------------------------------------------------------------- the seven public health districts (= the regions)
# Each licenses and inspects restaurants in its counties; none publishes results in bulk or issues a grade, placard or score.
# Every lookup was fetched on 2026-10-08 and renders (IdahoEats/Models/HealthDistrict.swift has the same table). QA never fetches them.
DISTRICTS = [
    dict(slug="north-idaho", name="North Idaho", district="Panhandle Health District", counties="Benewah Bonner Boundary Kootenai Shoshone",
         lookup="https://panhandlehealthdistrict.org/licensing-and-permitting/food-establishments/", site=None),
    dict(slug="north-central-idaho", name="North Central Idaho", district="Public Health – Idaho North Central District",
         counties="Clearwater Idaho Latah Lewis Nez_Perce", lookup="https://id.healthinspections.us/idaho/food/", site=None),
    dict(slug="southwest-idaho", name="Southwest Idaho", district="Southwest District Health", counties="Adams Canyon Gem Owyhee Payette Washington",
         lookup=None, site="https://swdh.id.gov/"),
    dict(slug="boise-mccall-mountain-home", name="Boise, McCall and Mountain Home", district="Central District Health", counties="Ada Boise Elmore Valley",
         lookup="https://cdh.idaho.gov/licenses-permits-inspections/food-establishments/", site=None),
    dict(slug="magic-valley-wood-river", name="Magic Valley and Wood River", district="South Central Public Health District",
         counties="Blaine Camas Cassia Gooding Jerome Lincoln Minidoka Twin_Falls", lookup="https://phd5.idaho.gov/inspections/", site=None),
    dict(slug="southeast-idaho", name="Southeast Idaho", district="Southeastern Idaho Public Health",
         counties="Bannock Bear_Lake Bingham Butte Caribou Franklin Oneida Power",
         lookup="https://inspectionsonline.us/foodsafety/idbannockpocatello/search.htm", site=None),
    dict(slug="eastern-idaho", name="Eastern Idaho", district="Eastern Idaho Public Health", counties="Bonneville Clark Custer Fremont Jefferson Lemhi Madison Teton",
         lookup="https://inspectionsonline.us/foodsafety/idbonnevilleidahofalls/search.htm", site=None),
]
for d in DISTRICTS:
    d["county_list"] = [c.replace("_", " ") for c in d["counties"].split()]
DISTRICT_OF = {c: d for d in DISTRICTS for c in d["county_list"]}
assert sorted(c + " County" for c in DISTRICT_OF) == sorted(COUNTIES), "every Idaho county belongs to exactly one district"
_hd = f"{ROOT}/IdahoEats/Models/HealthDistrict.swift"
if os.path.exists(_hd):   # the app and the site send people to the same lookups
    app_d = {name: (url if url != "nil" else None, sorted(re.findall(r'"([^"]+)"', cs)))
             for name, url, cs in re.findall(r'\("([^"]+)",\s*(nil|"[^"]*")\s*,\s*\[([^\]]*)\]\)', open(_hd).read())}
    app_d = {k: (u.strip('"') if u else None, cs) for k, (u, cs) in app_d.items()}
    assert app_d == {d["district"]: (d["lookup"], sorted(d["county_list"])) for d in DISTRICTS}, f"HealthDistrict.swift disagrees: {app_d}"
for p in PLACES:
    p.district = DISTRICT_OF.get(p.county) if p.county else None
    p.region = p.district["name"] if p.district else None
N_DISTRICT = Counter(p.district["slug"] for p in REST if p.district)


def miles(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


# ---------------------------------------------------------------- html helpers
e = html.escape


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("'", "").replace("’", "")).strip("-")


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def join_words(xs, conj="and"):
    xs = [x for x in xs if x]
    if len(xs) <= 1:
        return "".join(xs)
    return ", ".join(xs[:-1]) + f" {conj} " + xs[-1]


def fit(cands, lo, hi, what=""):
    seen = []
    for o in cands:
        if lo <= len(o) <= hi:
            return o
        seen.append(o)
    raise ValueError(f"nothing fits {lo}-{hi} for {what}: {[(len(o), o) for o in seen[:14]]}")


def cap1(s):
    return s[:1].upper() + s[1:]


# ---------------------------------------------------------------- the brand mark: the app icon in miniature (scripts/make-brand.swift)
def _icon_geometry():
    """make-brand.swift's potatoFood geometry (Eats Ranked icon style, 2026-10-09) in a 64-unit box. The Swift code already
    measures y from the top, so nothing flips."""
    u = 64
    px1 = 1 / 1024
    cx, cy, rx, ry = 0.5, 0.519, 0.36, 0.21
    skin_top = cy - ry
    shade = cy + ry - 2 * ry * 0.28                      # underside edge: the lower 28% of the potato
    shade_hw = rx * math.sqrt(1 - ((shade - cy) / ry) ** 2)
    eye_w, eye_h = 50 * px1, 34 * px1
    eyes = ((0.25, 0.492), (0.75, 0.482), (0.58, shade - 30 * px1 - eye_h / 2))
    lens_half, lens_top = 0.24, skin_top + 0.035
    lens_bottom = lens_top + 0.145
    hw = lens_half + 60 * px1
    tip = cy - ry * math.sqrt(1 - (hw / rx) ** 2)
    x0, x1 = cx - lens_half, cx + lens_half
    k_top, k_bot = tip + (lens_top - tip) / 0.75, tip + (lens_bottom - tip) / 0.75
    pat_w, pat_top, pat_bottom = 0.18, skin_top - 10 * px1, lens_top + 60 * px1

    def f(v):
        return f"{v * u:.2f}".rstrip("0").rstrip(".")

    eye_svg = "".join(f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(eye_w / 2)}" ry="{f(eye_h / 2)}" fill="#8A5A30"/>' for x, y in eyes)
    return (f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}" fill="#A8713E"/>'
            f'<path d="M{f(cx - shade_hw)} {f(shade)} A{f(rx)} {f(ry)} 0 0 0 {f(cx + shade_hw)} {f(shade)} Z" fill="#8A5A30"/>' + eye_svg
            + f'<path d="M{f(x0)} {f(tip)} C{f(x0 + .09)} {f(k_top)} {f(x1 - .09)} {f(k_top)} {f(x1)} {f(tip)} '
            f'C{f(x1 - .115)} {f(k_bot)} {f(x0 + .115)} {f(k_bot)} {f(x0)} {f(tip)} Z" fill="#F6E7B6"/>'
            f'<rect x="{f(cx - pat_w / 2)}" y="{f(pat_top)}" width="{f(pat_w)}" height="{f(pat_bottom - pat_top)}" rx="{f(12 * px1)}" fill="#E9B832"/>')


ICON_FOOD = _icon_geometry()


def potato_svg(size=None, rx=14):
    """A flat split baked russet with a butter pat on Sawtooth-pine green (the app icon, redrawn 2026-10-09 in the shared Eats
    Ranked icon style): make-brand.swift's geometry in a 64-unit box. No ids, so it can appear more than once on a page."""
    dims = f' width="{size}" height="{size}" aria-hidden="true" focusable="false"' if size else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"{dims}><rect width="64" height="64" rx="{rx}" fill="#2E5A4C"/>'
            + ICON_FOOD + "</svg>")


LOGO = potato_svg(30)
# The Sawtooths under the header: the app's RidgeLine (Theme.swift), sharp uneven granite teeth with three snow caps, on a
# huckleberry line. Colors come from the stylesheet (currentColor), so the CSP needs no inline style.
RIDGE_PEAKS = [(0, 0.62), (0.05, 0.42), (0.08, 0.55), (0.13, 0.18), (0.17, 0.44), (0.21, 0.30), (0.25, 0.50), (0.31, 0.06), (0.35, 0.36),
               (0.39, 0.24), (0.44, 0.52), (0.50, 0.14), (0.54, 0.40), (0.59, 0.28), (0.64, 0.55), (0.70, 0.10), (0.74, 0.38), (0.79, 0.26),
               (0.85, 0.52), (0.90, 0.22), (0.95, 0.45), (1, 0.36)]


def _ridge_svg():
    w, h = 1000, 26
    granite = "M0 26 " + " ".join(f"L{x * w:.0f} {y * (h - 3):.2f}" for x, y in RIDGE_PEAKS) + f" L{w} 26 Z"
    caps = []
    for x, y in ((0.31, 0.06), (0.70, 0.10), (0.50, 0.14)):
        hh = h - 3
        X, Y = x * w, y * hh
        caps.append(f"M{X:.1f} {Y:.2f} L{X - hh * .40:.1f} {(y + .34) * hh:.2f} L{X - hh * .10:.1f} {(y + .24) * hh:.2f} "
                    f"L{X + hh * .06:.1f} {(y + .34) * hh:.2f} L{X + hh * .36:.1f} {(y + .30) * hh:.2f} Z")
    return (f'<svg class="ridge" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true" focusable="false">'
            f'<path class="granite" d="{granite}"/><path class="snow" d="{" ".join(caps)}"/><rect class="line" x="0" y="{h - 3}" width="{w}" height="3"/></svg>')


RIDGE = _ridge_svg()

CSS = """
  :root {
    --bg: #f8f4ec; --surface: #fffdf9; --surface2: #f1ece2; --rule: #e2dacc; --rule2: #c7bba8;
    --ink: #1f1a24; --ink2: #3a3342; --muted: #5e5668;
    --huck: #4b2a5c; --pine: #2e5a4c; --on-dark: #fff; --russet: #c9a06b; --russetsoft: #efe1c8; --on-russet: #1f1a24;
    --land: #fffdf9; --mapbg: #e9e3d6; --county: rgba(94,86,104,.35); --dot: #4b2a5c; --pin-pick: #c9a06b; --pin-honor: #2e5a4c; --pin-edge: #1f1a24;
    --radius: 16px;
    --text: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif;
    --display: "Avenir Next Condensed", "HelveticaNeue-CondensedBold", "Arial Narrow", system-ui, sans-serif;
    color-scheme: light;
  }
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  @media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 17px/1.55 var(--text); -webkit-font-smoothing: antialiased; }
  a { color: var(--huck); text-underline-offset: 2px; }
  a:focus-visible, summary:focus-visible, button:focus-visible, select:focus-visible, input:focus-visible, [tabindex]:focus-visible { outline: 3px solid var(--pine); outline-offset: 2px; border-radius: 6px; }
  .skip { position: absolute; left: -9999px; top: 0; background: var(--russet); color: var(--on-russet); padding: 10px 14px; font-weight: 700; z-index: 30; }
  .skip:focus { left: 8px; top: 8px; }
  .vh { position: absolute !important; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
  .wrap { max-width: 760px; margin: 0 auto; padding: 0 20px; }
  header.site { display: flex; align-items: center; justify-content: space-between; gap: 6px 12px; padding: 12px 0 8px; }
  .ridge { display: block; width: 100%; height: 30px; color: var(--pine); }
  .ridge .granite { fill: var(--pine); } .ridge .snow { fill: #fff; opacity: .9; } .ridge .line { fill: var(--huck); }
  .logo { display: inline-flex; align-items: center; gap: 10px; min-height: 44px; font: 800 22px/1 var(--display); text-transform: uppercase; letter-spacing: .01em; color: var(--huck); text-decoration: none; }
  .logo svg { border-radius: 8px; flex: 0 0 auto; }
  header.site nav { display: flex; flex-wrap: wrap; gap: 0 12px; justify-content: flex-end; }
  header.site nav a, footer nav a, nav.crumbs a { display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; }
  header.site nav a { color: var(--ink2); text-decoration: none; font-size: 15px; }
  header.site nav a:hover { color: var(--huck); text-decoration: underline; }
  h1, h2 { font-family: var(--display); font-weight: 800; color: var(--huck); letter-spacing: -.005em; }
  h1 { font-size: clamp(34px, 7.5vw, 54px); line-height: 1.04; margin: 0 0 16px; text-transform: uppercase; overflow-wrap: anywhere; }
  .kicker { font: 700 15px/1.4 var(--text); letter-spacing: .06em; text-transform: uppercase; color: var(--muted); margin: 0 0 12px; }
  h2 { font-size: 32px; line-height: 1.1; margin: 0 0 10px; }
  h3 { font-size: 18px; margin: 0; line-height: 1.3; }
  .lede { font-size: 19px; color: var(--ink2); margin: 0 0 26px; }
  .hero { padding: 34px 0 28px; }
  section { padding: 36px 0; border-top: 1px solid var(--rule); }
  section.hero { border: 0; }
  .sub { color: var(--ink2); margin: 0 0 22px; }
  .cta-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 10px; min-height: 44px; background: var(--russet); color: var(--on-russet); font-weight: 700; padding: 13px 20px; border-radius: 14px; text-decoration: none; font-size: 17px; line-height: 1.2; }
  .btn-ghost { background: transparent; color: var(--huck); border: 2px solid var(--huck); }
  .store-badge { display: inline-flex; min-height: 44px; align-items: center; }
  .pill { font-size: 14px; color: var(--muted); }
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 28px 0 0; padding: 0; list-style: none; }
  .stats li { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 14px; }
  .stats b { display: block; font: 800 30px/1 var(--display); color: var(--huck); }
  .stats span { font-size: 14px; color: var(--muted); }
  .steps { display: grid; gap: 12px; list-style: none; margin: 0; padding: 0; }
  .step { display: flex; gap: 14px; background: var(--surface); border: 1px solid var(--rule); border-radius: var(--radius); padding: 18px; }
  .step .n { flex: 0 0 32px; height: 32px; border-radius: 50%; background: var(--russet); color: var(--on-russet); font-weight: 800; display: grid; place-items: center; }
  .step p { margin: 4px 0 0; color: var(--ink2); }
  .shots { display: flex; gap: 14px; overflow-x: auto; margin: 0 -20px; padding: 4px 20px 14px; scroll-snap-type: x proximity; list-style: none; }
  .shots li { flex: 0 0 auto; width: 210px; scroll-snap-align: start; }
  .shots img { display: block; width: 210px; height: auto; border-radius: 24px; border: 1px solid var(--rule); background: var(--surface2); }
  .shots p { font-size: 14px; color: var(--muted); margin: 8px 2px 0; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .card { background: var(--surface); border: 1px solid var(--rule); border-radius: var(--radius); padding: 18px; }
  .card p { margin: 6px 0 0; color: var(--ink2); }
  a.card { display: block; text-decoration: none; color: var(--ink); }
  a.card h3 { color: var(--huck); }
  a.card:hover h3 { text-decoration: underline; }
  .cities { display: flex; flex-wrap: wrap; gap: 8px; list-style: none; padding: 0; margin: 0; }
  .cities a { display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 8px 14px; border-radius: 999px; border: 1px solid var(--rule2); background: var(--surface); text-decoration: none; color: var(--ink); font-size: 15px; }
  .cities a:hover { border-color: var(--huck); }
  .cities a[aria-current] { border-color: var(--huck); font-weight: 700; }
  details { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 2px 18px; margin-bottom: 10px; }
  summary { cursor: pointer; padding: 14px 0; min-height: 44px; font-weight: 600; list-style: none; display: flex; justify-content: space-between; gap: 12px; }
  summary::-webkit-details-marker { display: none; }
  summary::after { content: "+"; color: var(--huck); font-weight: 800; }
  details[open] summary::after { content: "\\2013"; }
  details p { margin: 0 0 16px; color: var(--ink2); }
  .final { text-align: center; }
  .final .cta-row { justify-content: center; }
  nav.crumbs { font-size: 14px; color: var(--muted); padding: 6px 0 0; }
  nav.crumbs ol { list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 0 6px; }
  nav.crumbs li { display: inline-flex; align-items: center; min-height: 44px; }
  nav.crumbs li + li::before { content: "/"; margin-right: 6px; color: var(--muted); }
  nav.crumbs a { color: var(--muted); }
  .places { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
  .places li { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 14px 16px; min-width: 0; overflow-wrap: anywhere; scroll-margin-top: 12px; }
  .places li:target { border-color: var(--huck); box-shadow: 0 0 0 2px var(--huck); }
  .places h3 a { display: block; padding: 11px 0; margin: -11px 0; text-decoration: none; }
  .places h3 a:hover { text-decoration: underline; }
  .places .where { margin: 2px 0 0; font-size: 15px; color: var(--muted); }
  .places .facts { margin: 8px 0 0; font-size: 15px; color: var(--ink2); }
  .places .facts b { color: var(--ink); font-weight: 600; }
  .places .note { margin: 6px 0 0; font-size: 15px; color: var(--ink2); }
  .places .fine { margin: 6px 0 0; }
  .places .link { font-size: 15px; margin: 2px 0 -8px; }
  .places .link a, .near a, .toc a, .plinks a, td a, .lookup a { display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; }
  .tag { display: inline-block; font-size: 12px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; background: var(--russetsoft); color: var(--on-russet); border-radius: 6px; padding: 1px 6px; margin-right: 4px; }
  .tag-jb { background: var(--pine); color: var(--on-dark); }
  .toc { columns: 2; padding-left: 20px; margin: 0; }
  .near { list-style: none; padding: 0; margin: 0; }
  .near span { display: block; font-size: 14px; color: var(--muted); margin: -8px 0 6px; }
  .actions { display: flex; flex-wrap: wrap; gap: 10px; margin: 6px 0 0; }
  .actions .btn { font-size: 16px; padding: 10px 16px; }
  dl.facts { display: grid; grid-template-columns: max-content 1fr; gap: 10px 18px; margin: 0 0 18px; }
  dl.facts dt { font-weight: 700; color: var(--ink); }
  dl.facts dd { margin: 0; color: var(--ink2); }
  dl.facts ul { margin: 0; padding-left: 18px; }
  .addr { font-size: 17px; color: var(--ink2); margin: 0 0 14px; }
  .qa h3 { margin: 22px 0 6px; font-size: 19px; }
  .qa p { margin: 0 0 10px; color: var(--ink2); }
  table { border-collapse: collapse; width: 100%; font-size: 15px; }
  th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--rule); vertical-align: top; }
  td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
  .tbl { overflow-x: auto; }
  .fine { font-size: 14px; color: var(--muted); }
  .legal h2 { font-size: 26px; margin-top: 28px; }
  .legal p, .legal li { color: var(--ink2); }
  .notice { white-space: pre-wrap; font-size: 14px; color: var(--ink2); background: var(--surface); border: 1px solid var(--rule); border-radius: 12px; padding: 14px; overflow-wrap: anywhere; }
  footer { padding: 24px 0 56px; color: var(--muted); font-size: 14px; border-top: 1px solid var(--rule); margin-top: 20px; }
  footer nav { display: flex; flex-wrap: wrap; gap: 0 18px; }
  footer a { color: var(--muted); }
  footer p { margin: 12px 0 0; }
  @media (max-width: 600px) {
    .grid2 { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
    .toc { columns: 1; }
    header.site { flex-direction: column; align-items: flex-start; }
    header.site nav { justify-content: flex-start; }
    dl.facts { grid-template-columns: 1fr; gap: 2px; }
    dl.facts dd { margin-bottom: 10px; }
    th, td { padding: 8px 4px; font-size: 14px; }
  }
"""


# ---------------------------------------------------------------- structured data shared by every page
ORG_ID, PERSON_ID, SITE_ID = f"{DOMAIN}/#org", f"{DOMAIN}/about.html#nicholas-soderstrom", f"{DOMAIN}/#website"
BASE_LD = {"@context": "https://schema.org", "@graph": [
    {"@type": "Organization", "@id": ORG_ID, "name": BRAND, "url": f"{DOMAIN}/",
     "logo": {"@type": "ImageObject", "url": f"{DOMAIN}/icon-512.png", "width": 512, "height": 512}, "founder": {"@id": PERSON_ID},
     "email": EMAIL, "contactPoint": {"@type": "ContactPoint", "contactType": "customer support", "email": EMAIL, "availableLanguage": "en"},
     # the Eats Ranked hub lists this site as a subOrganization; say so from this side too (Wisconsin's wording, wi-eats a6d63a5)
     "parentOrganization": {"@type": "Organization", "@id": "https://eatsranked.com/#organization", "name": "Eats Ranked",
                            "url": "https://eatsranked.com/"}},
    {"@type": "Person", "@id": PERSON_ID, "name": AUTHOR, "url": f"{DOMAIN}/about.html"},
    {"@type": "WebSite", "@id": SITE_ID, "name": BRAND, "alternateName": [APP_NAME, "Idaho Eats app"], "url": f"{DOMAIN}/",
     "inLanguage": "en", "publisher": {"@id": ORG_ID}}]}


def jsonld(obj):
    # "<", ">" and "&" as \u escapes: a place name containing "</script>" can't end the block early
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return '<script type="application/ld+json">' + raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026") + "</script>"


def crumbs(trail):
    """trail: [(name, url)] ending with the current page."""
    items = "".join(f'<li><a href="{u}">{e(n)}</a></li>' if i < len(trail) - 1 else f'<li aria-current="page">{e(n)}</li>'
                    for i, (n, u) in enumerate(trail))
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": DOMAIN + u} for i, (n, u) in enumerate(trail)]}
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{items}</ol></nav>', ld


STORE_NOTE = "Free for iPhone and iPad." if APP_STORE_URL else f"{BRAND} for iPhone and iPad is free, with its App Store release still ahead."


def store_button(label="Ask for early access"):
    if APP_STORE_URL:   # Apple's own badge artwork, unaltered (see APP_STORE_URL above)
        return (f'<a class="store-badge" href="{e(APP_STORE_URL)}" rel="noopener">'
                f'<img src="{APP_STORE_BADGE}" alt="Download on the App Store" width="120" height="40"></a>')
    # a plain mailto button until launch: no Apple logo (Apple allows it only in its own badge artwork). Only Nick's internal
    # TestFlight group exists (Nick, 2026-10-13), so the label is an ask and no copy says we'll send an invite or a link.
    return (f'<a class="btn store-btn" href="mailto:{EMAIL}?subject=Idaho%20Eats%20early%20access&amp;body=Send%20me%20the%20TestFlight%20link.">'
            f'<span class="store-label">{label}</span></a>')


def cta(extra=""):
    return f'<div class="cta-row">{store_button()}{extra}<span class="pill store-note">{STORE_NOTE}</span></div>'


def sha256_src(s):
    return "'sha256-" + base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode() + "'"


def csp_for(doc):
    """A strict policy for one finished page: only its own inline <script>/<style> blocks (by hash), same-origin data and images."""
    assert not re.search(r"<script(?![^>]*application/ld\+json)[^>]+>", doc), "only plain inline <script> and JSON-LD are allowed"
    assert not re.search(r"<[a-zA-Z][^>]*\sstyle=", doc), "inline style attributes would be blocked by the CSP"
    assert not re.search(r"<[a-zA-Z][^>]*\son[a-z]+=", doc), "inline event handlers would be blocked by the CSP"
    scripts = re.findall(r"<script>(.*?)</script>", doc, re.S)          # executable inline scripts (JSON-LD blocks are data, not run)
    styles = re.findall(r"<style>(.*?)</style>", doc, re.S)
    none = "'none'"
    return ("default-src 'none'; "
            f"script-src {' '.join(sha256_src(s) for s in scripts) or none}; "
            f"style-src {' '.join(sha256_src(s) for s in styles) or none}; "
            "img-src 'self' data:; connect-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'")


CSP_SLOT = "__CSP__"
written, noindexed = [], []
TITLES, DESCS = {}, {}


def nav_links():
    """The header: up to three Idaho guide pages that exist, then Cities and Search."""
    out = [f'<a href="/{g["path"]}">{e(g["nav"])}</a>' for g in PAGED[:3]]
    return "\n      ".join(out + ['<a href="/cities/">Cities</a>', '<a href="/explore/">Search</a>'])


def footer_links():
    out = [f'<a href="/">{BRAND} app</a>', '<a href="/explore/">Search Idaho restaurants</a>']
    out += [f'<a href="/{g["path"]}">{e(cap1(g["name"].replace("Idaho ", "", 1)))}</a>' for g in PAGED]
    if HON_PAGE:
        out.append(f'<a href="/{HON_PATH}">James Beard honorees</a>')
    if OLD_PAGE:
        out.append(f'<a href="/{OLD_PATH}">Oldest restaurants</a>')
    out += [f'<a href="/{INS_PATH}">Restaurant inspections</a>', '<a href="/cities/">Cities and regions</a>', '<a href="/about.html">About and sources</a>',
            '<a href="/privacy.html">Privacy policy</a>', '<a href="/terms.html">Terms of use</a>', f'<a href="mailto:{EMAIL}">Email us</a>']
    return "\n      ".join(out)


SOURCES_LINE = (f"Place data: hand-checked research by {BRAND} ({CHECKED}); Overture Maps Foundation places data (CDLA Permissive 2.0), including "
                "data from Foursquare (Apache 2.0) and AllThePlaces (CC0 1.0), and Overture addresses; county outlines © OpenStreetMap contributors "
                "and Overture Maps Foundation (ODbL)" + ("; Idaho State Police Alcohol Beverage Control retail alcohol licenses" if ABC else "")
                + f". Restaurant data as of {hdate(D['generated'])}. Not affiliated with or endorsed by any restaurant, team, chain, university "
                "or government agency, or the James Beard Foundation. James Beard Foundation and James Beard Award are trademarks of the James "
                "Beard Foundation. Places open and close, so check before you go.")


def page(path, title, desc, body, lds=(), robots="index,follow,max-image-preview:large", og_alt=None, extra_css="", og_type="article"):
    is404 = path == "404.html"
    if not is404:
        assert 50 <= len(title) <= 60, (path, len(title), title)
        assert 140 <= len(desc) <= 160, (path, len(desc), desc)
        assert title not in TITLES, ("duplicate title", path, TITLES.get(title))
        assert desc not in DESCS, ("duplicate description", path, DESCS.get(desc))
        TITLES[title], DESCS[desc] = path, path
    assert body.count("<h1") == 1, path
    assert "<!--" not in body, f"{path}: no HTML comments in the output"
    url = DOMAIN + "/" + ("" if path == "index.html" else path.removesuffix("index.html"))
    indexed = "noindex" not in robots
    og_alt = og_alt or f"{BRAND}: {TAGLINE}. Idaho restaurants, with hand-checked Basque kitchens, finger steaks, drive-ins and spud plates."
    ld = "\n".join(jsonld(x) for x in (BASE_LD, *lds))
    canon = f'<link rel="canonical" href="{url}">\n' if indexed and not is404 else ""
    og_url = f'<meta property="og:url" content="{url}">\n' if indexed and not is404 else ""
    # the Smart App Banner once the App Store record exists; until then the SEO spec's placeholder (the only comment in any page)
    banner = (f'<meta name="apple-itunes-app" content="app-id={APP_ID}">\n' if APP_STORE_URL else
              '<!-- <meta name="apple-itunes-app" content="app-id=APP_ID"> fill in once the App Store record exists -->\n')
    doc = f"""<!DOCTYPE html>
<html lang="en" data-base="{BASE}">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP_SLOT}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="strict-origin-when-cross-origin">
<meta name="color-scheme" content="light">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
{canon}<meta name="robots" content="{robots}">
<meta name="theme-color" content="#4b2a5c">
{banner}<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
{og_url}<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{BRAND}">
<meta property="og:locale" content="en_US">
<meta property="og:image" content="{DOMAIN}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(og_alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{DOMAIN}/og.png">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<style>{CSS}{extra_css}</style>
{ld}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="wrap">
  <header class="site">
    <a class="logo" href="/" aria-label="{BRAND} home">{LOGO}{BRAND}</a>
    <nav aria-label="Main">
      {nav_links()}
    </nav>
  </header>
  {RIDGE}
{body}
  <footer>
    <nav aria-label="Footer">
      {footer_links()}
    </nav>
    <p>{e(SOURCES_LINE)}</p>
    <p>© 2026 {BRAND}, an independent app by {AUTHOR}. Part of <a href="https://eatsranked.com/" rel="noopener">Eats Ranked</a>, restaurant apps state by state.</p>
  </footer>
</div>
</body>
</html>
"""
    if BASE:   # served under /idaho-eats/: every root-relative link and asset gets the prefix
        doc = re.sub(r'(href|src|srcset)="/', rf'\1="{BASE}/', doc)
    doc = doc.replace(CSP_SLOT, csp_for(doc), 1)   # hashed last, over the exact bytes the browser will see
    os.makedirs(os.path.dirname(f"{DOCS}/{path}"), exist_ok=True)
    open(f"{DOCS}/{path}", "w").write(doc)
    if not is404:
        (written if indexed else noindexed).append(path)
    return path


def article_ld(url, headline, desc):
    return {"@context": "https://schema.org", "@type": "Article", "headline": headline, "description": desc,
            "datePublished": PUBLISHED, "dateModified": TODAY, "inLanguage": "en", "mainEntityOfPage": url,
            "image": f"{DOMAIN}/og.png", "author": {"@id": PERSON_ID}, "publisher": {"@id": ORG_ID}, "isPartOf": {"@id": SITE_ID}}


# ---------------------------------------------------------------- place pages: slugs first, so every list can link to them
PAGE_PLACES = sorted([p for p in REST if p.hc or p.jbf], key=lambda p: (p.city, p.name.lower(), p.id))
_groups = defaultdict(list)
for p in PAGE_PLACES:
    _groups[slug(f"{p.name} {p.city or 'idaho'}")].append(p)
for base_slug, ps in _groups.items():
    if len(ps) == 1:
        ps[0].slug = base_slug
        continue
    with_addr = Counter(f"{base_slug}-{slug(p.addr)}" for p in ps)
    for p in ps:    # every member of a clash gets the same treatment, so slugs don't depend on order
        s = f"{base_slug}-{slug(p.addr)}"
        p.slug = s if with_addr[s] == 1 and p.addr else f"{base_slug}-{p.id[:6]}"
assert len({p.slug for p in PAGE_PLACES}) == len(PAGE_PLACES)


def place_url(p):
    return f"/places/{p.slug}.html"


class Anchors:
    """Gives each place an id (its place-page slug) the first time it appears on a page, so ItemList items can point to page#id."""
    RESERVED = {"main", "about", "questions", "list", "honors", "oldest", "cuisines", "more", "towns", "how", "what", "guides", "cities",
                "regions", "faq", "download", "screens", "pricing", "privacy", "checked", "nearby", "app", "inspections", "districts",
                "lookup", "nicholas-soderstrom", "sources", "notice"} | {g["sec"] for g in GUIDES}

    def __init__(self, page_url):
        self.page_url, self.used, self.of = page_url, set(self.RESERVED), {}

    def take(self, p):
        if id(p) in self.of:
            return None
        base_id = p.slug or slug(p.name + (" " + p.zip if p.zip else "")) or "place"
        a, n = base_id, 2
        while a in self.used:
            a, n = f"{base_id}-{n}", n + 1
        self.used.add(a)
        self.of[id(p)] = a
        return a

    def url(self, p):
        return f"{self.page_url}#{self.of[id(p)]}"


def place_item(p, anchors=None, extra=None, show_fn=False, honors=False):
    facts = []
    if p.dishes:
        facts.append(f"<b>On the menu:</b> {e(p.dishes)}")
    if p.founded:
        facts.append(f"<b>Since</b> {e(str(p.founded))}")
    if p.season:
        facts.append(f"<b>Season:</b> {e(p.season)}")
    kinds = []
    if p.jb_label():
        kinds.append(('<span class="tag tag-jb">', e(p.jb_label())))
    for g in guides_of(p):
        for t in g["tags"]:
            if p.tags & BIT[t]:
                lab = {"fingersteak": "Finger steaks", "drivein": "Drive-in"}.get(t, g["chip"])
                if (('<span class="tag">', lab)) not in kinds:
                    kinds.append(('<span class="tag">', lab))
    where = ", ".join(x for x in (p.addr, p.city) if x)
    if extra:
        where += f" · {extra}"
    aid = anchors.take(p) if anchors else None
    name = f'<a href="{place_url(p)}">{e(p.name)}</a>' if p.slug else e(p.name)
    out = [f'<li id="{e(aid)}">' if aid else "<li>", f"<h3>{name}</h3>", f'<p class="where">{e(where)}</p>']
    if kinds or facts:
        out.append('<p class="facts">' + "".join(f"{tag}{k}</span>" for tag, k in kinds) + (" " + " · ".join(facts) if facts else "") + "</p>")
    if p.note:
        out.append(f'<p class="note">{e(p.note)}</p>')
    if show_fn and p.fn:
        out.append(f'<p class="fine">{e(p.fn)}</p>')
    if honors and p.jbf:
        out.append('<p class="fine">' + e("; ".join("James Beard: " + x for x in p.jbf.split("; "))) + "</p>")
    if p.site:
        host = re.sub(r"^https?://(www\.)?", "", p.site, flags=re.I).split("/")[0]
        out.append(f'<p class="link"><a href="{e(p.site)}" rel="noopener nofollow">{e(host)}</a></p>')
    out.append("</li>")
    return "".join(out)


def restaurant_ld(p, item_url):
    addr = {"@type": "PostalAddress"}
    if p.addr:
        addr["streetAddress"] = p.addr
    if p.city:
        addr["addressLocality"] = p.city
    addr["addressRegion"] = "ID"
    if p.zip:
        addr["postalCode"] = p.zip
    addr["addressCountry"] = "US"
    x = {"@type": "Restaurant", "name": p.name, "url": item_url, "address": addr}
    if p.lat is not None and p.lon is not None:
        x["geo"] = {"@type": "GeoCoordinates", "latitude": round(p.lat, 5), "longitude": round(p.lon, 5)}
    if p.site:
        x["sameAs"] = p.site
    if p.tel:
        x["telephone"] = p.tel
    if p.founded:
        x["foundingDate"] = str(p.founded)
    if p.cuisine and p.cuisine not in ("Other", "Restaurant", "American & Other", "Bar & Pub"):
        x["servesCuisine"] = p.cuisine
    return x


def item_list(name, places, url, anchors):
    """An all-on-one-page list: each item's url is its anchor on this page; the restaurant's own site goes in sameAs."""
    return {"@context": "https://schema.org", "@type": "ItemList", "name": name, "url": url, "numberOfItems": len(places),
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": restaurant_ld(p, anchors.url(p))} for i, p in enumerate(places)]}


def by_region(places, key=lambda p: (p.city, p.name.lower())):
    groups = defaultdict(list)
    for p in places:
        groups[p.region or "Elsewhere in Idaho"].append(p)
    order = [d["name"] for d in DISTRICTS] + ["Elsewhere in Idaho"]
    return [(r, sorted(groups[r], key=key)) for r in order if groups.get(r)]


REGION_SLUG = {d["name"]: d["slug"] for d in DISTRICTS}


def region_sections(places, noun, plural_noun, anchors, **item_kw):
    toc = '<ul class="toc">' + "".join(f'<li><a href="#{slug(r)}">{e(r)}</a> ({len(ps)})</li>' for r, ps in by_region(places)) + "</ul>"
    secs = []
    for r, ps in by_region(places):
        anchors.used.update({slug(r), "h-" + slug(r)})
        more = f' The <a href="/regions/{REGION_SLUG[r]}.html">{e(r)} page</a> has the region\'s other lists.' if r in REGION_SLUG else ""
        secs.append(f'<section id="{slug(r)}" aria-labelledby="h-{slug(r)}"><h2 id="h-{slug(r)}">{e(r)}</h2>'
                    f'<p class="sub">{plural(len(ps), noun, plural_noun)}, by town.{more}</p><ol class="places">'
                    + "".join(place_item(p, anchors, **item_kw) for p in ps) + "</ol></section>")
    return toc, "\n".join(secs)


def dish_counts(places):
    c = Counter()
    for p in places:
        for d in dict.fromkeys(x.lower() for x in p.dish_list):   # in menu order, once per place (a set's order changes run to run)
            c[d] += 1
    return c


def dish_line(places, k=6, min_n=1, rx=None):
    # most named first, ties A to Z, so the same data always writes the same page (and the same CSP hashes); rx keeps a topical guide's
    # line to its own food (a huckleberry place's finger steaks aren't a huckleberry dish)
    top = [(d, n) for d, n in sorted(dish_counts(places).items(), key=lambda x: (-x[1], x[0])) if n >= min_n and (not rx or re.search(rx, d))][:k]
    return ", ".join(f"{d} ({n})" for d, n in top)


def town_line(places, k=5):
    return ", ".join(f"{t} ({n})" for t, n in Counter(p.city for p in places if p.city).most_common(k))


# ---------------------------------------------------------------- cities: each place on its nearest city page only
CITY_WANTED = ["Boise", "Meridian", "Nampa", "Idaho Falls", "Pocatello", "Caldwell", "Coeur d'Alene", "Twin Falls", "Post Falls", "Lewiston",
               "Rexburg", "Eagle", "Moscow", "Sandpoint", "Ketchum", "McCall", "Hailey"]
CITY_PAGES = [c for c in CITY_WANTED if any(p.city == c and p.lat is not None for p in REST)]   # a town the data lost gets no page
CENTER, N_TOWN = {}, {}
for c in CITY_PAGES:
    here = [p for p in REST if p.city == c and p.lat is not None]
    CENTER[c] = (sorted(p.lat for p in here)[len(here) // 2], sorted(p.lon for p in here)[len(here) // 2])
    N_TOWN[c] = sum(1 for p in REST if p.city == c)
RADIUS = 15   # miles: a place outside a city-page town is listed on the closest city page within this distance, and only there


def home_city(p):
    """The one city page a place is listed on: its own town's, else the closest city page within RADIUS, else none. A mailing
    address can name a town far away (a lodge in the Sawtooth Valley with a Ketchum address), so even the own town counts only
    within RADIUS of the town's center."""
    if p.lat is None:
        return (p.city, 0.0) if p.city in CENTER else (None, None)
    if p.city in CENTER and miles(CENTER[p.city], (p.lat, p.lon)) <= RADIUS:
        return p.city, 0.0
    d, c = min((miles(CENTER[c], (p.lat, p.lon)), c) for c in CITY_PAGES)
    return (c, d) if d <= RADIUS else (None, d)


for p in PLACES:
    p.home, p.home_miles = home_city(p)


def city_url(c):
    return f"/cities/{slug(c)}.html"


def city_links(current=None, cities=None):
    cities = CITY_PAGES if cities is None else cities
    return '<ul class="cities">' + "".join(f'<li><a href="{city_url(c)}"{" aria-current=" + chr(34) + "page" + chr(34) if c == current else ""}>{e(c)}</a></li>'
                                           for c in cities) + "</ul>"


def region_links(current=None):
    return '<ul class="cities">' + "".join(f'<li><a href="/regions/{d["slug"]}.html"{" aria-current=" + chr(34) + "page" + chr(34) if d["slug"] == current else ""}>{e(d["name"])}</a></li>'
                                           for d in DISTRICTS) + "</ul>"


GUIDE_LINKS = ([("/" + g["path"], cap1(g["name"])) for g in PAGED] + ([("/" + HON_PATH, "Idaho James Beard honorees")] if HON_PAGE else [])
               + ([("/" + OLD_PATH, "Idaho's oldest restaurants")] if OLD_PAGE else []) + [("/" + INS_PATH, "Idaho restaurant inspections")])


def other_guides(skip):
    return "Other guides: " + ", ".join(f'<a href="{u}">{e(t)}</a>' for u, t in GUIDE_LINKS if u != skip) + "."


def qa_html(title, qas):
    return f'<section id="questions" class="qa"><h2>{e(title)}</h2>' + "".join(f"<h3>{e(q)}</h3><p>{a}</p>" for q, a in qas) + "</section>"


def guide_page(path, h1, kicker, title_opts, desc_opts, lede, about_html, places, noun, plural_noun, list_name, qas=None, qa_title="",
               region=True, **item_kw):
    url = f"{DOMAIN}/{path}"
    title, desc = fit(title_opts, 50, 60, path + " title"), fit(desc_opts, 140, 160, path + " description")
    nav, bc = crumbs([("Home", "/"), (h1, "/" + path)])
    anchors = Anchors(url)
    if region:
        toc, secs = region_sections(places, noun, plural_noun, anchors, **item_kw)
        jump = f"<h2>Jump to a region</h2>\n    {toc}"
    else:
        secs = (f'<section id="list" aria-labelledby="h-list"><h2 id="h-list">Oldest first</h2><ol class="places">'
                f'{"".join(place_item(p, anchors, **item_kw) for p in places)}</ol></section>')
        jump = ""
    body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{kicker}</p>
    <h1>{e(h1)}</h1>
    <p class="lede">{lede}</p>
    {cta()}
  </section>
  <section id="about">
    {about_html}
    <p class="fine">{other_guides("/" + path)} City pages: {", ".join(f'<a href="{city_url(c)}">{e(c)}</a>' for c in CITY_PAGES)}. Regions: {", ".join(f'<a href="/regions/{d["slug"]}.html">{e(d["name"])}</a>' for d in DISTRICTS)}.</p>
    {jump}
  </section>
{qa_html(qa_title, qas) if qas else ""}
{secs}
  </main>"""
    page(path, title, desc, body, [article_ld(url, h1, desc), bc, item_list(list_name, places, url, anchors)])


HOW_BUILT = ("How this list was made: for every place we read a 2025 or 2026 source, usually its own menu page or a dated story in Idaho "
             "news, and matched the street address to it. A place whose only source was older, whose website had gone dark, or whose menu "
             "named the dish just in passing stayed off. Review sites played no part, and the places run by region and town, not by anybody's "
             f"score. Menus change, so check before you go. Our sources are on the <a href=\"/about.html\">about {BRAND}</a> page.")
IN_APP = (f"On an iPhone or iPad, {BRAND} puts this same list in order of distance from wherever you're standing, and a tap on a place "
          "brings up Apple Maps' card with today's hours, photos and directions.")


def std_titles(g, n, extra=()):
    nm = g["short"]
    return list(extra) + [f"{nm} Around Idaho: {n} Places We Checked | {BRAND}", f"{nm} Across Idaho, {n} Places Read Against Menus",
                          f"{nm} in Idaho: {n} Places, Each One Checked | {BRAND}", f"Idaho {nm}, Town by Town: {n} Places | {BRAND}",
                          f"Idaho {nm}: {n} Places We Checked by Hand", f"{nm} in Idaho, {n} Places | {BRAND}"]


def std_descs(g, places, what):
    n = len(places)
    towns = join_words([t for t, _ in Counter(p.city for p in places if p.city).most_common(3)])
    base = [f"{cap1(what)} at {plural(n, 'Idaho place')}, from {towns} on. We read each one's 2025–26 menu or local news in {CHECKED}.",
            f"{cap1(what)}: {plural(n, 'Idaho place')} grouped by region and town, each read against its own menu or local news in {CHECKED}.",
            f"Where Idaho serves {what}: {plural(n, 'place')} in {towns} and beyond, each matched to a 2025–26 menu or news story in {CHECKED}.",
            f"{plural(n, g['noun'], g['nouns'])} around Idaho, listed by region and town with dishes, seasons and links, each matched to a 2025–26 source in {CHECKED}."]
    return base + [x + y for x in base for y in (" No ratings.", " Free, no ads.", " No ratings, no ads.", " The app is coming soon.")]


# ---------------------------------------------------------------- the Idaho guide pages
def guide_copy(g):
    """Each guide's own words. Only facts we can stand behind plus counts from the data; no claim about places we didn't check."""
    ps, n = g["places"], len(g["places"])
    topic = {"huckleberry": ("Huckleberry dishes", r"huckleberr"), "trout": ("Trout dishes", r"trout"),
             "spuds": ("Potato dishes", r"potato|spud|fries|russet|hash brown|tots|baker")}.get(g["key"], ("Dishes", None))
    dl = dish_line(ps, rx=topic[1])
    dishes_p = f"<p>{topic[0]} these menus name most: {e(dl)}.</p>" if dl else ""
    in_boise = sum(1 for p in ps if p.city == "Boise")
    towns = town_line(ps)
    by_town = f"<p>Where they are, by town: {e(towns)}.</p>" if towns else ""
    k = g["key"]
    if k == "basque":
        about = f"""<h2>Basque food in Idaho, briefly</h2>
    <p>Basque immigrants from the Pyrenees, on both sides of the Spain–France border, came to Idaho from the late 1800s on, many to herd sheep in the high desert, and Boise still has one of the largest Basque communities in the United States. Its center is the Basque Block, the stretch of Grove Street downtown between Capitol Boulevard and 6th Street, with the Basque Museum &amp; Cultural Center, the Basque Center and several of the places below. The food is hearty: chorizo, croquetas, solomo (marinated pork loin), lamb, beans and paella.</p>
    <h2>Where the Basque places are</h2>
    <p>{n_word(in_boise, n)} of the {n:,} are in Boise.</p>
    {dishes_p}
    <p>{HOW_BUILT}</p>
    <p>{IN_APP}</p>"""
        qas = [("Where is Boise's Basque Block?", "On Grove Street in downtown Boise, between Capitol Boulevard and 6th Street. The places on this list with a Grove Street or Capitol Boulevard address are on it or next to it; their addresses are with each place."),
               ("What is solomo?", "Pork loin marinated with garlic and paprika, then grilled, often served as a sandwich with roasted red peppers. It's a Basque-Idaho staple, and the menus here say which places serve it."),
               ("What are croquetas?", f"Small fried croquettes with a creamy filling, often ham or chicken. {dish_n(ps, 'croquetas')} of the {plural(n, 'place')} here list them."),
               ("Is this every Basque restaurant in Idaho?" if False else "Why isn't my favorite Basque place here?",
                f"The list grows as places are checked. A place is in only when a 2025 or 2026 source shows it serving Basque food at this address. Tell us at <a href=\"mailto:{EMAIL}\">{EMAIL}</a>.")]
        return dict(kicker="Basque", what="Basque food from Boise's Basque Block and beyond", about=about, qas=qas, qa_title="Basque questions",
                    titles=std_titles(g, n, [f"Basque Food in Idaho: {n} Restaurants, Bars & Markets", f"Basque Restaurants in Idaho: {n}, From the Basque Block On",
                                             f"Idaho Basque Restaurants, Boise's Basque Block & More ({n})"]),
                    descs=std_descs(g, ps, "Basque food: chorizo, croquetas, solomo and lamb from Boise's Basque Block and beyond"),
                    lede=f"Chorizo, croquetas and solomo: {plural(n, 'Idaho restaurant')}, bars and markets that cook Basque food, {words_num(in_boise)} of them in Boise. We read each one's 2025–26 menu or a recent local news story in {CHECKED}, and every listing names its dishes and, where a source documents it, the year it opened at this address.")
    if k == "fingersteaks":
        nf = sum(1 for p in ps if p.tags & BIT["fingersteak"])
        nd = sum(1 for p in ps if p.tags & BIT["drivein"])
        fry = dish_n(ps, "fry sauce")
        about = f"""<h2>Finger steaks, briefly</h2>
    <p>Finger steaks are strips of steak, battered and deep-fried, served with fries and a dipping sauce, often fry sauce (ketchup mixed with mayonnaise). They've been on Boise menus since the 1950s and are still a fixture at Idaho drive-ins, alongside burgers, shakes and fry sauce.</p>
    <h2>Steaks, drive-ins and fry sauce, counted</h2>
    <p>{n_word(nf, n)} of the {n:,} serve finger steaks, {words_num(nd)} {"is a drive-in" if nd == 1 else "are drive-ins"} (a place can be both), and {words_num(fry)} list fry sauce on the menu.</p>
    {dishes_p}
    <p>{HOW_BUILT}</p>
    <p>{IN_APP}</p>"""
        qas = [("What are finger steaks?", "Strips of steak, battered and deep-fried like chicken strips, served with fries and a dipping sauce. They're an Idaho specialty you'll mostly find at drive-ins, diners and taverns."),
               ("What is fry sauce?", f"A pink sauce of ketchup and mayonnaise, sometimes with pickle juice or spices, for dipping fries and finger steaks. {cap1(words_num(fry))} of the {plural(n, 'place')} here list it."),
               ("What counts as a drive-in here?", "A burger stand with a walk-up window, carhop or drive-thru service, as the place itself or local news describes it. Each one was checked by hand against a 2025 or 2026 source.")]
        return dict(kicker="Finger steaks &amp; drive-ins", what="finger steaks, fry sauce and drive-in burgers", about=about, qas=qas, qa_title="Finger steak questions",
                    titles=[f"Finger Steaks & Fry Sauce in Idaho: {n} Drive-Ins & Diners", f"Where to Get Finger Steaks in Idaho: {n} Drive-Ins & Diners",
                            f"Idaho Finger Steaks and Drive-Ins, {n} Places | {BRAND}"] + std_titles(g, n),
                    descs=std_descs(g, ps, "finger steaks, fry sauce and drive-in burgers"),
                    lede=f"Battered steak strips with fry sauce, and burgers handed through a window: {plural(n, 'Idaho drive-in')}, diners and taverns, every one read against its own 2025–26 menu or a recent local news story in {CHECKED}.")
    if k == "spuds":
        about = f"""<h2>Idaho potatoes on the plate</h2>
    <p>Idaho grows more potatoes than any other state, and the russet is the classic Idaho baker. This list is the places where a potato is the point of the plate: loaded baked potatoes, fresh-cut fries, hash browns, potato dishes the menu names. Some aren't potatoes at all: the Idaho Ice Cream Potato is ice cream made to look like a baked spud.</p>
    <h2>What the spud menus name</h2>
    {dishes_p}
    {by_town}
    <p>{HOW_BUILT}</p>
    <p>{IN_APP}</p>"""
        qas = [("What is a spud plate?", "Our name for a dish where Idaho potatoes are the point: a loaded baked potato, a potato named on the menu, fresh-cut fries made a fuss of. A place is on the list when its own 2025 or 2026 menu, or local news, names the dish."),
               ("What is an Idaho Ice Cream Potato?", f"A dessert made to look like a baked potato: ice cream shaped and dusted to look like the skin, with toppings standing in for butter and sour cream. {cap1(words_num(dish_n(ps, 'idaho ice cream potato')))} of the places here list it."),
               ("Are the potatoes local?", "Sometimes, and when a place says where its potatoes come from, the note under it says so. Otherwise we don't assume.")]
        return dict(kicker="Spud plates", what="baked potatoes, fresh-cut fries and potato plates named on the menu", about=about, qas=qas, qa_title="Spud questions",
                    titles=[f"Idaho Potatoes on the Plate: {n} Spud Spots | {BRAND}", f"Spud Plates in Idaho: {n} Places Where the Potato Leads",
                            f"Loaded Bakers & Fresh-Cut Fries in Idaho: {n} Places"] + std_titles(g, n),
                    descs=std_descs(g, ps, "Idaho potatoes: loaded bakers, fresh-cut fries and spud plates named on the menu"),
                    lede=f"Loaded bakers, fresh-cut fries and potato dishes with their own names on the menu: {plural(n, 'place')} around the country's biggest potato state, every one matched to a 2025–26 menu or news story in {CHECKED}.")
    if k == "huckleberry":
        about = f"""<h2>Idaho huckleberries, briefly</h2>
    <p>The huckleberry is Idaho's state fruit. It grows wild in mountain forests and ripens in mid to late summer, and it's picked by hand rather than farmed at scale, so it turns up in shakes, pies, pancakes, sauces and cocktails, especially in north Idaho and the resort towns. Menus with huckleberry change with the season, so check before you go.</p>
    <h2>What the huckleberry menus name</h2>
    {dishes_p}
    {by_town}
    <p>{HOW_BUILT}</p>
    <p>{IN_APP}</p>"""
        qas = [("When is huckleberry season in Idaho?", "Wild huckleberries ripen in mid to late summer, later at higher elevations. Some places serve huckleberry dishes only then or on a seasonal menu; each place's note says what its 2025 or 2026 menu named."),
               ("Is the huckleberry Idaho's state fruit?", "Yes. The Idaho Legislature named the huckleberry the state fruit in 2000."),
               ("What huckleberry dishes are on the list?", f"The ones the menus name: {e(dish_line(ps, 8, rx=r'huckleberr')) or 'see each place below'}.")]
        return dict(kicker="Huckleberry", what="huckleberry shakes, pies, pancakes and sauces", about=about, qas=qas, qa_title="Huckleberry questions",
                    titles=[f"Huckleberry Shakes, Pies & Pancakes in Idaho: {n} Places", f"Where to Eat Huckleberry in Idaho: {n} Places | {BRAND}",
                            f"Idaho's State Fruit on the Menu: {n} Huckleberry Spots"] + std_titles(g, n),
                    descs=std_descs(g, ps, "huckleberry shakes, pies, pancakes and sauces"),
                    lede=f"Shakes, pies, pancakes and sauces made with the state fruit: {plural(n, 'Idaho place')} where a 2025–26 menu or a recent local news story names huckleberry, each one read by hand in {CHECKED}. Some serve it only in season.")
    if k == "trout":
        about = f"""<h2>Idaho trout, briefly</h2>
    <p>Idaho raises more farmed trout than any other state, most of it in the Magic Valley, where spring water from the Snake River Plain aquifer pours out of the canyon walls near Hagerman and Buhl. Rainbow trout from those farms, often sold as Idaho ruby red trout, is on menus across the state, along with smoked trout and, near Hagerman, farmed sturgeon.</p>
    <h2>What the trout menus name</h2>
    {dishes_p}
    {by_town}
    <p>{HOW_BUILT}</p>
    <p>{IN_APP}</p>"""
        qas = [("Where does Idaho's trout come from?", "Mostly from fish farms along the Snake River in the Magic Valley, fed by springs from the Snake River Plain aquifer. Where a place says where its trout comes from, the note under it says so."),
               ("What is Idaho ruby red trout?", "A rainbow trout raised in Idaho whose flesh is red, like salmon's. Menus here list it by that name."),
               ("Is the trout on the list wild?", "We don't assume. Most restaurant trout in Idaho is farmed; the menus and notes say what each place serves.")]
        return dict(kicker="Idaho trout", what="Idaho rainbow trout, smoked trout and ruby red trout", about=about, qas=qas, qa_title="Trout questions",
                    titles=[f"Where to Eat Idaho Trout: {n} Restaurants and Lodges", f"Idaho Trout on the Menu: {n} Restaurants & Lodges",
                            f"Rainbow & Ruby Red Trout in Idaho: {n} Places | {BRAND}"] + std_titles(g, n),
                    descs=std_descs(g, ps, "Idaho rainbow trout, smoked trout and ruby red trout"),
                    lede=f"Rainbow, smoked and ruby red trout: {plural(n, 'Idaho restaurant')} and lodges with trout on a 2025–26 menu or in a recent local news story, each one read by hand in {CHECKED}.")
    if k == "taquerias":
        about = f"""<h2>Idaho taquerías</h2>
    <p>This list sticks to taquerías you can find twice: a shop, or a truck parked at a fixed address. A truck that moves from spot to spot isn't here, because we check each place's street address against its menu or a news story.</p>
    <h2>The taquerías, by the numbers</h2>
    {dishes_p}
    {by_town}
    <p>{HOW_BUILT}</p>
    <p>{IN_APP}</p>"""
        qas = [("Are taco trucks on the list?", "Only trucks parked at a fixed address, as the truck's own site or local news says. A truck that moves around isn't."),
               ("What's on the menu?", f"What the menus name: {e(dish_line(ps, 8)) or 'see each place below'}.")]
        return dict(kicker="Taquerías", what="tacos, tortas and taquerías with a fixed address", about=about, qas=qas, qa_title="Taquería questions",
                    titles=[f"Idaho Taquerías: {n} Taco Shops With a Street Address", f"Tacos in Idaho: {n} Taquerías That Stay Put | {BRAND}"] + std_titles(g, n),
                    descs=std_descs(g, ps, "tacos, tortas and taquerías with a fixed address"),
                    lede=f"Tacos and tortas from kitchens that stay put: {plural(n, 'Idaho taquería')}, shops and parked trucks with a street address, every one read against its own 2025–26 menu or a recent local news story in {CHECKED}.")
    if k == "historic":
        dated = sorted([p for p in ps if p.founded], key=lambda p: p.founded)
        oldest = f" The oldest with a documented year at this address: {e(dated[0].name)} in {e(dated[0].city)}, {dated[0].founded}." if dated else ""
        about = f"""<h2>Old saloons and supper clubs</h2>
    <p>Mining camps, railroad towns and ranch country left Idaho with bars and dining rooms that have been pouring for generations. This list is old saloons, bars and supper clubs that are still serving, with what their history rests on.</p>
    <h2>How old, and where</h2>
    <p>{n_word(len(dated), n)} of the {n:,} {"has" if len(dated) == 1 else "have"} a documented founding year at this address.{oldest}</p>
    {by_town}
    <p>{HOW_BUILT}</p>
    <p>{IN_APP}</p>"""
        qas = [("What makes a saloon historic here?", "A long run that the place itself or a published source documents: a founding date, a building's history, a local honor. The note under each place says what we found, and a founding year is shown only when it's documented at this address."),
               ("Do these places serve food?", "Each is on the list because it serves food as well as drinks, as its 2025 or 2026 menu or local news shows. Kitchens in small towns keep short or seasonal hours, so check before you go.")]
        return dict(kicker="Historic saloons", what="old saloons, bars and supper clubs still serving", about=about, qas=qas, qa_title="Saloon questions",
                    titles=[f"Old Idaho Saloons & Supper Clubs Still Serving: {n}", f"Idaho's Old Saloons and Supper Clubs, {n} Places | {BRAND}",
                            f"Historic Saloons in Idaho: {n} Still Serving | {BRAND}"] + std_titles(g, n),
                    descs=std_descs(g, ps, "old saloons, bars and supper clubs still serving food"),
                    lede=f"Saloons, bars and supper clubs with decades behind them: {plural(n, 'Idaho place')} still serving food, each read against its own site or a recent local news story in {CHECKED}, with what its history rests on.")
    raise KeyError(k)


def n_word(k, n):
    return cap1(words_num(k)) if k < 10 else f"{k:,}"


def dish_n(ps, word):
    return sum(1 for p in ps if any(word in d.lower() for d in p.dish_list))


for g in PAGED:
    c = guide_copy(g)
    guide_page(g["path"], cap1(g["name"]), f"{BRAND} guide · {c['kicker']} · checked {CHECKED}", c["titles"], c["descs"], e(c["lede"]),
               c["about"], g["places"], g["noun"], g["nouns"], cap1(g["name"]), qas=c["qas"], qa_title=c["qa_title"])

# ---------------------------------------------------------------- James Beard honors
JB_N = Counter(p.jb_label() for p in HON_L)
if HON_PAGE:
    jb_parts = [f"{plural(JB_N[k], k.replace('James Beard ', ''), None)}" for k in
                ("America's Classic", "James Beard winner", "James Beard nominee", "James Beard semifinalist", "James Beard (restaurateur)") if JB_N.get(k)]
    jb_line = join_words([x.replace("winner", "winner").replace("(restaurateur)", "restaurateur honor") for x in jb_parts])
    guide_page(HON_PATH, "Idaho James Beard Award restaurants", f"{BRAND} guide · honors as of {CHECKED}",
               [f"James Beard Honors in Idaho: {len(HON_L)} Restaurants and Bars", f"Idaho Restaurants With a James Beard Honor ({len(HON_L)})",
                f"James Beard Award Restaurants in Idaho | {BRAND}"],
               [f"Which Idaho kitchens the James Beard Foundation named from 2023 to 2026: {plural(len(HON_L), 'restaurant')} and bars, from America's Classics to semifinalists, by town.",
                f"{plural(len(HON_L), 'Idaho restaurant')} and bars named by the James Beard Foundation in 2023–26, from America's Classics to semifinalists, listed by region and town.",
                f"{plural(len(HON_L), 'Idaho restaurant')} with a 2023–2026 James Beard Foundation honor: winners, nominees, semifinalists and America's Classics, by region and town."],
               f"James Beard Foundation honors from 2023 to 2026 at {plural(len(HON_L), 'Idaho restaurant')} and bars still serving: {e(jb_line)}. Each listing leads with its highest honor, with the rest beneath it.",
               f"""<h2>Honors, not ratings</h2>
    <p>Everything on this page comes from the James Beard Foundation's own announcements, matched by hand to each restaurant. The Foundation's restaurant and chef awards narrow in stages: a long semifinalist list each winter, then nominees (what the Foundation calls its finalists), then a single winner per category. America's Classics is a separate honor for long-running, locally owned restaurants with timeless appeal. We call a semifinalist a semifinalist and a nominee a nominee; only a winner is called a winner. For the Best Chef award, Idaho competes in the Mountain region alongside Colorado, Montana, Utah and Wyoming.</p>
    <p>Idaho has no MICHELIN Guide, so no MICHELIN stars or recommendations appear here. Reader polls, "best of" roundups and review-site stars stay off this page, and a restaurant that closed after its honor is dropped.</p>
    <p class="fine">James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation. {BRAND} is not affiliated with the Foundation.</p>""",
               HON_L, "honored restaurant", "honored restaurants", "Idaho James Beard Award restaurants", honors=True)

# ---------------------------------------------------------------- oldest
if OLD_PAGE:
    old_pre1950 = sum(1 for p in OLD_L if p.founded < 1950)
    old_checked = f" Each was checked by hand in {CHECKED} against a 2025–26 source." if OLD_ALL_HC else ""
    old_early = [p for p in OLD_L if p.founded < 1950]
    old_early_txt = join_words([f"{p.name} ({p.city}, {p.founded})" for p in old_early])
    old_lodges = [p for p in OLD_L[:3] if re.search(r"\b(Lodge|Hotel|Inn|Resort)\b", p.name)]
    old_lodge_txt = f" {join_words([e(p.name) for p in old_lodges])} {'is' if len(old_lodges) == 1 else 'are'} dated that way." if old_lodges else ""
    guide_page(OLD_PATH, "Idaho's oldest restaurants", f"{BRAND} guide · checked {CHECKED}" if OLD_ALL_HC else f"{BRAND} guide",
               ["Idaho's Oldest Restaurants, Cafés & Lodges, Year by Year", f"Idaho's Longest-Running Restaurants: {len(OLD_L)} Places, Dated",
                f"Oldest Restaurants in Idaho, Year by Year ({len(OLD_L)}) | {BRAND}", f"Oldest Restaurants in Idaho: {len(OLD_L)} Places | {BRAND}"],
               [f"Idaho's oldest restaurants, cafés and lodges, oldest first: {plural(len(OLD_L), 'place')} dated at the address they have today, with the source behind each year.",
                f"Idaho's oldest restaurants: {plural(len(OLD_L), 'place')} with a founding year documented at the same address, oldest first, with the source behind each year noted."],
               f"Idaho dining rooms we could put a year on at their own address, oldest first: {plural(len(OLD_L), 'restaurant')}, cafés and lodges. "
               + (f"{cap1(words_num(len(old_early)))} go back before 1950: {e(old_early_txt)}. " if old_early else "")
               + "A note under each one says where its year comes from.",
               f"""<h2>What the year means</h2>
    <p>The year beside each place is when it started serving at the address it has today, in much the form it has today, as the place itself or a published history tells it. A dining room that opened together with its lodge or hotel takes the lodge's year.{old_lodge_txt} A business that began somewhere else, or moved, gets only the year it reached this address, never its older start. When two sources give different years we take the later one, and when the only source is the place's own telling, the note says so.{old_checked} A place we couldn't date at its address isn't on this list, so an older one may be missing.</p>""",
               OLD_L, "place", "places", "Idaho's oldest restaurants", region=False, show_fn=True)

# ---------------------------------------------------------------- how to look up an inspection (the seven districts)
url = f"{DOMAIN}/{INS_PATH}"
nav, bc = crumbs([("Home", "/"), ("Idaho restaurant inspections", "/" + INS_PATH)])
rows = []
for d in DISTRICTS:
    look = (f'<a href="{e(d["lookup"])}" rel="noopener">Food inspection lookup</a>' if d["lookup"]
            else f'No online lookup. <a href="{e(d["site"])}" rel="noopener">District website</a>')
    rows.append(f'<tr><th scope="row">{e(d["district"])}<span class="fine"> · <a href="/regions/{d["slug"]}.html">{e(d["name"])}</a></span></th>'
                f'<td>{e(join_words(d["county_list"]))}</td><td class="lookup">{look}</td><td class="n">{N_DISTRICT.get(d["slug"], 0):,}</td></tr>')
no_online = [d for d in DISTRICTS if not d["lookup"]]
ins_qas = [
    ("Does Idaho grade restaurants?", "No. Idaho's public health districts record what an inspector found, but none issues a letter, number, placard or score, and none publishes results in bulk. To see a place's inspections, use its district's own lookup above, or ask the district."),
    ("Why doesn't Idaho Eats show inspection results?", f"Because there is no bulk data to show fairly. The lookups are one search at a time, and the districts don't publish a statewide file, so {BRAND} lists no inspection results rather than a partial or guessed picture. Each place in the app and on this site links its own district's lookup."),
    ("Which district inspects a restaurant?", "The one for the county it's in: find the county in the table above. In the app and the web search, each place's details name its district and link the lookup."),
    ("How often are restaurants inspected?", "About once a year under the Idaho Food Code, the state's food safety rules, which follow the U.S. Food and Drug Administration's model Food Code. Districts also inspect after complaints and before a new place opens."),
]
if no_online:
    ins_qas.append((f"What about {no_online[0]['district']}?", f"{e(no_online[0]['district'])} ({e(join_words(no_online[0]['county_list']))} counties) has no online inspection lookup. Contact the district through <a href=\"{e(no_online[0]['site'])}\" rel=\"noopener\">its website</a> to ask about a place's inspections."))
ins_title = fit(["How to Look Up an Idaho Restaurant Inspection | Idaho Eats", "How to Look Up an Idaho Restaurant Inspection"], 50, 60, "inspections title")
ins_desc = fit([f"Idaho's {words_num(len(DISTRICTS))} public health districts inspect restaurants but publish no grades or bulk results. Each district, its counties and its own inspection lookup.",
                f"Idaho's public health districts inspect restaurants but publish no grades or bulk data. Find the district for a county and its own inspection lookup here."], 140, 160, "inspections description")
body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · health inspections</p>
    <h1>How to look up an Idaho restaurant inspection</h1>
    <p class="lede">Idaho's {words_num(len(DISTRICTS))} public health districts license and inspect restaurants, about once a year, under the Idaho Food Code. None publishes inspection results in bulk, and none issues a grade, placard or score, so {BRAND} shows no inspection results. Here is each district, the counties it covers and its own lookup.</p>
  </section>
  <section id="districts">
    <h2>The {words_num(len(DISTRICTS))} districts</h2>
    <p class="sub">The last column counts the restaurants, cafés, bars and bakeries on our list in each district's counties.</p>
    <div class="tbl" role="region" aria-labelledby="h-dt" tabindex="0"><table><caption class="vh" id="h-dt">Idaho public health districts, their counties and inspection lookups</caption><thead><tr><th scope="col">District</th><th scope="col">Counties</th><th scope="col">Inspections</th><th scope="col" class="n">Places on our list</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
    <p class="fine">Each lookup link was checked on October 8, 2026. The districts run their own sites; {BRAND} isn't affiliated with any of them.</p>
  </section>
{qa_html("Inspection questions", ins_qas)}
  <section id="more">
    <h2>Restaurants by region</h2>
    <p class="sub">The regions on this site follow the same district lines.</p>
    {region_links()}
    <p class="fine">{other_guides("/" + INS_PATH)}</p>
  </section>
  </main>"""
page(INS_PATH, ins_title, ins_desc, body, [article_ld(url, "How to look up an Idaho restaurant inspection", ins_desc), bc])

# ---------------------------------------------------------------- city pages
SEC_WORDS = {   # section id: (title long, title short, h1 phrase, desc phrase builder)
    "basque": ("Basque Food", "Basque", "Basque food", lambda n: plural(n, "hand-checked Basque spot")),
    "finger-steaks": ("Finger Steaks & Drive-Ins", "Finger Steaks", "finger steaks & drive-ins", lambda n: plural(n, "finger steak or drive-in spot", "finger steak and drive-in spots")),
    "spuds": ("Spud Plates", "Spuds", "spud plates", lambda n: plural(n, "spud plate spot")),
    "huckleberry": ("Huckleberry", "Huckleberry", "huckleberry", lambda n: plural(n, "place") + " for huckleberry"),
    "trout": ("Idaho Trout", "Trout", "Idaho trout", lambda n: plural(n, "place") + " for Idaho trout"),
    "taquerias": ("Taquerías", "Tacos", "taquerías", lambda n: plural(n, "hand-checked taquería")),
    "historic": ("Historic Saloons", "Saloons", "historic saloons", lambda n: plural(n, "historic saloon or supper club", "historic saloons and supper clubs")),
    "honors": ("James Beard Honorees", "James Beard", "James Beard honorees", lambda n: plural(n, "James Beard honoree")),
    "oldest": ("Oldest Restaurants", "Oldest Places", "oldest places", None),
}


def area_info(members, town=None):
    """The sections an area page actually has (in the guides' order), each with its places."""
    secs = []
    for g in GUIDES:
        ps = [p for p in g["places"] if p in members]
        if ps:
            secs.append((g["sec"], g, ps))
    hon = [p for p in HON_L if p in members]
    if hon:
        secs.append(("honors", None, hon))
    old = [p for p in OLD_L if p in members][:10]
    if old:
        secs.append(("oldest", None, old))
    return secs


def sec_desc_phrase(sid, ps):
    f = SEC_WORDS[sid][3]
    return f(len(ps)) if f else f"the oldest restaurants (back to {ps[0].founded})"


def tjoin(xs):
    if len(xs) == 1:
        return xs[0]
    conj = " and " if any("&" in x for x in xs) else " & "
    return ", ".join(xs[:-1]) + conj + xs[-1]


def area_title(c, secs, st="ID", state="Idaho"):
    cands = []
    rank = {"basque": 1, "finger-steaks": 2, "spuds": 3, "huckleberry": 4, "trout": 5, "historic": 6, "taquerias": 7, "honors": 3.5, "oldest": 8}
    secs = sorted(secs, key=lambda s: rank[s[0]])
    for k in range(len(secs), 0, -1):
        for col in (0, 1):
            J = tjoin([SEC_WORDS[s[0]][col] for s in secs[:k]])
            forms = [f"{c} {J} | {BRAND}", f"{c}, {st} {J} | {BRAND}", f"{c}, {state} {J}", f"{c}, {st} {J}", f"{c} {J}"]
            if "Restaurant" not in J:
                forms += [f"{c} {J} & Restaurants", f"{c} Restaurants: {J}", f"{c}, {st} Restaurants: {J}", f"{c} Restaurants: {J} | {BRAND}",
                          f"{c}, {state} Restaurants: {J}", f"{c} {J} & Restaurants | {BRAND}", f"{c}, {state} {J} & Restaurants",
                          f"{c}, {st} {J} & Restaurants | {BRAND}", f"{c}, {state} {J} & Restaurants | {BRAND}",
                          f"{c}, {state} {J} & More Restaurants | {BRAND}", f"{c}, {state}: {J}, Cafés & Bars | {BRAND}"]
            cands += forms
    cands += [f"{c}, {state} Restaurants, Cafés & Bars | {BRAND}", f"{c} Restaurants, Cafés & Bars | {BRAND}", f"{c}, {st} Restaurants, Cafés & Bars | {BRAND}",
              f"{c}, {state} Restaurants, Cafés and Bars", f"{c} Restaurants: What {c} Eats | {BRAND}", f"Restaurants in {c}, {state} | {BRAND}",
              f"{c} Restaurants, Cafés, Bars & Bakeries", f"{c}, {state}: Restaurants, Cafés & Bars", f"{c} Restaurants: Cafés, Bars & Bakeries"]
    return fit(cands, 50, 60, c + " title")


def area_desc(c, n_town, secs, suburb_lead, top):
    leads = [suburb_lead, f"{c}, Idaho", f"{c}, ID"]
    tails = [f". Search {n_town:,} {c} restaurants, cafés and bars", f". Search {n_town:,} local places to eat",
             f", plus {n_town:,} local places to eat on a searchable map", f", plus {n_town:,} more local places to eat",
             f", plus what {c} eats, by kind of restaurant", f". Most common kind of place here: {top}" if top else "", ""]
    ex1 = [x for x in ((f" Hand-checked in {CHECKED}." if any(s[0] not in ("honors", "oldest") for s in secs) else ""),
                       " Free iPhone app coming soon.", " Free, no ads, no ratings.") if x]
    extras = [""] + ex1 + [a + b for i, a in enumerate(ex1) for b in ex1[i + 1:]]

    def gen():
        for k in range(len(secs), 0, -1):
            J = join_words([sec_desc_phrase(s[0], s[2]) for s in secs[:k]])
            for lead in leads:
                for tail in tails:
                    for x in extras:
                        yield f"{lead}: {J}{tail}.{x}"
        for tail in tails:   # a town with none of the lists' places: what it eats
            for x in extras + [" Free Idaho restaurant guide for iPhone and iPad, coming soon.", " A free Idaho restaurant guide, no ads and no ratings.",
                               " From open map data, with no ratings and no ads.", " Free Idaho restaurant guide, coming soon to iPhone and iPad. No ads, no ratings."]:
                yield f"Restaurants in {c}, Idaho: the kinds of places {c} eats at most{tail}.{x}"
                yield f"Where to eat in {c}, Idaho: the kinds of restaurants, cafés and bars {c} has most{tail}.{x}"
    return fit(list(dict.fromkeys(s.replace("..", ".") for s in gen())), 140, 160, c + " description")


def section_html(sid, g, ps, anchors, where_c, statewide_note, dist=lambda p: None):
    items = "".join(place_item(p, anchors, extra=dist(p), show_fn=(sid == "oldest"), honors=(sid == "honors")) for p in ps)
    if g:
        link = f' The whole state: <a href="/{g["path"]}">{plural(len(g["places"]), g["noun"], g["nouns"])} in Idaho</a>.' if g["page"] else ""
        return (f'<section id="{sid}"><h2>{e(cap1(SEC_WORDS[sid][2]))} {where_c}</h2><p class="sub">{statewide_note}. Each one was read against a '
                f'2025–26 menu or news story in {CHECKED}.{link}</p><ol class="places">{items}</ol></section>')
    if sid == "honors":
        link = f' The whole state: <a href="/{HON_PATH}">{plural(len(HON_L), "Idaho James Beard honoree")}</a>.' if HON_PAGE else ""
        return (f'<section id="honors"><h2>James Beard honorees {where_c}</h2><p class="sub">Honors the James Beard Foundation gave from 2023 to 2026, '
                f'from semifinalist up to winner and America\'s Classic. They\'re facts, not ratings.{link}</p><ol class="places">{items}</ol></section>')
    link = f' The whole state: <a href="/{OLD_PATH}">Idaho\'s oldest restaurants</a>.' if OLD_PAGE else ""
    return (f'<section id="oldest"><h2>Oldest restaurants {where_c}</h2><p class="sub">Oldest first, each dated at the address it has now from its own '
            f'account or a published history; the note under each one names the source.{link}</p><ol class="places">{items}</ol></section>')


def cuisine_table(town_places, label, n):
    cuis = Counter(p.cuisine for p in town_places if p.cuisine and p.cuisine not in ("Other", "American & Other")).most_common(10)
    if not cuis:
        return ""
    rows = "".join(f'<tr><td>{e(k)}</td><td class="n">{v:,}</td></tr>' for k, v in cuis)
    return (f'<section id="cuisines"><h2>What {e(label)} eats</h2><p class="sub">The most common kinds among {e(label)}\'s {n:,} places to eat, '
            f'counted from open map data.</p><table><thead><tr><th scope="col">Kind of place</th><th scope="col" class="n">Places</th></tr></thead><tbody>{rows}</tbody></table></section>')


city_stats = {}
for c in CITY_PAGES:
    members = [p for p in PAGE_PLACES if p.home == c]
    secs = area_info(members)
    listed = list(dict.fromkeys(p for _, _, ps in secs for p in ps))
    n_town = N_TOWN[c]
    town_places = [p for p in REST if p.city == c]
    path = f"cities/{slug(c)}.html"
    url = DOMAIN + "/" + path
    anchors = Anchors(url)
    title = area_title(c, secs)
    outside = any(p.city != c for p in listed)
    top = Counter(p.cuisine for p in town_places if p.cuisine and p.cuisine not in ("Other", "American & Other")).most_common(1)
    desc = area_desc(c, n_town, secs, f"In and near {c}, Idaho" if outside else f"In {c}, Idaho", top[0][0].lower() if top else "")
    k = 3
    while k > 1 and len(join_words([SEC_WORDS[s[0]][2] for s in secs[:k]])) > 48:   # a heading, not the whole table of contents
        k -= 1
    h1_bits = [SEC_WORDS[s[0]][2] for s in secs[:k]]
    h1 = f"{c} restaurants" + ((": " + ", ".join(h1_bits) + " and more") if len(secs) > k else (": " + join_words(h1_bits)) if secs else "")
    nav, bc = crumbs([("Home", "/"), ("Cities", "/cities/"), (c, "/" + path)])
    area = f"In and around {c}" if outside else f"In {c}"
    counts = [sec_desc_phrase(s[0], s[2]) for s in secs]
    notes = []
    if any(s[1] for s in secs):
        notes.append(f"The Idaho lists were checked by hand in {CHECKED} against 2025–26 sources.")
    lede = ((f"{area}: {e(join_words(counts))}. " if counts else f"Our hand-checked guides haven't reached {e(c)} yet; that research is still under way. ")
            + " ".join(notes) + (" " if notes else "") + f"The {BRAND} app and the web search include {n_town:,} restaurants, cafés, bars and bakeries in {e(c)}, closest first once you share your location.")
    reg = DISTRICT_OF.get(Counter(p.county for p in town_places if p.county).most_common(1)[0][0]) if town_places else None

    def dist(p, c=c):
        return None if p.city == c else f"{p.home_miles:.0f} mi from {c}"

    parts = [f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · {e(c)}, Idaho</p>
    <h1>{e(h1)}</h1>
    <p class="lede">{lede}</p>
    {cta()}
    <p class="fine">A place outside {e(c)} is listed here only when {e(c)} is the closest of our {words_num(len(CITY_PAGES)) if len(CITY_PAGES) < 10 else len(CITY_PAGES)} city pages and it's within {RADIUS} miles, so each place is on one city page.{f' {e(c)} is in the <a href="/regions/{reg["slug"]}.html">{e(reg["name"])}</a> region, where {e(reg["district"])} inspects restaurants.' if reg else ""}</p>
  </section>"""]
    for sid, g, ps in secs:
        where_c = ("in and near " if any(p.city != c for p in ps) else "in ") + e(c)
        note = (f"Places in {e(c)} first, then others closest to {e(c)}" if any(p.city != c for p in ps) else f"Places in {e(c)}")
        parts.append(section_html(sid, g, ps if sid in ("honors", "oldest") else sorted(ps, key=lambda p: (p.city != c, p.home_miles, p.name.lower())),
                                  anchors, where_c, note, dist))
    parts.append(cuisine_table(town_places, c, n_town))
    parts.append(f'<section id="more"><h2>More Idaho cities and towns</h2>{city_links(current=c)}<p class="fine plinks"><a href="/cities/">Cities and regions</a></p></section>\n  </main>')
    lds = [article_ld(url, h1, desc), bc]
    if listed:
        lds.append(item_list(f"{c}: " + join_words([SEC_WORDS[s[0]][2] for s in secs]), listed, url, anchors))
    thin = len(listed) < 5   # a near-empty page stays out of search until it has real content
    page(path, title, desc, "\n".join(parts), lds, robots="noindex,follow" if thin else "index,follow,max-image-preview:large")
    city_stats[c] = {"restaurants": n_town, "listed": len(listed), "picks": sum(1 for p in listed if p.tags & GUIDE_BITS and p.hc),
                     "james_beard": sum(1 for p in listed if p.jbf), "sections": [s[0] for s in secs], "indexed": not thin}

# ---------------------------------------------------------------- region pages (the seven public health districts)
region_stats = {}
for d in DISTRICTS:
    members = [p for p in PAGE_PLACES if p.district is d]
    secs = area_info(members)
    listed = list(dict.fromkeys(p for _, _, ps in secs for p in ps))
    rest_here = [p for p in REST if p.district is d]
    n_here = len(rest_here)
    towns = Counter(p.city for p in rest_here if p.city)
    path = f"regions/{d['slug']}.html"
    url = DOMAIN + "/" + path
    anchors = Anchors(url)
    name = d["name"]
    county_words = join_words(d["county_list"]) + (" counties" if len(d["county_list"]) > 1 else " County")
    picks_n = sum(1 for p in listed if p.hc and p.tags & GUIDE_BITS)
    sec_names = [SEC_WORDS[s[0]][2] for s in secs]
    by_size = sorted(secs, key=lambda s: -len(s[2]))   # the region's biggest lists lead its title
    title = fit(([f"{name} Restaurants: {tjoin([SEC_WORDS[s[0]][1] for s in by_size[:k]])} | {BRAND}" for k in range(len(secs), 0, -1)]
                 + [f"{name} Restaurants: {tjoin([SEC_WORDS[s[0]][1] for s in by_size[:k]])}" for k in range(len(secs), 0, -1)]
                 + [f"{name}: {tjoin([SEC_WORDS[s[0]][1] for s in by_size[:k]])} & More | {BRAND}" for k in range(len(secs), 0, -1)])
                + [f"{name} Restaurants & Health District | {BRAND}", f"{name} Restaurants and Inspections Lookup | {BRAND}",
                   f"{name}, Idaho Restaurants & Inspection Lookup", f"{name} Restaurants: Picks & Inspection Lookup",
                   f"{name} Restaurants, Cafés & Bars | {BRAND}", f"{name} Restaurants by Town | {BRAND}"], 50, 60, path + " title")
    where_r = name if "Idaho" in name else f"{name}, Idaho"

    def region_descs():
        whats = [join_words([sec_desc_phrase(s[0], s[2]) for s in secs[:k]]) for k in range(min(len(secs), 3), 0, -1)]
        tails = [f", plus {n_here:,} places to eat by town and the {d['district']} inspection lookup.",
                 f" ({county_words}), plus {n_here:,} places to eat and where to look up an inspection.",
                 f", plus {n_here:,} places to eat by town and where to look up an inspection.", f", plus {n_here:,} more places to eat by town."]
        extras = ["", " Free, no ratings.", f" Hand-checked in {CHECKED}.", " Free app coming soon.", " Free, no ads, no ratings."]
        for w in whats:
            for t in tails:
                for x in extras:
                    yield f"{cap1(w)} in {where_r}{t}{x}"
        for x in extras + [" A free guide, no ratings.", f" From {d['district']}'s counties.", " Free iPhone app coming soon, no ads, no ratings."]:
            yield f"{n_here:,} restaurants, cafés and bars in {where_r} ({county_words}), by town, with where to look up an inspection.{x}"
            yield f"{n_here:,} restaurants, cafés and bars in {where_r}, by town, and how to look up an inspection with {d['district']}.{x}"
            yield f"Restaurants in {where_r}: {n_here:,} places to eat by town, our hand-checked picks, and how to look up a restaurant inspection here.{x}"
            yield f"Where to eat in {where_r}: {n_here:,} restaurants, cafés and bars by town, plus how to look up a restaurant inspection in the region.{x}"
    desc = fit(list(dict.fromkeys(region_descs())), 140, 160, path + " description")
    h1 = f"{name} restaurants"
    nav, bc = crumbs([("Home", "/"), ("Cities and regions", "/cities/"), (name, "/" + path)])
    cities_here = [c for c in CITY_PAGES if any(p.city == c for p in rest_here)]
    lede = (f"On this site, {e(name)} is {e(county_words)}: the counties {e(d['district'])} looks after. They hold {plural(n_here, 'restaurant')}, cafés, bars and bakeries "
            f"across {plural(len(towns), 'town')}" + (f", including {e(join_words([sec_desc_phrase(s[0], s[2]) for s in secs]))} from our hand-checked lists." if secs else
                                                       ". Our hand-checked guides haven't reached this region yet; that research is still under way."))
    look = (f'<p class="lookup"><a href="{e(d["lookup"])}" rel="noopener">{e(d["district"])}: food inspection lookup</a></p>' if d["lookup"]
            else f'<p>{e(d["district"])} has no online inspection lookup. Contact it through <a href="{e(d["site"])}" rel="noopener">its website</a>.</p>')
    parts = [f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · region</p>
    <h1>{e(h1)}</h1>
    <p class="lede">{lede}</p>
    {cta()}
  </section>"""]
    for sid, g, ps in secs:
        parts.append(section_html(sid, g, ps if sid in ("honors", "oldest") else sorted(ps, key=lambda p: (p.city, p.name.lower())), anchors,
                                  "in " + e(name), "By town"))
    trows = "".join(f'<tr><td>{f"<a href={chr(34)}{city_url(t)}{chr(34)}>{e(t)}</a>" if t in CITY_PAGES else e(t)}</td><td class="n">{n:,}</td></tr>'
                    for t, n in towns.most_common(12))
    parts.append(f'<section id="towns"><h2>Towns in {e(name)}</h2><p class="sub">Where {e(name)}\'s places to eat cluster, counted from open map data.'
                 f'{" Town pages: " + ", ".join(f"<a href={chr(34)}{city_url(c)}{chr(34)}>{e(c)}</a>" for c in cities_here) + "." if cities_here else ""}</p>'
                 f'<table><thead><tr><th scope="col">Town</th><th scope="col" class="n">Places to eat</th></tr></thead><tbody>{trows}</tbody></table></section>')
    parts.append(f'<section id="inspections"><h2>Health inspections in {e(name)}</h2><p>{e(d["district"])} licenses and inspects restaurants in '
                 f'{e(county_words)}, about once a year. Like Idaho\'s other districts, it publishes no inspection results in bulk and issues no grade, '
                 f'placard or score, so {BRAND} shows none.</p>{look}<p class="fine plinks"><a href="/{INS_PATH}">How to look up an Idaho restaurant inspection</a></p></section>')
    parts.append(f'<section id="more"><h2>Other regions</h2>{region_links(current=d["slug"])}</section>\n  </main>')
    lds = [article_ld(url, h1, desc), bc]
    if listed:
        lds.append(item_list(f"{name}: " + join_words(sec_names), listed, url, anchors))
    thin = len(listed) < 5
    page(path, title, desc, "\n".join(parts), lds, robots="noindex,follow" if thin else "index,follow,max-image-preview:large")
    region_stats[d["slug"]] = {"restaurants": n_here, "listed": len(listed), "picks": picks_n, "indexed": not thin}

# ---------------------------------------------------------------- cities hub
url = f"{DOMAIN}/cities/"
nav, bc = crumbs([("Home", "/"), ("Cities and regions", "/cities/")])
crow = "".join(f'<tr><td><a href="{city_url(c)}">{e(c)}</a></td><td class="n">{s["picks"]:,}</td><td class="n">{s["james_beard"]:,}</td><td class="n">{s["restaurants"]:,}</td></tr>'
               for c, s in city_stats.items())
rrow = "".join(f'<tr><td><a href="/regions/{d["slug"]}.html">{e(d["name"])}</a></td><td>{e(d["district"])}</td><td class="n">{region_stats[d["slug"]]["picks"]:,}</td><td class="n">{region_stats[d["slug"]]["restaurants"]:,}</td></tr>'
               for d in DISTRICTS)
first, last = CITY_PAGES[:2], CITY_PAGES[-2:]
title = fit([f"Idaho Cities & Regions: Restaurant Guides | {BRAND}", f"Idaho Restaurant Guides by City and Region | {BRAND}"], 50, 60, "cities title")
desc = fit([f"Restaurant guides for {len(CITY_PAGES)} Idaho cities and towns, from {join_words(first)} to {join_words(last)}, and {words_num(len(DISTRICTS))} regions, with hand-checked picks{x}"
            for x in (".", " and honors.", ", honors and more.")]
           + [f"Restaurant guides for {len(CITY_PAGES)} Idaho cities and {words_num(len(DISTRICTS))} regions, with hand-checked Basque, finger steak and spud picks, by town{x}"
              for x in (".", ". Free, no ads, no ratings.", ", plus James Beard honorees.", ", plus the oldest places.")], 140, 160, "cities description")
body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · cities and regions</p>
    <h1>Idaho cities and regions</h1>
    <p class="lede">A page for each of {len(CITY_PAGES)} of Idaho's biggest towns and for each of its {words_num(len(DISTRICTS))} public health district regions, with the hand-checked picks, James Beard honorees and oldest places that are actually there. Each place near a city is on the page of the closest one.</p>
  </section>
  <section id="cities">
    <h2>City pages</h2>
    <div class="tbl" role="region" aria-labelledby="h-ct" tabindex="0"><table><caption class="vh" id="h-ct">Idaho city pages</caption><thead><tr><th scope="col">City</th><th scope="col" class="n">Hand-checked picks</th><th scope="col" class="n">James Beard</th><th scope="col" class="n">Places to eat</th></tr></thead><tbody>{crow}</tbody></table></div>
  </section>
  <section id="regions">
    <h2>Region pages</h2>
    <div class="tbl" role="region" aria-labelledby="h-rt" tabindex="0"><table><caption class="vh" id="h-rt">Idaho region pages</caption><thead><tr><th scope="col">Region</th><th scope="col">Health district</th><th scope="col" class="n">Hand-checked picks</th><th scope="col" class="n">Places to eat</th></tr></thead><tbody>{rrow}</tbody></table></div>
    <p class="fine">Regions follow the public health districts' county lines; each region page says which counties. <a href="/{INS_PATH}">How to look up an Idaho restaurant inspection</a>.</p>
  </section>
  </main>"""
page("cities/index.html", title, desc, body, [bc], og_type="website")


# ---------------------------------------------------------------- one page per hand-checked or honored place
def kind_labels(p):
    out = []
    jb = {"America's Classic": "James Beard America's Classic", "James Beard winner": "James Beard Award Winner", "James Beard nominee": "James Beard Nominee",
          "James Beard semifinalist": "James Beard Semifinalist", "James Beard (restaurateur)": "James Beard Honoree"}.get(p.jb_label())
    lab = {"basque": ["Basque Restaurant", "Basque Food", "Basque"], "fingersteak": ["Finger Steaks", "Finger Steaks & Fry Sauce"],
           "drivein": ["Idaho Drive-In", "Drive-In"], "spud": ["Idaho Spud Plates", "Spud Plates"], "huckleberry": ["Huckleberry", "Idaho Huckleberry"],
           "trout": ["Idaho Trout", "Trout"], "taqueria": ["Taquería", "Tacos"], "historic": ["Historic Saloon", "Historic Idaho Saloon"]}
    if jb:
        out.append(jb)
    for t in ("basque", "fingersteak", "drivein", "spud", "huckleberry", "trout", "taqueria", "historic"):
        if p.hc and p.tags & BIT[t]:
            out += lab[t]
    if p.founded:
        out += [f"Since {p.founded}", f"Open Since {p.founded}"]
    low = p.name.lower()
    keep = [k for k in out if k.lower() not in low]
    return keep or out or ["Idaho Restaurant"]


def place_title(p):
    city = p.city or "Idaho"
    locs = [f"{p.name}, {city}", f"{p.name}, {city}, ID", f"{p.name}, {city}, Idaho", f"{p.name} in {city}, Idaho"]
    sfxs = (f" | {BRAND}", "", " | ID Eats")
    labels = kind_labels(p)
    opts = [f"{loc}: {k}{sfx}" for loc in locs for k in labels for sfx in sfxs]
    opts += [f"{loc}: {a} & {b}{sfx}" for loc in locs for i, a in enumerate(labels) for b in labels[i + 1:] for sfx in sfxs]
    opts += [f"{loc}{sfx}" for loc in locs for sfx in sfxs] + [f"{p.name}: {k}{sfx}" for k in labels for sfx in sfxs]
    opts += [f"{loc}, Restaurant{sfx}" for loc in locs for sfx in sfxs] + [f"{p.name} | {BRAND}", f"{p.name[:44].rstrip()}… | {BRAND}"]
    good = [o for o in opts if 50 <= len(o) <= 60 and o not in TITLES]
    if not good:
        raise ValueError(f"no title fits for {p.name} ({p.city}): {[(len(o), o) for o in opts[:6]]}")
    return good[0]


def place_desc(p):
    city = p.city or "Idaho"
    links = join_words([x for x in ("address", "website" if p.site else "", "phone" if p.tel else "", "directions") if x])
    chk = f"Hand-checked in {CHECKED}" if p.hc else "Listed for its James Beard honor"
    tails = [f" {chk}, with {links}.", f" {chk} against a 2025–26 source.", f" {chk}.", "", f" {chk}, with {links} and nearby places."]
    opts = []
    if p.note:
        note = p.note.rstrip(".") + "."
        for t in tails:
            opts += [f"{p.name}, {city}: {note}{t}", f"{p.name} in {city}, Idaho: {note}{t}", f"{note}{t}"]
    facts = []
    if p.jb_label():
        facts.append({"America's Classic": "a James Beard America's Classic", "James Beard winner": "a James Beard Award winner",
                      "James Beard nominee": "a James Beard Award nominee", "James Beard semifinalist": "a James Beard Award semifinalist",
                      "James Beard (restaurateur)": "honored by the James Beard Foundation"}[p.jb_label()])
    gl = [g["noun"] for g in guides_of(p)]
    menu = f" serving {join_words(p.dish_list[:3])}" if p.dish_list else ""
    leads = [f"{p.name} in {city}, Idaho", f"{p.name} in {city}", f"{p.name}, {city}, Idaho"]
    bodies = []
    if facts:
        bodies.append(f"is {facts[0]}")
    if gl:
        bodies += [f"is a hand-checked {gl[0]}{menu}", f"is a hand-checked {gl[0]}"]
    if p.founded:
        bodies += [f"has been open at this address since {p.founded}"]
    bodies.append(f"is a {p.cuisine.lower()} place" if p.cuisine and p.cuisine not in ("American & Other", "Other") else "is an Idaho restaurant")
    for t in tails + [f" {chk}, with {links}, the district inspection lookup and nearby places.", f" See its {links}, and the hand-checked places nearby."]:
        for b in bodies:
            for lead in leads:
                opts.append(f"{lead} {b}.{t}")
    good = [o for o in opts if 140 <= len(o) <= 160 and o not in DESCS]
    if not good:
        raise ValueError(f"no description fits for {p.name} ({p.city}): {sorted({len(o) for o in opts})[:20]}")
    return good[0]


def apple_maps(p):
    return (f"https://maps.apple.com/?q={quote(p.name)}&ll={p.lat:.5f},{p.lon:.5f}" if p.lat is not None
            else f"https://maps.apple.com/?q={quote(p.name + ', ' + p.addr + ', ' + p.city + ', Idaho')}")


def directions(p):
    return f"https://maps.apple.com/?daddr={p.lat:.5f},{p.lon:.5f}&dirflg=d" if p.lat is not None else apple_maps(p)


for p in PAGE_PLACES:
    path = f"places/{p.slug}.html"
    url = DOMAIN + "/" + path
    gs = guides_of(p)
    parent = ((("/" + gs[0]["path"]), cap1(gs[0]["name"])) if gs and gs[0]["page"] else
              ("/" + HON_PATH, "Idaho James Beard Award restaurants") if p.jbf and HON_PAGE else
              ("/" + OLD_PATH, "Idaho's oldest restaurants") if p.founded and OLD_PAGE else
              (city_url(p.home), p.home) if p.home else
              (f"/regions/{p.district['slug']}.html", p.district["name"]) if p.district else ("/cities/", "Cities and regions"))
    nav, bc = crumbs([("Home", "/"), (parent[1], parent[0]), (p.name, "/" + path)])
    rows = []
    if p.dishes:
        rows.append(("On the menu", e(p.dishes)))
    if gs:
        rows.append(("On our lists", e(join_words([g["app"] for g in gs]))))
    if p.founded:
        rows.append(("Open here since", f"{p.founded}" + (f"<br><span class=\"fine\">{e(p.fn)}</span>" if p.fn else "")))
    if p.season:
        rows.append(("Season", e(p.season)))
    if p.jbf:
        rows.append(("Honors", "<ul>" + "".join(f"<li>{e('James Beard: ' + x)}</li>" for x in p.jbf.split("; ") if x) + "</ul>"))
    if p.cuisine and p.cuisine not in ("Other", "American & Other"):
        rows.append(("Kind of place", e(p.cuisine)))
    if p.chain:
        rows.append(("Locations in Idaho", f"{p.r.get('ch'):,}"))
    facts_html = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    addr = ", ".join(x for x in (p.addr, p.city) if x) + (f", ID {p.zip}" if p.zip else ", Idaho")
    acts = [f'<a class="btn" href="{e(apple_maps(p))}" rel="noopener">Hours &amp; photos in Apple Maps</a>',
            f'<a class="btn btn-ghost" href="{e(directions(p))}" rel="noopener">Directions</a>']
    if p.site:
        acts.append(f'<a class="btn btn-ghost" href="{e(p.site)}" rel="noopener nofollow">Website</a>')
    if p.tel:
        acts.append(f'<a class="btn btn-ghost" href="tel:{p.tel}">Call {e(phone_text(p.tel))}</a>')
    acts.append(f'<a class="btn btn-ghost" href="/explore/#p={e(p.id)}">Open in the web app</a>')
    near = sorted(((miles((p.lat, p.lon), (q.lat, q.lon)), q) for q in PAGE_PLACES if q is not p and q.lat is not None and p.lat is not None),
                  key=lambda x: (x[0], x[1].name.lower()))[:6]
    near_html = "".join(f'<li><a href="{place_url(q)}">{e(q.name)}</a><span>{e(q.city)} · {d:.1f} mi · '
                        f'{e(join_words([g["noun"] for g in guides_of(q)][:2]) or (q.jb_label() or "hand-checked").lower().replace("james beard", "James Beard").replace("america", "America"))}</span></li>'
                        for d, q in near)
    more = [f'<a href="/{g["path"]}#{p.slug}">{e(cap1(g["name"]))}</a>' for g in gs if g["page"]]
    if p.jbf and HON_PAGE:
        more.append(f'<a href="/{HON_PATH}#{p.slug}">Idaho James Beard honorees</a>')
    if p.home:
        more.append(f'<a href="{city_url(p.home)}">{e(p.home)} page</a>')
    if p.district:
        more.append(f'<a href="/regions/{p.district["slug"]}.html">{e(p.district["name"])} page</a>')
    d = p.district
    insp = ("" if not d else
            f'<p>{e(d["district"])} licenses and inspects restaurants in {e(p.county)} County. It publishes no inspection results in bulk and issues no grade, so there are none here. '
            + (f'<a href="{e(d["lookup"])}" rel="noopener">Look up {e(p.name)} in the district\'s food inspection search</a>.' if d["lookup"]
               else f'It has no online lookup; ask the district through <a href="{e(d["site"])}" rel="noopener">its website</a>.') + "</p>")
    checked_note = (f"Checked by hand in {CHECKED} against a 2025 or 2026 source: the place's own site or menu, or local news. Menus and seasons change, and resort-town places close between seasons, so check with {e(p.name)} before you go."
                    if p.hc else f"Listed for its James Beard honor, checked against the Foundation's announcements; not hand-checked yet, so check with {e(p.name)} before you go.")
    body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{e(kind_labels(p)[0])} · {e(p.city or "Idaho")}</p>
    <h1>{e(p.name)}</h1>
    {f'<p class="lede">{e(p.note)}</p>' if p.note else ""}
    <p class="addr">{e(addr)}</p>
    <div class="actions">{"".join(acts)}</div>
  </section>
  <section id="checked">
    <h2>What we checked</h2>
    <dl class="facts">{facts_html}</dl>
    <p class="fine">{checked_note} Hours, photos and ratings are Apple Maps' own, in its place card. Something wrong? <a href="mailto:{EMAIL}?subject={quote('Correction: ' + p.name + ', ' + p.city)}">Tell us</a>.</p>
  </section>
  <section id="inspections">
    <h2>Health inspections</h2>
    {insp}
    <p class="fine plinks"><a href="/{INS_PATH}">How to look up an Idaho restaurant inspection</a></p>
  </section>
  <section id="nearby">
    <h2>Nearby on our lists</h2>
    <ul class="near">{near_html}</ul>
    <p class="plinks">More: {" · ".join(more) if more else '<a href="/cities/">cities and regions</a>'}</p>
  </section>
  <section id="app" class="final">
    <h2>Save it for the trip</h2>
    <p class="sub">The free {BRAND} app has {e(p.name)} and {N_REST - 1:,} other Idaho places, sorted by distance from you, with Apple Maps' live hours and photos.</p>
    {cta()}
  </section>
  </main>"""
    ld = {"@context": "https://schema.org", "@id": url + "#place", **restaurant_ld(p, url), "mainEntityOfPage": url}
    page(path, place_title(p), place_desc(p), body, [ld, bc], og_alt=f"{BRAND}: {p.name}, {p.city or 'Idaho'}")

# ---------------------------------------------------------------- web app (docs/explore/): data split + page
os.makedirs(f"{DOCS}/data", exist_ok=True)
CORE_KEYS = ["id", "n", "c", "co", "cu", "t", "s", "a", "z", "la", "lo", "b", "ch", "v", "g", "hc", "ip", "f", "h", "j", "dish"]
cols = {k: [] for k in CORE_KEYS + ["jb"]}
detail = []
for r in D["places"]:
    for k in CORE_KEYS:
        v = r.get(k)
        cols[k].append(round(v, 4) if k in ("la", "lo") and v is not None else v)
    cols["jb"].append(1 if r.get("jbf") else None)
    dd = {k: r[k] for k in ("note", "dish", "seas", "fn", "jbf", "lic", "liq") if r.get(k)}
    if site_url(r.get("w")):
        dd["w"] = site_url(r.get("w"))
    if safe_tel(r.get("ph")):
        dd["ph"] = safe_tel(r.get("ph"))
    detail.append(dd or None)
core = {"generated": D["generated"], "checked": CHECKED, "overture_release": OVERTURE, "abc_licenses": ABC, "liquor_updated": LIQUOR_DATE,
        "cities": CITIES, "cuisines": CUISINES, "counties": COUNTIES, "brands": D["brands"], "srcs": D["srcs"], "tags": D["tags"],
        "calibration": D.get("calibration", {}), "inspections_page": INS_PATH,
        "districts": [{"name": d["district"], "url": d["lookup"], "site": d["site"], "counties": [c + " County" for c in d["county_list"]]} for d in DISTRICTS],
        "cols": cols}
json.dump(core, open(f"{DOCS}/data/core.json", "w"), separators=(",", ":"), ensure_ascii=False)
json.dump(detail, open(f"{DOCS}/data/detail.json", "w"), separators=(",", ":"), ensure_ascii=False)
json.dump(json.load(open(f"{ROOT}/data/app/id_shapes.json")), open(f"{DOCS}/data/id_shapes.json", "w"), separators=(",", ":"))
assert all(p.id in set(cols["id"]) for p in PAGE_PLACES), "every place page's #p= link must open in the web app"

EXPLORE_CSS = """
  [hidden] { display: none !important; }
  .ex-hero { padding: 22px 0 4px; }
  .ex-hero h1 { font-size: clamp(30px, 6vw, 44px); }
  .ex-hero .sub { margin-bottom: 12px; }
  .ex-controls { background: var(--bg); padding: 6px 0 8px; border-bottom: 1px solid var(--rule); }
  .ex-guides { display: flex; gap: 6px; overflow-x: auto; padding: 2px 0 8px; scrollbar-width: none; }
  @media (min-width: 601px) { .ex-guides { flex-wrap: wrap; overflow: visible; } }
  @media (max-width: 600px) { .ex-guides { padding-right: 32px; -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 32px), transparent); mask-image: linear-gradient(to right, #000 calc(100% - 32px), transparent); } }
  .ex-guides button, .ex-view button, .ex-small, .ex-linkbtn { flex: 0 0 auto; display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px;
    border: 1px solid var(--rule2); background: var(--surface); color: var(--huck); border-radius: 999px; padding: 0 14px; font: 600 15px/1.2 var(--text); cursor: pointer; }
  .ex-guides button[aria-pressed="true"], .ex-view button[aria-pressed="true"] { background: var(--huck); color: var(--on-dark); border-color: var(--huck); }
  .ex-guides button:disabled, .ex-small:disabled { cursor: default; }
  .ex-linkbtn { border-color: var(--huck); margin-left: 4px; }
  .ex-row1 { display: flex; gap: 8px; align-items: center; }
  .ex-row1 input[type=search] { flex: 1; min-width: 0; min-height: 44px; font: 16px/1.3 var(--text); padding: 10px 12px; border: 2px solid var(--huck); border-radius: 12px; background: var(--surface); color: var(--ink); }
  @media (max-width: 370px) { .ex-row1 { flex-wrap: wrap; } .ex-row1 input[type=search] { flex-basis: 100%; } }   /* the search hint was cut at 320 px: Near me goes under the box */
  .ex-row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; align-items: center; margin-top: 8px; }
  .ex-sel select { width: 100%; min-height: 44px; font: 16px/1.2 var(--text); padding: 6px 8px; border: 1px solid var(--rule2); border-radius: 10px; background: var(--surface); color: var(--ink); }
  .ex-check { display: inline-flex; align-items: center; gap: 8px; min-height: 44px; font-size: 16px; color: var(--ink); cursor: pointer; }
  .ex-check input { width: 20px; height: 20px; margin: 0; accent-color: var(--huck); }
  .ex-off { visibility: hidden; }
  .ex-view { display: flex; gap: 4px; justify-self: end; }
  @media (min-width: 700px) {
    .ex-row2 { display: flex; flex-wrap: wrap; }
    .ex-sel select { width: 13em; }
    .ex-view { margin-left: auto; }
  }
  #ex-sub { margin: 6px 0 0; font-size: 14px; line-height: 1.45; min-height: 1.45em; color: var(--ink2); }
  @media (max-width: 699px) { #ex-sub { min-height: 2.9em; } }
  #ex-count { margin: 4px 0 0; font-size: 14px; line-height: 1.45; min-height: 1.45em; color: var(--muted); }
  #ex-locmsg { font-size: 13px; color: var(--muted); margin: 4px 0 0; }
  #ex-locmsg:empty { display: none; }
  #ex-locmsg.ex-away { color: var(--ink2); }
  #ex-listwrap { min-height: 100vh; }
  #ex-loading { padding: 18px 4px; color: var(--ink2); margin: 0; }
  .ex-list { list-style: none; padding: 0; margin: 10px 0; }
  .ex-list li + li { border-top: 1px solid var(--rule); }
  .ex-row { width: 100%; min-height: 44px; display: flex; gap: 12px; align-items: center; text-align: left; background: none; border: 0; padding: 12px 4px; cursor: pointer; color: var(--ink); font: inherit; }
  .ex-row:hover { background: var(--surface2); }
  .ex-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
  .ex-main b { font-weight: 650; overflow-wrap: anywhere; }
  .ex-town { font-size: 14px; color: var(--muted); }
  .ex-chips .tag { margin: 0 4px 2px 0; }
  .tag-plain { background: var(--surface2); color: var(--huck); }
  .tag-dash { background: transparent; color: var(--muted); border: 1px dashed var(--muted); }
  .ex-metric { text-align: right; display: flex; flex-direction: column; }
  .ex-metric b { font: 800 22px/1 var(--display); color: var(--huck); }
  .ex-metric small { font-size: 12px; color: var(--muted); }
  .ex-rank { flex: 0 0 34px; height: 34px; display: grid; place-items: center; font: 800 20px/1 var(--display); color: var(--huck); border-radius: 8px; }
  .ex-rank.top { background: var(--russet); color: var(--on-russet); }
  .ex-empty { padding: 24px 4px; color: var(--muted); }
  .ex-few { padding-top: 14px; }
  .ex-widen { display: flex; width: fit-content; max-width: 100%; margin-top: 10px; padding: 8px 16px; text-align: left; text-wrap: balance; border-color: var(--huck); }   /* a guide search with few or no matches: the same search in All restaurants */
  #ex-more { display: flex; margin: 8px auto 24px; }
  #ex-mapwrap { position: relative; height: min(78vh, 760px); margin: 10px 0 20px; border: 1px solid var(--rule); border-radius: 16px; overflow: hidden; background: var(--mapbg); }
  #ex-map { width: 100%; height: 100%; display: block; touch-action: none; cursor: grab; }
  .ex-zoom { position: absolute; right: 10px; top: 10px; display: flex; flex-direction: column; gap: 6px; }
  .ex-zoom button { width: 44px; height: 44px; border-radius: 10px; border: 1px solid var(--rule2); background: var(--surface); color: var(--huck); font: 700 22px/1 var(--text); cursor: pointer; }
  #ex-maphint { position: absolute; left: 10px; bottom: 8px; margin: 0; font-size: 13px; background: var(--surface); padding: 3px 8px; border-radius: 999px; color: var(--ink2); }
  .ex-panel { position: fixed; z-index: 20; right: 0; top: 0; bottom: 0; width: min(440px, 100%); overflow-y: auto; background: var(--surface); border-left: 1px solid var(--rule); box-shadow: -8px 0 24px rgba(0,0,0,.12); padding: 14px 20px 40px; }
  .ex-scrim { position: fixed; inset: 0; z-index: 19; background: rgba(31,26,36,.28); }   /* behind the modal panel; a click on it closes the panel */
  @media (max-width: 600px) { .ex-panel { top: auto; height: 86vh; border-left: 0; border-top: 4px solid var(--russet); border-radius: 18px 18px 0 0; } }
  .ex-close { position: sticky; top: 0; float: right; width: 44px; height: 44px; border-radius: 50%; border: 1px solid var(--rule2); background: var(--surface); font: 400 26px/1 var(--text); cursor: pointer; color: var(--ink); }
  .ex-kicker { margin: 0; font-size: 12px; font-weight: 700; letter-spacing: .1em; color: var(--pine); }
  .ex-panel h2 { font-size: 34px; margin: 4px 0 6px; text-transform: uppercase; overflow-wrap: anywhere; }
  .ex-addr, .ex-dist { margin: 0 0 4px; color: var(--ink2); font-size: 15px; }
  .ex-actions { margin: 14px 0 8px; display: grid; gap: 8px; }
  .ex-apple { justify-content: center; }
  .ex-act-row { display: flex; gap: 8px; flex-wrap: wrap; }
  .ex-act-row a, .ex-act-row button { flex: 1; min-width: 88px; min-height: 44px; display: inline-flex; align-items: center; justify-content: center; text-align: center; padding: 8px 10px; border: 1px solid var(--rule2); border-radius: 12px; text-decoration: none; color: var(--huck); font: 600 15px/1.2 var(--text); background: var(--surface); cursor: pointer; }
  .ex-act-row button[aria-pressed="true"] { background: var(--russetsoft); color: var(--on-russet); }
  .ex-sec { margin-top: 18px; }
  .ex-sec h3 { font-size: 12px; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); border-bottom: 1px solid var(--rule); padding-bottom: 6px; margin-bottom: 8px; }
  .ex-sec p, .ex-sec li { font-size: 15px; color: var(--ink2); margin: 6px 0; }
  .ex-sec a, .ex-app a { display: inline-flex; align-items: center; min-height: 44px; }
  .ex-kv { display: flex; justify-content: space-between; gap: 12px; font-size: 15px; padding: 3px 0; }
  .ex-kv span { color: var(--ink2); }
  .ex-kv b { text-align: right; }
  .ex-fine { font-size: 13px !important; color: var(--muted) !important; }
  .ex-app { margin-top: 22px; font-size: 14px; color: var(--muted); }
  body.ex-open { overflow: hidden; }
  @media (min-width: 601px) { body.ex-open { overflow: auto; } }
"""
EXPLORE_GUIDES = [(g["key"], g["app"], len(g["places"])) for g in GUIDES] + [("honors", "James Beard", len(HON_L)), ("oldest", "Oldest", len(OLD_L))]
EXPLORE_GUIDES = [(k, t) for k, t, n in EXPLORE_GUIDES if n > 0] + [("all", "All restaurants"), ("saved", "Saved")]   # an empty guide gets no button, as on the app's Home
DEFAULT_GUIDE = next((k for k in ("fingersteaks", "basque", "spuds", "huckleberry", "trout", "historic", "taquerias", "honors", "oldest")
                      if any(k == x for x, _ in EXPLORE_GUIDES)), "all")
url = f"{DOMAIN}/explore/"
NP = len(PICKS)
title = fit(["Search Idaho Restaurants, Finger Steaks & Basque Food", "Idaho Restaurant Search & Map | Idaho Eats"], 50, 60, "explore title")
desc = fit([f"Search {N_REST:,} Idaho restaurants by name, town, street or dish, and map {NP} hand-checked picks: Basque food, finger steaks, spud plates and huckleberry."]
           + [f"Search {N_REST:,} Idaho restaurants by name, town, street or dish, and browse {NP} hand-checked Basque, finger steak and spud picks on a map{x}."
              for x in ("", ", free", " in your browser", ", free in your browser", ". Free, no ratings")]
           + [f"Search {N_REST:,} Idaho restaurants by name, town, street or dish, with {NP} hand-checked picks and {len(HON_L)} James Beard honorees on a map{x}."
              for x in ("", ", free", " in your browser", ". Free, no ads, no ratings")], 140, 160, "explore description")
nav, bc = crumbs([("Home", "/"), ("Search", "/explore/")])
guide_buttons = "".join(f'<button type="button" data-g="{k}" aria-pressed="{str(k == DEFAULT_GUIDE).lower()}">{e(t)}</button>' for k, t in EXPLORE_GUIDES)
explore_js = open(f"{ROOT}/scripts/explore.js").read()
assert "</script" not in explore_js.lower()
STORE_PREFIX = re.search(r'const PREFIX = "([^"]+)";', explore_js).group(1)
STORE_KEYS = [STORE_PREFIX + k for k in dict.fromkeys(re.findall(r'store\.set\("([a-z]+)"', explore_js))]   # what the privacy page must name
assert STORE_KEYS, "explore.js writes no localStorage keys?"
noscript_links = ", ".join(f'<a href="/{g["path"]}">{e(g["name"].replace("Idaho ", "", 1))}</a>' for g in PAGED)
body = f"""{nav}
  <main id="main">
  <section class="ex-hero">
    <p class="kicker">{BRAND} · in your browser</p>
    <h1>Search Idaho restaurants</h1>
    <p class="sub">Pick a guide for the {NP} places we checked by hand or the {plural(len(HON_L), "James Beard honoree")}, or choose All restaurants and type a name, a town, a street or a dish to look through {N_REST:,} Idaho restaurants, cafés, bars and bakeries. It runs on the data the coming iPhone and iPad app ships with, and whatever you save stays in this browser.</p>
  </section>
  <noscript><p>Searching needs JavaScript turned on; the guide pages don't: {noscript_links}{", " if noscript_links else ""}<a href="/cities/">cities and regions</a>.</p></noscript>
  <div id="ex-app" data-default="{DEFAULT_GUIDE}" data-store="{e(APP_STORE_URL or '')}">
    <div class="ex-controls">
      <div class="ex-guides" role="group" aria-label="Guides">{guide_buttons}</div>
      <div class="ex-row1">
        <label class="vh" for="ex-q">Search</label>
        <input id="ex-q" type="search" placeholder="Name, town, street or dish" autocomplete="off" enterkeyhint="search" disabled>
        <button type="button" id="ex-locate" class="ex-small" disabled>Near me</button>
      </div>
      <div class="ex-row2">
        <label class="ex-sel"><span class="vh">Sort</span><select id="ex-sort" disabled><option>Featured first</option></select></label>
        <label class="ex-sel"><span class="vh">Town</span><select id="ex-town" disabled><option value="">All towns</option></select></label>
        <label class="ex-sel"><span class="vh">Kind of place</span><select id="ex-cuisine" disabled><option value="">All kinds</option></select></label>
        <label class="ex-check"><input type="checkbox" id="ex-chains" disabled> Hide chains</label>
        <button type="button" id="ex-clear" class="ex-small ex-off" disabled>Clear filters</button>
        <div class="ex-view" role="group" aria-label="View"><button type="button" data-v="list" aria-pressed="true">List</button><button type="button" data-v="map" aria-pressed="false">Map</button></div>
      </div>
      <p id="ex-sub"></p>
      <p id="ex-count" aria-live="polite"></p>
      <p id="ex-locmsg"></p>
    </div>
    <div id="ex-listwrap"><p id="ex-loading" role="status">Loading the restaurant list…</p><ol id="ex-list" class="ex-list"></ol><button type="button" id="ex-more" class="ex-small" hidden></button></div>
    <div id="ex-mapwrap" hidden>
      <canvas id="ex-map" role="img" aria-label="Map of Idaho with a dot for each place in the list. The list view has the same places."></canvas>
      <div class="ex-zoom"><button type="button" id="ex-zin" aria-label="Zoom in">+</button><button type="button" id="ex-zout" aria-label="Zoom out">−</button></div>
      <p id="ex-maphint"></p>
    </div>
  </div>
  <div id="ex-scrim" class="ex-scrim" hidden></div>
  <aside id="ex-panel" class="ex-panel" hidden aria-labelledby="ex-pname"></aside>
  </main>
<script>
{explore_js}
</script>"""
webapp_ld = {"@context": "https://schema.org", "@type": "WebApplication", "name": f"{BRAND} web app", "url": url,
             "applicationCategory": "TravelApplication", "operatingSystem": "Any", "browserRequirements": "Requires JavaScript",
             "description": desc, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "publisher": {"@id": ORG_ID}, "author": {"@id": PERSON_ID}}
page("explore/index.html", title, desc, body, [webapp_ld, bc], extra_css=EXPLORE_CSS, og_type="website")

# ---------------------------------------------------------------- landing page
shots = [("home", "Idaho Eats home screen: Basque, Finger Steaks & Drive-Ins, Spud Plates, Huckleberry, Idaho Trout, Historic Saloons, James Beard Honors and Oldest Places guides, with a search box.", "Guides for finger steaks, Basque food and spuds."),
         ("fingersteaks", "The hand-checked Finger Steaks & Drive-Ins list in Idaho Eats, sorted by distance from downtown Boise.", "Finger steaks nearest you first."),
         ("detail", "A place in Idaho Eats: address, a button for ratings, hours and photos in Apple Maps, what's on the menu and its health district's inspection lookup.", "Each place, with live Apple Maps hours and photos."),
         ("map", "Idaho Eats map of Idaho with pins for hand-checked places.", "The map, by guide."),
         ("honors", "James Beard honors list in Idaho Eats.", "Idaho's James Beard honorees.")]
shot_html = []
for i, (name, alt, capn) in enumerate(shots):   # App Store screenshots don't exist yet: each one shows up once scripts/site-images.sh makes it
    png = f"{DOCS}/img/screen-{name}.png"
    if not os.path.exists(png):
        continue
    w, h = png_size(png)
    src = f'<source srcset="/img/screen-{name}.webp" type="image/webp">' if os.path.exists(f"{DOCS}/img/screen-{name}.webp") else ""
    shot_html.append(f'<li><picture>{src}<img src="/img/screen-{name}.png" alt="{e(alt)}" width="{w}" height="{h}" loading="lazy" decoding="async"></picture><p>{e(capn)}</p></li>')

paged_names = [g["app"].lower() for g in PAGED]
faq = [
    ("Does Idaho grade or score its restaurants?", f"No. Idaho's {words_num(len(DISTRICTS))} public health districts inspect restaurants, but none hands out a grade, score or window placard, and none publishes its results in bulk, so {BRAND} has no inspection results to show. Each place links the lookup run by its own district instead, and our inspections page lists all {words_num(len(DISTRICTS))}."),
    ("Does it cover north Idaho and the resort towns?", f"Yes: the {N_REST:,} places reach {N_TOWNS:,} towns, from Sandpoint and Coeur d'Alene in the Panhandle to Ketchum, Stanley and McCall in the mountains. Resort-town and backcountry kitchens often close between seasons, so call before a long drive."),
    ("How were the Basque, finger steak and spud lists checked?", f"By hand, in {CHECKED}. Each of the {NP} places on the Idaho lists has a 2025 or 2026 source, usually its own menu or a dated local news story, and its street address was checked against it. James Beard honors come from the Foundation's own announcements. Everything else is Overture Maps' open place data{', matched against Idaho State Police alcohol licenses' if ABC else ''}."),
    (f"What does {BRAND} cost?", f"Not a cent. {BRAND} carries no advertising, sells nothing inside the app and never asks you to sign up. The iPhone and iPad app hasn't reached the App Store yet, but the search on this site works today."),
    ("Where do ratings and hours come from?", f"From Apple Maps, live. {BRAND} keeps no ratings or reviews of its own and never sorts a list by them; tap a place and Apple's place card shows its current hours, photos and ratings."),
    ("Is my location sent to you?", "No. Sharing it is up to you, and all it does is bring the nearest places to the top. The app keeps it on your iPhone or iPad, and on this site Near me does its sorting inside your browser, so your whereabouts never reach us."),
    ("Spotted a closed or missing place?", f"Email {EMAIL} with the restaurant's name and town, and the correction rides along with the next data update."),
]
faq_html = "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in faq)
faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "@id": f"{DOMAIN}/#faq",
          "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
app_node = {"@type": "MobileApplication", "@id": f"{DOMAIN}/#app", "name": APP_NAME,
            "alternateName": [BRAND, f"{BRAND}: {TAGLINE}"],
            "description": f"A free guide to {N_REST:,} Idaho restaurants, with {NP} hand-checked picks for Basque food, finger steaks, drive-ins, spud plates, huckleberry, Idaho trout and historic saloons, and {plural(len(HON_L), 'James Beard honoree')}. Sort by distance, open Apple Maps' live place card for hours and photos, and save places for your next trip.",
            "url": f"{DOMAIN}/", "image": f"{DOMAIN}/og.png", "operatingSystem": "iOS, iPadOS", "applicationCategory": "TravelApplication",
            "applicationSubCategory": "Food & Drink", "inLanguage": "en", "author": {"@id": PERSON_ID}, "publisher": {"@id": ORG_ID}}
if APP_STORE_URL:   # no "offers" until the app is on the App Store
    app_node.update({"offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD", "category": "free"}, "installUrl": APP_STORE_URL, "sameAs": [APP_STORE_URL]})
if shot_html:
    app_node["screenshot"] = f"{DOMAIN}/img/screen-home.png"
app_ld = {"@context": "https://schema.org", "@graph": [app_node]}
title = "Idaho Eats: Finger Steak, Basque & Restaurant Guide App"
desc = fit([f"Free iPhone and iPad guide to {N_REST:,} Idaho restaurants, with {NP} hand-checked picks for Basque food, finger steaks, drive-ins, spuds and huckleberry.",
            f"A free iPhone and iPad guide to {N_REST:,} Idaho restaurants, with {NP} hand-checked picks for Basque food, finger steaks, spuds and huckleberry.",
            f"A free iPhone and iPad guide to {N_REST:,} Idaho restaurants, with hand-checked picks for Basque food, finger steaks, drive-ins and spud plates."], 140, 160, "landing description")
screens = f"""
  <section id="screens">
    <h2>What it looks like</h2>
    <ul class="shots" tabindex="0" aria-label="{BRAND} app screenshots">
      {"".join(shot_html)}
    </ul>
  </section>""" if shot_html else ""
cards = [f'<a class="card" href="/{g["path"]}"><h3>{e(cap1(g["name"]))}</h3><p>{plural(len(g["places"]), "hand-checked place")}.</p></a>' for g in PAGED]
if HON_PAGE:
    cards.append(f'<a class="card" href="/{HON_PATH}"><h3>James Beard honorees</h3><p>{plural(len(HON_L), "honored Idaho restaurant")}, 2023–26.</p></a>')
if OLD_PAGE:
    cards.append(f'<a class="card" href="/{OLD_PATH}"><h3>Idaho\'s oldest restaurants</h3><p>{plural(len(OLD_L), "place")} with a documented founding year.</p></a>')
cards.append(f'<a class="card" href="/{INS_PATH}"><h3>Restaurant inspections</h3><p>How to look one up with each of Idaho\'s {words_num(len(DISTRICTS))} public health districts.</p></a>')
cards.append(f'<a class="card" href="/explore/"><h3>Search the state</h3><p>Look up {N_REST:,} places to eat in {N_TOWNS:,} Idaho towns, in your browser.</p></a>')
coming = [g for g in SKIPPED if g["places"]]
coming_note = (f' {cap1(join_words([g["app"] for g in coming]))} {"is" if len(coming) == 1 else "are"} in the app and the web search, with a page here once the list has {MIN_LIST} places.'
               if coming else "")
stats = [(NP, "hand-checked picks"), (len(HON_L), "James Beard honorees"), (N_REST, "restaurants"), (N_TOWNS, "towns")]
body = f"""  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND}: the {TAGLINE[:1].lower() + TAGLINE[1:]} for iPhone and iPad</p>
    <h1>Idaho restaurants, from Basque Block croquetas to drive-in finger steaks</h1>
    <p class="lede">Where Idaho actually eats: croquetas on Boise's Basque Block, finger steaks dunked in fry sauce, a loaded russet, a huckleberry shake in a mountain town. {BRAND} gathers {NP} places we checked by hand into guides for those, and lets you search {N_REST:,} restaurants, cafés, bars and bakeries across {N_TOWNS:,} Idaho towns. It's free.</p>
    {cta('<a class="btn btn-ghost" href="/explore/">Search on the web</a>')}
    <ul class="stats" aria-label="What's in the app">
      {"".join(f"<li><b>{n:,}</b><span>{t}</span></li>" for n, t in stats)}
    </ul>
  </section>

  <section id="what">
    <h2>Built around fry sauce, solomo and huckleberry season</h2>
    <p class="sub">Star ratings won't tell you which drive-in still has finger steaks on the menu, or who in Boise serves solomo. So {BRAND} begins with what Idahoans go looking for: Basque kitchens, finger steaks and drive-ins, potatoes, huckleberry, Idaho trout, taquerías and saloons that have poured for generations. We read a 2025 or 2026 menu or news story for every place on those lists in {CHECKED}. Hours, photos and ratings stay with Apple Maps, whose live card opens from any place.</p>
  </section>

  <section id="how">
    <h2>How it works</h2>
    <ol class="steps">
      <li class="step"><div class="n" aria-hidden="true">1</div><div><h3>Start with a craving.</h3><p>Open Basque, Finger Steaks &amp; Drive-Ins, Spud Plates, Huckleberry, Idaho Trout, Taquerías, Historic Saloons, James Beard Honors or Oldest Places, or type a name, town, street or dish to search the {N_REST:,} places.</p></div></li>
      <li class="step"><div class="n" aria-hidden="true">2</div><div><h3>Narrow it to your road.</h3><p>Let the nearest rise to the top, stick to one town or one kind of food, or pan the state map from Bonners Ferry down to Bear Lake.</p></div></li>
      <li class="step"><div class="n" aria-hidden="true">3</div><div><h3>Head out.</h3><p>Pull up Apple Maps for today's hours and photos, ring ahead, get turn-by-turn directions, or tuck the place away for a later trip.</p></div></li>
    </ol>
  </section>
{screens}
  <section id="guides">
    <h2>Idaho food guides</h2>
    <p class="sub">Each guide in the app also has its own page here, with every place, its dishes and its source.{e(coming_note)}</p>
    <div class="grid2">
      {"".join(cards)}
    </div>
  </section>

  <section id="cities">
    <h2>By city and region</h2>
    <p class="sub">From Coeur d'Alene to Twin Falls, each town page gathers the picks, honorees and old-timers in and around it, and each region follows a public health district's counties. <a href="/cities/">See what each page has</a>.</p>
    <ul class="cities">{"".join(f'<li><a href="{city_url(c)}">{e(c)}</a></li>' for c in CITY_PAGES)}</ul>
    <p class="sub">And by region:</p>
    {region_links()}
  </section>

  <section id="pricing">
    <h2>No price tag, no sign-up</h2>
    <p class="sub">{BRAND} costs nothing and shows no ads, and there's nothing to subscribe to or log in to. Every list is stored in the app itself, so it opens without a connection, which helps on a backcountry road out of cell range.</p>
  </section>

  <section id="privacy">
    <h2>Nothing here keeps track of you</h2>
    <p class="sub">Your phone keeps your location and your saved places to itself: location, when you allow it, only reorders the lists by distance on the device. This website stores no cookies, and nothing on it tracks visits. <a href="/privacy.html">Read the privacy policy</a>.</p>
  </section>

  <section id="faq">
    <h2>Questions</h2>
    {faq_html}
  </section>

  <section id="download" class="final">
    <h2>Plan the next stop</h2>
    <p class="sub">{f"Get {BRAND} free on the App Store for iPhone and iPad." if APP_STORE_URL else f"{BRAND} for iPhone and iPad is headed for the App Store, free. Until then, ask for early access."}</p>
    <div class="cta-row">{store_button()}</div>
  </section>
  </main>"""
page("index.html", title, desc, body, [app_ld, faq_ld], og_type="website")

# ---------------------------------------------------------------- about, sources and licenses
os.makedirs(f"{DOCS}/licenses", exist_ok=True)
for f in ("Apache-2.0", "CDLA-Permissive-2.0", "Foursquare-NOTICE"):
    shutil.copyfile(f"{ROOT}/IdahoEats/Resources/Licenses/{f}.txt", f"{DOCS}/licenses/{f}.txt")
FOURSQUARE_NOTICE = open(f"{ROOT}/IdahoEats/Resources/Licenses/Foursquare-NOTICE.txt").read().strip()
den = (D.get("calibration") or {}).get("reference_colorado_denver", {}).get("groups", {}).get("meta_high", {}).get("official")
den_txt = (f" Tested against Denver's full list of food licenses (the same map data, in Colorado), high-confidence listings matched a licensed "
           f"business {round(den * 100)}% of the time." if isinstance(den, (int, float)) else "")
abc_src = (f'<li><b>Idaho State Police, Alcohol Beverage Control</b>: public retail alcohol license records{f" (as of {hdate(LIQUOR_DATE)})" if LIQUOR_DATE else ""}: '
           f'the business name, premises address and license type, {plural(ABC, "license")} in all. Licensee names are never shown. Idaho State Police does not endorse {BRAND} and isn\'t responsible for how the records are used here.</li>'
           if ABC else f"<li><b>Idaho State Police, Alcohol Beverage Control</b>: the retail alcohol license list isn't in this version of {BRAND}, so no place shows a license or whether it serves alcohol.</li>")
census_src = "<li><b>U.S. Census Bureau Geocoder</b> (public domain): puts researched addresses on the map where Overture's address points don't reach.</li>" if CENSUS else ""
nav, bc = crumbs([("Home", "/"), ("About and sources", "/about.html")])
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <p class="kicker">About {BRAND}</p>
    <h1>Who makes {BRAND}, and how</h1>
    <p class="lede">{BRAND} is an independent app and website by {AUTHOR}: a free guide to {N_REST:,} Idaho restaurants, with {NP} hand-checked picks for Basque food, finger steaks and drive-ins, spud plates, huckleberry, Idaho trout, taquerías and historic saloons, plus {plural(len(HON_L), "James Beard honoree")}. No account, no ads, no tracking.</p>
  </section>
  <section id="sources">
    <h2 id="nicholas-soderstrom">Who makes it</h2>
    <p>{AUTHOR} makes the {BRAND} app and this site. {BRAND} is not affiliated with, endorsed by or operated by the State of Idaho, Idaho State Police, the Idaho Department of Health and Welfare, any of Idaho's public health districts, any city or county, the James Beard Foundation, Apple, or any restaurant, team, university or chain.</p>
    <h2>How the lists are built</h2>
    <p>The Idaho guides are hand-checked: each place was checked in {CHECKED} against a 2025 or 2026 source (the place's own website or menu, or local news), with the address checked. Founding years mean the year it opened at this address. Resort-town places that close between seasons say so. Research records facts only, with a source for every place: no review text and no ratings from anyone. Places the research finds closed come off the lists. A guide gets its own page here once it has {MIN_LIST} places; until then it's in the app and the web search.</p>
    <p>Honors are James Beard Foundation awards, nominees, semifinalists and America's Classics from 2023 to 2026, checked by hand against the Foundation's announcements.</p>
    <p>The rest of the {N_REST:,} places come from Overture Maps' open place data{", checked against Idaho State Police's alcohol licenses" if ABC else ""}. High-confidence map listings are kept; single listings are marked Listing only.{den_txt} Website links are checked, and any that no longer belong to the place are left out.</p>
    <p>Idaho's {words_num(len(DISTRICTS))} public health districts inspect restaurants, but none publishes results in bulk and none issues a grade or placard, so {BRAND} has no inspection results; each place links its district's own lookup (<a href="/{INS_PATH}">how to look up an Idaho restaurant inspection</a>). Ratings, reviews, hours and photos in the app are Apple Maps' own, shown live in Apple's place card; {BRAND} doesn't store or rank by them.</p>
    <h2>Updates</h2>
    <p>This build's restaurant data is from {hdate(D["generated"])}{f", from Overture Maps release {e(OVERTURE)}" if OVERTURE else ""}; the hand checks were done in {CHECKED}. The data is rebuilt when the research or the open data changes, and corrections go into the next update. Places open and close, so check before you go.</p>
    <h2>Sources and licenses</h2>
    <ul>
      <li><b>Overture Maps Foundation</b> (<a href="https://overturemaps.org" rel="noopener">overturemaps.org</a>): restaurant listings and websites{f", release {e(OVERTURE)}" if OVERTURE else ""}, filtered and reformatted for {BRAND}. Data from Meta, Microsoft, DAC and BrightQuery, available under the <a href="/licenses/CDLA-Permissive-2.0.txt">Community Data License Agreement – Permissive 2.0</a>. Data from Foursquare, © Foursquare Labs, Inc., available under the <a href="/licenses/Apache-2.0.txt">Apache License 2.0</a>; see the notice below. Data from AllThePlaces, available under CC0 1.0. License records and researched addresses are placed on the map with Overture Maps addresses data (open address sources under permissive licenses, docs.overturemaps.org/attribution).</li>
      {abc_src}
      {census_src}
      <li><b>Idaho's public health districts</b>: their names, counties and inspection lookups, linked, not copied. Each lookup link was checked on October 8, 2026.</li>
      <li><b>Honors</b>: James Beard Foundation awards, nominees, semifinalists and America's Classics are reported as facts. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation. Other names belong to their owners.</li>
      <li><b>Maps</b>: county outlines from Overture Maps Foundation divisions, © OpenStreetMap contributors (ODbL). In the app, maps, place cards and directions are by Apple Maps.</li>
    </ul>
    <h2>Foursquare notice</h2>
    <div class="notice">{e(FOURSQUARE_NOTICE)}</div>
    <h2>Contact</h2>
    <p>Corrections, a missing or closed place, or anything else: <a href="mailto:{EMAIL}">{EMAIL}</a>. See also the <a href="/privacy.html">privacy policy</a> and <a href="/terms.html">terms of use</a>.</p>
  </section>
  </main>"""
about_ld = {"@context": "https://schema.org", "@type": "AboutPage", "url": f"{DOMAIN}/about.html", "name": f"About {BRAND}",
            "mainEntity": {"@id": PERSON_ID}, "isPartOf": {"@id": SITE_ID}, "dateModified": TODAY}
page("about.html", fit([f"About Idaho Eats: Who Makes It and Where the Data Comes From", "About Idaho Eats: Sources, Methods and Who Makes It"], 50, 60, "about title"),
     fit([f"Idaho Eats is an independent app and website by {AUTHOR}. How the hand-checked Basque, finger steak and spud lists are built, plus sources and licenses.",
          f"Idaho Eats is an independent app and website by {AUTHOR}: how the hand-checked lists are built, where the data comes from, and its licenses."], 140, 160, "about description"),
     body, [about_ld, bc])

# ---------------------------------------------------------------- privacy and terms
nav, bc = crumbs([("Home", "/"), ("Privacy policy", "/privacy.html")])
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <h1>Privacy policy</h1>
    <p class="lede">Short version: the {BRAND} app collects nothing about you, and this website doesn't track you. Last updated {hdate(PRIVACY_UPDATED)}.</p>
  </section>
  <section>
    <h2>The app</h2>
    <ul>
      <li><b>No account, no analytics, no ads.</b> The app has no sign-in, no advertising and no analytics or crash-reporting code. We receive no data from it.</li>
      <li><b>Location.</b> If you allow it, your location is used on your device to sort places by distance and show where you are on the map. It is never sent to us. You can turn it off in Settings at any time.</li>
      <li><b>Saved places and filters</b> are stored only on your device and are deleted when you delete the app.</li>
      <li><b>Apple Maps.</b> When you open a place's ratings, hours and photos, or ask for directions, the app asks Apple Maps for that place. Apple handles that request under <a href="https://www.apple.com/legal/privacy/" rel="noopener">Apple's privacy policy</a>, as it does for any app that shows a map.</li>
      <li><b>Data updates.</b> When you open the app, it checks this website for newer restaurant data, at most once a day (or an hour later if a check didn't go through), and downloads it when there is some. These requests carry no location or identifiers. GitHub, which hosts this site, may keep standard server logs of them, as it does for any visit here.</li>
      <li><b>Spotlight.</b> The app adds its hand-checked and honored places to your device's search index so you can find them from Spotlight. That index stays on your device.</li>
      <li><b>Calls, websites, email and inspection lookups</b> you start from a place open in the Phone app, your browser or Mail, and are handled by them and by the site you open.</li>
    </ul>
    <p>When the app is on the App Store, its privacy label will be "Data Not Collected".</p>
    <h2>This website</h2>
    <p>The site is static pages hosted on GitHub Pages. It sets no cookies and loads no analytics, fonts or scripts from anyone else. GitHub may keep standard server logs, such as IP addresses, for security; see <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" rel="noopener">GitHub's privacy statement</a>.</p>
    <ul>
      <li><b>Saved places and your last guide.</b> The search page (<a href="/explore/">/explore/</a>) keeps the places you save and the last guide you opened in your browser's local storage, on this device only, under the {"key" if len(STORE_KEYS) == 1 else "keys"} {join_words([f"<code>{k}</code>" for k in STORE_KEYS])}. Nothing is sent to us. Clearing this site's data in your browser removes them.</li>
      <li><b>Location.</b> If you tap Near me or choose the Nearest sort, your browser asks whether to share your location. If you allow it, the location is used only inside your browser to sort places by distance and is never sent to us or anyone else.</li>
      <li><b>Links out.</b> Apple Maps, directions, websites, phone numbers and the health districts' inspection lookups open in Apple Maps, the other site or your phone, under their own privacy policies.</li>
    </ul>
    <h2>Email</h2>
    <p>If you email us, we use your message and address only to reply and to fix the listing you told us about. We don't add you to a mailing list or share your address.</p>
    <h2>Children</h2>
    <p>The app collects no personal information from anyone, including children.</p>
    <h2>Changes and contact</h2>
    <p>If this policy changes, the new version will be posted here with a new date. Questions: <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>
  </section>
  </main>"""
page("privacy.html", "Privacy Policy: Idaho Eats Finger Steak & Restaurant App",
     fit(["The Idaho Eats privacy policy: the app collects no data, keeps your location and saved places on your device, and this website sets no cookies at all."], 140, 160, "privacy"),
     body, [bc])

nav, bc = crumbs([("Home", "/"), ("Terms of use", "/terms.html")])
abc_term = ("<li>Idaho State Police, Alcohol Beverage Control: public retail alcohol license records (licensee names are never shown).</li>" if ABC else "")
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <h1>Terms of use</h1>
    <p class="lede">The plain-language terms for the {BRAND} app and this website. Last updated {hdate(POLICY_UPDATED)}.</p>
  </section>
  <section>
    <h2>What the app is</h2>
    <p>{BRAND} is a free guide to restaurants in Idaho, made by {AUTHOR}. It is provided as is, for personal use, without charge and without warranties of any kind.</p>
    <h2>Check before you go</h2>
    <p>Restaurants open, close, change their hours and change their menus, and resort-town and backcountry places close between seasons. Dishes, seasons and founding years are what each place or a named source said when we checked in {CHECKED}. We work to keep the lists right, but we can't promise that any listing is current or complete. Call the restaurant before you make the trip.</p>
    <h2>Health inspections</h2>
    <p>{BRAND} shows no inspection results. Idaho's public health districts inspect restaurants but publish no results in bulk and issue no grade. Links to a district's own inspection lookup go to that district's site, which is responsible for what it shows; see <a href="/{INS_PATH}">how to look up an Idaho restaurant inspection</a>.</p>
    <h2>Other people's content</h2>
    <p>Ratings, reviews, hours and photos in each place card come from Apple Maps and are Apple's and its providers', under Apple's terms. Restaurant names and trademarks belong to their owners. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation. {BRAND} is not affiliated with any restaurant, team, chain, award body or government agency.</p>
    <h2>Data sources and licenses</h2>
    <ul>
      <li>Overture Maps Foundation places data: data from Meta, Microsoft, DAC and BrightQuery under the <a href="/licenses/CDLA-Permissive-2.0.txt">Community Data License Agreement, Permissive 2.0</a>; data from Foursquare (© Foursquare Labs, Inc.) under the <a href="/licenses/Apache-2.0.txt">Apache License 2.0</a>, with its <a href="/licenses/Foursquare-NOTICE.txt">notice</a>; data from AllThePlaces under CC0 1.0. Overture addresses data, compiled from open address sources under permissive licenses. County outlines under the Open Database License, © OpenStreetMap contributors, Overture Maps Foundation.</li>
      {abc_term}
      <li>James Beard Foundation: award, nominee and semifinalist history and America's Classics, reported as facts.</li>
      <li>Basque food, finger steaks and drive-ins, spud plates, huckleberry, trout, taquerías, historic saloons and founding years: our own research, with a source recorded for every place.</li>
    </ul>
    <p>More on each source: <a href="/about.html">about {BRAND}</a>.</p>
    <h2>Corrections</h2>
    <p>If a listing is wrong, or you own a restaurant and want something fixed, email <a href="mailto:{EMAIL}">{EMAIL}</a>. We fix mistakes in the next update.</p>
    <h2>Liability</h2>
    <p>To the extent the law allows, we are not liable for any loss arising from use of the app or site, including a wasted drive to a closed restaurant.</p>
    <h2>Changes</h2>
    <p>We may update these terms; the current version and its date are always on this page. See also the <a href="/privacy.html">privacy policy</a>.</p>
  </section>
  </main>"""
page("terms.html", "Terms of Use: Idaho Eats Finger Steak & Restaurant App",
     fit(["The Idaho Eats terms of use: a free Idaho restaurant guide, provided as is. Check before you go, and see where each listing comes from and what it means."], 140, 160, "terms"),
     body, [bc])

lost = [f'<a href="/{g["path"]}">{e(g["name"].replace("Idaho ", "", 1))}</a>' for g in PAGED[:2]]
body = f"""  <main id="main">
  <section class="hero">
    <h1>This trail dead-ends</h1>
    <p class="lede">No page lives at this address, maybe because a link was mistyped or a page moved. Head back to the <a href="/">{BRAND} home page</a>, or pick up {join_words(lost + ['the <a href="/cities/">cities and regions</a>']) if lost else 'the <a href="/cities/">cities and regions</a>'}.</p>
    <p><a class="btn" href="/explore/">Search Idaho restaurants</a></p>
  </section>
  </main>"""
page("404.html", f"Page not found | {BRAND}", "No page lives at this address.", body, robots="noindex,follow")

# ---------------------------------------------------------------- plumbing
# pages that left the site (a guide that fell under MIN_LIST, a place no longer listed, a town the data lost) are removed, so the
# sitemap, the links and the files always agree. docs/ is all generated: every .html file here comes from this script.
keep = set(written + noindexed + ["404.html"])
for dirpath, _, files in os.walk(DOCS):
    for f in files:
        rel = os.path.relpath(os.path.join(dirpath, f), DOCS)
        if f.endswith(".html") and rel not in keep and not rel.startswith(("screenshots/", "img/")):
            os.remove(os.path.join(dirpath, f))
            print("removed stale", rel)
open(f"{DOCS}/favicon.svg", "w").write(potato_svg() + "\n")
try:   # the classic /favicon.ico (the custom domain's root asks for it), from the brand icon
    from PIL import Image
    Image.open(f"{DOCS}/icon-512.png").convert("RGBA").save(f"{DOCS}/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
except ImportError:
    pass


def order_key(u):
    return (u != "", u.startswith("places/"), u.startswith("regions/"), u.startswith("cities/"), u)


urls = sorted(("" if w == "index.html" else w.removesuffix("index.html") for w in written), key=order_key)
open(f"{DOCS}/sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                       + "".join(f"  <url><loc>{DOMAIN}/{u}</loc><lastmod>{TODAY}</lastmod></url>\n" for u in urls) + "</urlset>\n")
open(f"{DOCS}/robots.txt", "w").write(f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")
json.dump({"name": BRAND, "short_name": BRAND, "description": f"{TAGLINE}, plus {N_REST:,} Idaho restaurants.", "start_url": f"{BASE}/", "display": "browser",
           "background_color": "#f8f4ec", "theme_color": "#4b2a5c",
           "icons": [{"src": f"{BASE}/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": f"{BASE}/icon-512.png", "sizes": "512x512", "type": "image/png"},
                     {"src": f"{BASE}/favicon.svg", "sizes": "any", "type": "image/svg+xml"}]},
          open(f"{DOCS}/site.webmanifest", "w"), indent=2)
if CUSTOM_DOMAIN:
    open(f"{DOCS}/CNAME", "w").write(CUSTOM_DOMAIN + "\n")
elif os.path.exists(f"{DOCS}/CNAME"):
    os.remove(f"{DOCS}/CNAME")   # no custom domain yet: GitHub serves the project address
open(f"{DOCS}/.nojekyll", "w").write("")
os.makedirs(f"{ROOT}/playbook", exist_ok=True)
json.dump({"generated": TODAY, "domain": DOMAIN, "restaurants": N_REST, "towns": N_TOWNS, "counties": N_COUNTIES, "hand_checked": len(HC_L),
           "picks": NP, "guides": {g["key"]: {"places": len(g["places"]), "page": g["page"]} for g in GUIDES},
           "james_beard": {"places": len(HON_L), "page": HON_PAGE, "by_honor": dict(JB_N)}, "oldest": {"places": len(OLD_L), "page": OLD_PAGE},
           "place_pages": len(PAGE_PLACES), "abc_licenses": ABC, "cities": city_stats, "regions": region_stats, "noindex_pages": noindexed,
           "min_list": MIN_LIST},
          open(f"{ROOT}/playbook/site-numbers.json", "w"), indent=1)
print("wrote", len(written) + len(noindexed) + 1, "pages:", len(PAGE_PLACES), "place pages,", len(DISTRICTS), "regions,", len(CITY_PAGES), "cities, and",
      ", ".join(w for w in written if not w.startswith(("places/", "cities/", "regions/"))))
if noindexed:
    print("noindex (fewer than 5 listed places, left out of the sitemap):", ", ".join(noindexed))
print(f"restaurants {N_REST:,} in {N_TOWNS} towns | hand-checked {len(HC_L)} | " + " | ".join(f"{g['key']} {len(g['places'])}{'' if g['page'] else ' (no page)'}" for g in GUIDES)
      + f" | honors {len(HON_L)}{'' if HON_PAGE else ' (no page)'} | oldest {len(OLD_L)}{'' if OLD_PAGE else ' (no page)'}")
