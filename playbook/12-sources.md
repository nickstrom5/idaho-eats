# Idaho official sources (checked 2026-10-08)

Every host below was robots-checked with `pipeline/check_sources.py` (RFC 9309 matcher: agent group, longest match, `*` and `$`).
"Usable" means its robots.txt lets ClaudeBot, Claude-User and anthropic-ai fetch that path and it didn't answer with a bot check.

## Inspections: none in bulk, no official grade

| District | Counties | What it publishes | Bulk | Robots |
|---|---|---|---|---|
| 1 Panhandle Health District | Benewah, Bonner, Boundary, Kootenai, Shoshone | Food page links a legacy search (www2.phd1.idaho.gov/Foodsearch, data from July 2016) that doesn't answer | no | site ok; legacy host unreachable |
| 2 Public Health – Idaho North Central District | Clearwater, Idaho, Latah, Lewis, Nez Perce | id.healthinspections.us/idaho/food/ ("Digital Health Department"): one establishment per page, violation items, no score | no | usable (not scraped) |
| 3 Southwest District Health | Adams, Canyon, Gem, Owyhee, Payette, Washington | Nothing online | — | — |
| 4 Central District Health | Ada, Boise, Elmore, Valley | Accela Citizen Access (aca-prod.accela.com/CDH), one search at a time | no | usable (not scraped) |
| 5 South Central Public Health District | Blaine, Camas, Cassia, Gooding, Jerome, Lincoln, Minidoka, Twin Falls | HedgehogPortal (info.phd5.id.gov), linked from phd5.idaho.gov/inspections/ | no | **HedgehogPortal disallows Claude**: never fetched |
| 6 Southeastern Idaho Public Health | Bannock, Bear Lake, Bingham, Butte, Caribou, Franklin, Oneida, Power | inspectionsonline.us (Lotus Notes search) | no | usable (not scraped) |
| 7 Eastern Idaho Public Health | Bonneville, Clark, Custer, Fremont, Jefferson, Lemhi, Madison, Teton | inspectionsonline.us | no | usable (not scraped) |

No district issues a letter grade, placard or 0–100 score. The inspectionsonline.us "Score (RF)/Score (GRP)" columns count risk-factor
and good-retail-practice violations; they aren't grades. So there are **no inspection boards or results**; the app links each place's
district lookup. A statewide extract would need a public records request (Idaho Code Title 74), which needs Nick's yes.

Map listings per district (Overture 2026-09-23.1, cleaned and open): Panhandle 1,334, North Central 498, Southwest 938, Central 2,559,
South Central 995, Southeastern 660, Eastern 1,019 (8,003 statewide).

## Alcohol licenses: Idaho State Police, Alcohol Beverage Control
- apps.isp.idaho.gov/AbcReporting/license/search (public, no login) has an Export to Licenses.csv, but robots.txt says
  `User-agent: *` / `Disallow: /AbcReporting/*/search`, which covers the search and its export. Python's urllib.robotparser ignores the
  wildcard; our checker doesn't. No static list exists on isp.idaho.gov/abc/ (licensing, resources, FAQ checked).
- Decision (Nick, 2026-10-08): he exports the CSV himself in his browser into data/raw/official/. Licensee names are never shown.
- Renewals are staggered by county (ISP's "County Codes & Expiration Dates" PDF): e.g. Latah, Lewis, Clearwater, Idaho, Nez Perce 1/31;
  Kootenai, Benewah 2/28; Ada 4/30; Canyon, Owyhee, Payette 5/31; Twin Falls, Gooding, Jerome, Lincoln, Camas 6/30; Blaine, Cassia,
  Minidoka, Butte, Power 7/31; Lemhi, Custer, Boise, Valley 8/31; Bonneville, Madison, Jefferson, Teton, Fremont, Clark, Elmore 9/30;
  Bannock, Bingham, Bear Lake, Caribou, Franklin, Oneida 10/31; Bonner, Boundary, Shoshone 11/30; Adams, Gem, Washington 12/31.
  (The prompt's "every 7/31" was wrong.)
- Cities and counties license alcohol too (Boise's City Clerk issues a Food and Beverage License to every restaurant), but none
  publishes a list.

## Property values
- Ada County Parcel Boundaries (ArcGIS item c3c3a02008e7433a860938d693eba7b0, AdaCountyGIS): license **CC0**; `TOTALVALUE` is land plus
  buildings. Not used in v1.
- OIT "Public Idaho Parcels" (item 65a3f7c6d4ca404ba6ab677913953b35): 13 participating counties; terms grant no redistribution right and
  bar mailing-list use (Idaho Code §74-120). Not used.

## Map listings
Overture Maps places 2026-09-23.1 (latest on 2026-10-08), bbox -117.4..-110.9 / 41.9..49.1, kept by region = ID and the state outline
(drops Spokane, Pullman, Ontario, Jackson rows). 8,128 eating/drinking listings with region ID; Meta 5,423 (3,110 at confidence ≥ 0.95).

## Calibration
No complete official list exists in Idaho, so each source group is measured by how often Google's Sep 2021 snapshot also lists it as
open (web build only; the app ships no such number) and, once the ABC export is in, by on-premises license matches (a lower bound).
Colorado's full-list test against Denver's food licenses (same Overture release) sets the keep rule: Meta ≥ 0.95 matched 76%,
Meta 0.90–0.95 32%, Meta < 0.90 20%, Foursquare-only 14%.

| Group | Listings | Open in Google 2021 |
|---|---|---|
| Meta ≥ 0.95 | 3,090 | 70.6% |
| Meta 0.90–0.95 with a website | 843 | 49.5% |
| Meta 0.90–0.95, no website | 343 | 21.9% |
| Meta < 0.90 | 1,091 | 4.5% |
| Brand feeds (AllThePlaces, DAC) | 291 | 29.2% (many opened after 2021) |
| BrightQuery ≥ 0.95 | 475 | 41.7% |
| Foursquare only | 942 | 25.7% |
| Microsoft only | 522 | 40.8% |

App keep rule (as Colorado): Meta ≥ 0.95, Meta 0.90–0.95 with a website, brand feeds, official or hand-checked. The web leaderboard
also drops Meta < 0.90 unless Google 2021, a license or the research backs it.

## Honors
- James Beard Foundation (jamesbeard.org story pages, 2023–2026): 10 Idaho restaurants, all open (data/research/jbf.json,
  honors_notes.md). Winners: Kris Komori (KIN, Boise) Best Chef: Mountain 2023; Salvador Alamilla (Amano, Caldwell) Best Chef: Mountain
  2025. America's Classics: The Pioneer Saloon, Ketchum (2025). 2026 nominees: Ansots (Outstanding Hospitality), Bar, Please! (Best New
  Bar); neither won. Amano moved to 802 Arthur St, Caldwell.
- MICHELIN: no Idaho guide (michelinmedia.com's Oct 8, 2026 list of North American destinations; guide.michelin.com answers us with a
  bot challenge and isn't fetched).

## Benchmarks not used
BLS QCEW (data.bls.gov) disallows Claude in robots.txt, so its 2025 count (4,645 private NAICS 722 establishments, from the prompt) isn't
fetched or cited in anything public.
