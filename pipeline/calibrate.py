"""How often is a map listing a real restaurant? Idaho's measurements -> data/id/calibration.json and calibration_app.json

Adapted from co-eats/pipeline/calibrate.py. Idaho has no Denver-style list of every licensed food business: no health district
publishes its permits or inspections in bulk. What we can measure here:
- Statewide, district by district and county by county: the share of cleaned, open listings that match an on-premises ISP ABC
  license (liquor by the drink, or beer/wine for consumption there), by listing source. Many restaurants hold no alcohol license, so
  these are lower bounds that compare sources; they don't measure them. The other direction (licensed bars and restaurants found
  among the listings) is a real coverage number.
- Web build only: the share of each source group that Google's Sep 2021 snapshot also lists as open (corroboration, not proof).
- For reference, Colorado's full-list measurement (Denver's food licenses, same Overture release 2026-09-23.1), read from
  ../co-eats/data/co/calibration_app.json when it exists. Nothing in co-eats is modified.
A match is the same business name nearby, or the same street address with a distinctive name word in common.
"""
import json, os
import numpy as np, pandas as pd
from common import ID, ROOT
from listings_util import official_match

o = pd.read_pickle(f"{ID}/stage1.pkl")
F = pd.read_pickle(f"{ID}/official.pkl") if os.path.exists(f"{ID}/official.pkl") else pd.DataFrame()
DISTRICTS = {"Panhandle (1)": "Benewah Bonner Boundary Kootenai Shoshone", "North Central (2)": "Clearwater Idaho Latah Lewis Nez_Perce",
             "Southwest (3)": "Adams Canyon Gem Owyhee Payette Washington", "Central (4)": "Ada Boise Elmore Valley",
             "South Central (5)": "Blaine Camas Cassia Gooding Jerome Lincoln Minidoka Twin_Falls",
             "Southeastern (6)": "Bannock Bear_Lake Bingham Butte Caribou Franklin Oneida Power",
             "Eastern (7)": "Bonneville Clark Custer Fremont Jefferson Lemhi Madison Teton"}
C2D = {f"{c.replace('_', ' ')} County": d for d, cs in DISTRICTS.items() for c in cs.split()}
o["district"] = o.county.map(C2D)
base = ~o.j_junk & ~o.j_outside & ~o.ov_closed & ~o.j_closedname
L = o[base & o.county.notna()].reset_index(drop=True)


def groups(L):
    s, conf = L.src.fillna("none"), L.confidence.fillna(0)
    web = L.n_web.fillna(0) > 0
    return np.select([(s == "meta") & (conf >= 0.95), (s == "meta") & (conf >= 0.9) & web, (s == "meta") & (conf >= 0.9),
                      s.isin(["AllThePlaces", "DAC"]), (s == "BrightQuery") & (conf >= 0.95), s == "meta", s == "Foursquare", s == "BrightQuery",
                      s == "Microsoft"],
                     ["meta >= 0.95", "meta 0.90-0.95 + website", "meta 0.90-0.95, no website", "brand feed", "BrightQuery >= 0.95",
                      "meta < 0.90", "Foursquare only", "BrightQuery < 0.95", "Microsoft only"], "other")


L["grp"] = groups(L)
APP_KEEP = {"meta >= 0.95", "meta 0.90-0.95 + website", "brand feed"}
out = {"listings": int(len(L)), "groups": {}, "per_district": {}, "per_county": {}}
g21 = L.groupby("grp").agg(n=("id", "size"), google21_open=("in21", lambda s_: float((s_ & ~L.loc[s_.index, "closed21"]).mean())))
for g, r in g21.iterrows():
    out["groups"][g] = {"n": int(r.n), "google21_open": round(float(r.google21_open), 3), "app_keep": g in APP_KEEP}
print(f"== {len(L)} cleaned, open listings; share Google 2021 also lists as open, by source group")
print(g21.assign(google21_open=(g21.google21_open * 100).round(1)).sort_values("n", ascending=False).to_string())

if len(F):
    LQ = F[F.jur.eq("abc") & F.kind.isin(["restaurant", "bar", "brewery"]) & F.lat.notna()].reset_index(drop=True)
    LQ["district"] = LQ.county.map(lambda c: C2D.get(c) if isinstance(c, str) else None)
    m = {}
    for cty, sel in L.groupby("county").groups.items():
        R = LQ[LQ.county == cty]
        if not len(R):
            continue
        sub = L.loc[sel].reset_index(drop=True)
        for i, j in official_match(sub, R.reset_index(drop=True)).items():
            m[sel[i]] = R.index[j]
    L["abc"] = L.index.map(lambda i: i in m)
    found = {LQ.biz.iat[j] for j in m.values()}
    bygrp = L.groupby("grp").abc.agg(["size", "mean"])
    print("\n== matched to an on-premises ABC license, by source group (a lower bound)")
    print(bygrp.assign(mean=(bygrp["mean"] * 100).round(1)).to_string())
    for g, r in bygrp.iterrows():
        out["groups"][g]["abc_onprem"] = round(float(r["mean"]), 3)
    for key, col in (("per_district", "district"), ("per_county", "county")):
        per = L.groupby(col).agg(listings=("id", "size"), app_rule=("grp", lambda s_: int(s_.isin(APP_KEEP).sum())), abc_match=("abc", "mean"))
        lic = LQ.drop_duplicates("biz").groupby(col).biz.agg(lambda b: (len(b), float(np.mean([x in found for x in b]))))
        per["abc_onprem_businesses"] = [lic.get(c, (0, None))[0] for c in per.index]
        per["abc_found_in_listings"] = [lic.get(c, (0, None))[1] for c in per.index]
        out[key] = {c: {k: (round(float(v), 3) if isinstance(v, float) else (int(v) if v == v and v is not None else None)) for k, v in r.items()}
                    for c, r in per.iterrows()}
        if key == "per_district":
            print("\n== per district\n" + per.round(3).to_string())
    out["abc_onprem_businesses"] = int(LQ.biz.nunique())
    out["abc_found_in_listings"] = round(len(found) / max(1, LQ.biz.nunique()), 3)
    out["abc_unplaced"] = int((F.jur.eq("abc") & F.lat.isna()).sum())
    print("ABC on-premises businesses found among the listings:", out["abc_found_in_listings"], "of", out["abc_onprem_businesses"])
else:
    per = L.groupby("district").agg(listings=("id", "size"), app_rule=("grp", lambda s_: int(s_.isin(APP_KEEP).sum())))
    out["per_district"] = {c: {k: int(v) for k, v in r.items()} for c, r in per.iterrows()}
    out["abc_note"] = "No ISP ABC export in data/raw/official yet: license matching not measured."
    print("\n(no ABC export yet: license calibration skipped)\n" + per.to_string())

co = os.path.join(ROOT, "..", "co-eats", "data", "co", "calibration_app.json")
if os.path.exists(co):
    den = json.load(open(co)).get("Denver", {})
    out["reference_colorado_denver"] = {"note": "Colorado's measurement against Denver's full food-license list, same Overture release",
                                        "groups": den.get("groups"), "listings": den.get("listings")}
json.dump(out, open(f"{ID}/calibration.json", "w"), indent=1)
json.dump(out, open(f"{ID}/calibration_app.json", "w"), indent=1)
