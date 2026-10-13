"""Official records for Idaho -> one table of licensed food and drink businesses.

Idaho has no statewide food-license list and no bulk inspection data (see playbook/12-sources.md). The one statewide official list is
the Idaho State Police Alcohol Beverage Control (ABC) license list: every retail alcohol license (beer, wine, liquor by the drink),
with the trade name (DBA), premises address, county, license type, endorsements and an on-premises flag. ISP's robots.txt keeps
automated agents off its License Search (`Disallow: /AbcReporting/*/search`), so the list is exported by hand in a browser (Nick,
2026-10-08) into data/raw/official/ as Licenses*.csv (one file, or one per county). The Licensee column (a legal entity, sometimes a
person) is read only to recognize listings named for their holder; it is never shown.

load() returns: jur, lic (our id), name, dba, holder, keys (name keys), addr, city, zip, county, num, street, lat, lon, kind, active,
ltype, onprem, endorse, expires. kind: restaurant | bar | brewery | retail | venue | other.
"""
import os, re, glob
import numpy as np, pandas as pd
from common import norm_name, RAW, name_sim, _stems, GENERIC

OFF = os.path.join(RAW, "official")
DIRS = {"N": "N", "S": "S", "E": "E", "W": "W", "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}
TYPES = set("ST STREET AVE AV AVENUE BLVD BOULEVARD RD ROAD DR DRIVE LN LANE CT COURT PL PLACE PKWY PARKWAY TER TRL TRAIL WAY HWY CIR "
            "CIRCLE PLZ SQ MALL BND PASS XING RUN ROW WALK RDG LOOP".split())


def road(a):
    """One spelling for numbered roads: 'US HIGHWAY 95' = 'US-95' = 'Hwy 95'; 'STATE HIGHWAY 55' = 'ID-55' = 'SH 55'."""
    a = re.sub(r"(\d)\s*&\s*(\d)", r"\1-\2", a.upper())
    a = re.sub(r"\b(US|ID|SH|I)-(\w)", r"\1 \2", a)
    a = re.sub(r"\b(?:US|U S)\s+(?:HIGHWAY|HWY)\b", "US", a)
    a = re.sub(r"\b(?:STATE (?:HIGHWAY|HWY|ROAD|RD)|SH|IDAHO (?:HIGHWAY|HWY|STATE HIGHWAY)|ID (?:HIGHWAY|HWY)|ID)\b(?=\s+\d)", "IDH", a)
    a = re.sub(r"\bHIGHWAY\b", "HWY", a)
    return re.sub(r"\b(US|IDH|HWY) (\w+)\s*-\s*\w+", r"\1 \2", a)


ORD = {"FIRST": "1ST", "SECOND": "2ND", "THIRD": "3RD", "FOURTH": "4TH", "FIFTH": "5TH", "SIXTH": "6TH", "SEVENTH": "7TH",
       "EIGHTH": "8TH", "NINTH": "9TH", "TENTH": "10TH", "ELEVENTH": "11TH", "TWELFTH": "12TH"}


def street_key(a):
    """'2505 Monroe St' -> ('2505', 'MONROE'); '1000 OSAGE STREET' -> ('1000', 'OSAGE'); 'E Sherman Ave' keeps 'SHERMAN'."""
    if not isinstance(a, str):
        return None, None
    a = re.sub(r"[.,#]", " ", road(a))
    m = re.match(r"^\s*(\d+)[A-Z]?(?:\s*-\s*\d+[A-Z]?)?\s+(.*)$", a)
    if not m:
        return None, None
    words = [w for w in m.group(2).split() if w]
    if len(words) > 1 and words[0] in DIRS:
        words = words[1:]
    core = []
    for w in words:
        if w in TYPES and core:
            break
        core.append(w)
    core = [ORD.get(w, w) for w in core]
    return m.group(1), " ".join(core[:3]) or None


def street_compat(a, b):
    """Same street, or one is a whole-word prefix of the other."""
    if not isinstance(a, str) or not isinstance(b, str) or not a or not b:
        return False
    return a == b or a.startswith(b + " ") or b.startswith(a + " ")


def street_nums(a):
    """'157-159 W Main St' -> {'157', '159'}; '2505 Monroe St' -> {'2505'}."""
    if not isinstance(a, str):
        return set()
    a = road(a)
    m = re.match(r"^\s*(\d+)[A-Z]?(?:\s*-\s*(\d+)[A-Z]?)?\s", a.upper() + " ")
    if not m:
        return set()
    lo = int(m.group(1)); hi = int(m.group(2)) if m.group(2) else lo
    if hi < lo:   # "1500-02"
        hi = int(str(lo)[: len(str(lo)) - len(m.group(2))] + m.group(2)) if m.group(2) else lo
    return {str(x) for x in range(lo, hi + 1, 2 if (hi - lo) % 2 == 0 else 1)} if 0 <= hi - lo <= 12 else {str(lo)}


def _names(*vals):
    out = []
    for v in vals:
        if not isinstance(v, str):
            continue
        v = re.sub(r"\s*\((?:MOBILE|CATERING|SPECIAL EVENT|TEMP(?:ORARY)? EVENT|INSIDE [^)]*)\)\s*$", "", v, flags=re.I)
        for part in re.split(r"\s*/\s*|\s+\bdba\b\s+|\s+&\s+(?=[A-Z][a-z])", v, flags=re.I):
            k = norm_name(re.sub(r"\b(?:LLC|INC|CORP|CORPORATION|LTD|CO)\b\.?", "", part, flags=re.I))
            if k and k not in out:
                out.append(k)
    return out


def _col(df, *pats):
    """The first column whose name matches one of the patterns (the export's headers aren't documented)."""
    for p in pats:
        for c in df.columns:
            if re.fullmatch(p, str(c).strip(), flags=re.I):
                return c
    return None


def liq_kind(ltype, endorse, onprem, name=""):
    """An ABC license -> kind. Liquor by the drink and on-premises beer or wine mean a bar or restaurant serving alcohol; off-premises
    beer and wine is a store (groceries, gas stations); manufacturers (breweries, wineries, distilleries) count as makers."""
    t = f"{ltype or ''} {endorse or ''}".upper()
    if re.search(r"BREW|WINERY|WINE MAKER|DISTILL|MANUFACTUR", t):
        return "brewery"
    if re.search(r"WHOLESAL|DISTRIBUT|IMPORT|DIRECT SHIP|CARRIER|WAREHOUSE", t):
        return "other"
    if onprem is True or re.search(r"LIQUOR BY THE DRINK|BY THE DRINK|ON[- ]PREM|RESTAURANT", t):
        return "restaurant" if re.search(r"RESTAURANT", t) else "bar"
    if onprem is False:
        return "retail"
    return None


def load_abc():
    files = sorted(glob.glob(f"{OFF}/Licenses*.csv")) + sorted(glob.glob(f"{OFF}/abc/*.csv"))
    if not files:
        return pd.DataFrame(columns=["jur", "lic", "name", "dba", "holder", "keys", "addr", "city", "zip", "county", "num", "street", "lat",
                                     "lon", "kind", "active", "ltype", "onprem", "endorse", "expires"])
    d = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in files], ignore_index=True).drop_duplicates()
    c_id = _col(d, r"license ?(?:id|#|no|number)?", r"premises? ?(?:#|no|number)?", r"id")
    c_dba = _col(d, r"dba", r"doing business as", r"trade ?name", r"business ?name")
    c_hold = _col(d, r"licensee", r"licensee ?name", r"owner")
    c_addr = _col(d, r"(?:premises ?|street ?|physical ?)?address(?: ?1)?", r"street")
    c_city = _col(d, r"city", r"premises ?city")
    c_zip = _col(d, r"zip(?: ?code)?", r"postal ?code")
    c_cty = _col(d, r"county")
    c_type = _col(d, r"license ?types?", r"type", r"classification")
    c_end = _col(d, r"endorsements?", r"add ?ons?")
    c_on = _col(d, r"on[- ]?premises?(?: ?consumption)?", r"on ?prem")
    c_exp = _col(d, r"expir\w*(?: ?date)?", r"end ?date")
    c_status = _col(d, r"status")
    rows = []
    for _, r in d.iterrows():
        on = str(r[c_on]).strip().upper() if c_on else ""
        onprem = True if on in ("Y", "YES", "TRUE", "1", "X") else False if on in ("N", "NO", "FALSE", "0") else None
        kind = liq_kind(r[c_type] if c_type else "", r[c_end] if c_end else "", onprem)
        addr = (r[c_addr] if c_addr else "").strip()
        num, st = street_key(addr)
        dba = (r[c_dba] if c_dba else "").strip() or None
        holder = (r[c_hold] if c_hold else "").strip() or None
        rows.append({"jur": "abc", "lic": "ABC-" + str(r[c_id] if c_id else len(rows)).strip(), "name": dba or holder, "dba": dba, "holder": holder,
                     "keys": _names(dba, holder), "addr": addr, "city": (r[c_city] if c_city else "").strip(),
                     "zip": str(r[c_zip] if c_zip else "")[:5], "county": (r[c_cty] if c_cty else "").strip() or None, "num": num, "street": st,
                     "lat": np.nan, "lon": np.nan, "kind": kind,
                     "active": (not c_status) or bool(re.search(r"(?i)active|issued|renew", str(r[c_status]))),
                     "ltype": (r[c_type] if c_type else "").strip(), "onprem": onprem, "endorse": (r[c_end] if c_end else "").strip(),
                     "expires": str(r[c_exp])[:10] if c_exp else None})
    out = pd.DataFrame(rows)
    return out[out.kind.notna()].reset_index(drop=True)


def load():
    df = load_abc().reset_index(drop=True)
    # one business can hold several licenses (beer, wine and liquor; a restaurant and its bar): same address and a name in common
    df["biz"] = np.arange(len(df))
    town = df.city.fillna("").str.upper().str.strip()
    for num, g in df[df.num.notna() & df.street.notna()].groupby("num"):
        idx = list(g.index)
        if len(idx) < 2:
            continue
        for x in range(len(idx)):
            for y in range(x + 1, len(idx)):
                a, b = idx[x], idx[y]
                if not street_compat(df.at[a, "street"], df.at[b, "street"]):
                    continue
                if not ((df.at[a, "zip"] and df.at[a, "zip"] == df.at[b, "zip"]) or (town[a] and town[a] == town[b])):
                    continue
                ka, kb = df.at[a, "keys"], df.at[b, "keys"]
                if not ka or not kb:
                    continue
                if any(name_sim(p, q) >= 85 or ((_stems(p) - GENERIC) & (_stems(q) - GENERIC)) for p in ka for q in kb):
                    old, new = df.at[b, "biz"], df.at[a, "biz"]
                    df.loc[df.biz == old, "biz"] = new
    return df
