# App Store listing (ASO)

Numbers here must match `site-numbers.json`, which `scripts/make-site.py` rewrites from the data on every run. Current (2026-10-09
build): 7 Basque kitchens, 21 finger-steak spots and drive-ins, 9 spud plates, 23 huckleberry places, 12 trout places, 9 taquerías,
14 historic saloons and supper clubs, 10 James Beard honorees, 11 founding years, 87 hand-checked places (80 in the guides),
4,023 restaurants in 192 towns. Update this file after a data refresh.

## Name (30 max)
`Idaho Eats: Restaurants` (23). Nick's pick, 2026-10-08.

## Subtitle (30 max)
`Finger Steaks, Basque & Spuds` (29)

Together, the name and subtitle index: idaho, eats, restaurants, finger, steaks, basque, spuds. Apple also combines them with the keyword
field, so "falls" in keywords plus "idaho" in the name matches "idaho falls" (and "twin falls", "post falls" with their own words).

## Keywords (100 max, commas, no spaces after commas, no words already in the name or subtitle, no trademarks)
`boise,meridian,nampa,coeur d'alene,falls,pocatello,ketchum,sun valley,mccall,huckleberry,trout` (94)

- City and resort names are the biggest win. Twin Falls, Lewiston, Sandpoint and Stanley didn't fit; rotate them in after a month of App
  Store Connect search-term data. "drive-in" was cut for length.
- No "james beard", "best", "top" or "#1" (Guideline 2.3.7). Plurals are unnecessary.
- Apple's search and autocomplete endpoints disallow automated agents in robots.txt, so search-term research was done by hand-chosen
  place names; check them in App Store Connect's analytics after launch.

## Promotional text (170 max, editable any time without review)
`Basque bars, finger steaks with fry sauce, huckleberry shakes and Idaho trout, checked by hand, plus 4,000+ Idaho restaurants. Free, no account, no ads.` (152)

Huckleberry season (switch in late July, when the berries come in):
`Huckleberry season: 23 places for huckleberry shakes, pies and pancakes, checked by hand, sorted by how close they are to you.`

## Description
The first three lines show before "more", so they carry the pitch.

```
Idaho's restaurants, and the finger steaks worth the drive.

Idaho Eats is a free guide to eating in Idaho: Basque kitchens on Boise's Basque Block, finger steaks and drive-ins, spud plates, huckleberry shakes, Idaho trout, taquerías and historic saloons, each checked by hand, plus Idaho's James Beard honorees and 4,023 restaurants, cafés, bars and bakeries in 192 towns. No account, no ads.

IDAHO GUIDES
• Basque: chorizo, solomo and croquetas on Boise's Basque Block, and Basque kitchens elsewhere.
• Finger Steaks & Drive-Ins: battered strips of steak with fry sauce, and drive-in burgers.
• Spud Plates: potato specialties on the menu, from loaded bakers to the Pioneer Saloon's Jim Spud.
• Huckleberry: shakes, pies and pancakes, mostly in North Idaho and the mountains.
• Idaho Trout: rainbow trout from the Magic Valley and beyond.
• Taquerías: from Nampa and Caldwell to Burley.
• Historic Saloons: old bars and supper clubs from Wallace to Stanley.
• James Beard Honors: winners, nominees, semifinalists and America's Classics, as facts.
• Oldest Places: founding years checked at the same address, oldest first.

FIND IT FAST
• Sort by distance, or browse the map by guide.
• Search by name, town, street or dish: "finger steaks boise", "huckleberry shake", "basque".
• Filter by town or cuisine, hide chains.
• Save places for your next trip.
• Find hand-checked and honored places from iPhone search (Spotlight).

LIVE DETAILS FROM APPLE MAPS
Tap "Ratings, hours & photos" on any place to open Apple Maps' own place card, with current hours, photos, ratings and directions.

HOW THE LISTS ARE BUILT
Every place in a guide was checked by hand in fall 2026 against a 2025 or 2026 source: the place's own website or menu, or local news. The rest of the restaurants come from Overture Maps open data, kept by a reliability rule tested against a full city list of licensed food businesses (Denver's, for the same map data). Website links are checked too: each must be the restaurant's own page. Idaho's health districts don't publish inspection results in bulk, so each place links its district's own lookup instead. Nothing is ranked by star ratings.

PRIVATE BY DESIGN
No account, no tracking, no ads. Your location, if you share it, only sorts lists on your device. Saved places stay on your device.

Places open and close, and resort towns close between seasons, so check before you go. Spot a mistake? Email nick@eatsranked.com.

An independent app, not affiliated with any restaurant, team, university, chain or government agency, or the James Beard Foundation. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation. Place data from Overture Maps Foundation (CDLA Permissive 2.0) and others; sources and licenses are on the About tab.
```
(Add "Idaho State Police alcohol licenses" to HOW THE LISTS ARE BUILT once the ABC export is in the data.)

## What's New (1.0)
`First release. Basque, finger steaks, spud plates, huckleberry, trout, James Beard honorees and 4,000+ Idaho restaurants.`

## Screenshots
Upload in this order, one file at a time (a multi-file upload lands in random order); the first three show in search results.
No negative boards in any App Store image (Idaho has no inspection results, so none can appear).

| # | File (iPhone 6.9" / iPad 13") | Caption to overlay (optional) |
|---|---|---|
| 1 | `home.png` / `ipad-home.png` | 4,000+ Idaho restaurants |
| 2 | `basque.png` / `ipad-basque.png` | Basque, nearest first |
| 3 | `detail.png` / `ipad-detail.png` | Live hours & photos from Apple Maps |
| 4 | `map.png` / `ipad-map.png` | The map, by guide |
| 5 | `fingersteaks.png` / `ipad-fingersteaks.png` | Finger steaks & drive-ins |
| 6 | `honors.png` / `ipad-honors.png` | James Beard honorees |
| 7 | `huckleberry.png` / `ipad-huckleberry.png` | Huckleberry, checked by hand |
| 8 | `oldest.png` / `ipad-oldest.png` | The oldest places |

## Category
Primary Food & Drink, secondary Travel.

## Age rating
Alcohol references "Infrequent" (saloons, bars), which gives 13+; everything else "None" or "No".

## App Review notes
Paste the reply from `13-app-review-reply.md` into App Review Information → Notes. "Sign-in required": unticked (no login).
