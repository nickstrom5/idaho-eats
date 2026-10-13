# Idaho Eats: launch steps

Status 2026-10-08. Everything outward-facing waits for Nick's explicit yes, each time. Never submit for review or accept agreements.

## Done
- Sources checked and documented (`12-sources.md`); naming, icon and palette chosen by Nick (`05-naming.md`).
- Pipeline (Overture 2026-09-23.1 + research + James Beard honors), private leaderboard artifact (link in Nick's notes).
- App (`IdahoEats/`, bundle `com.idahoeats.ios`, 1.0.0 (1)) compiles with its unit and UI test targets.
- Website links checked (`pipeline/check_websites.py`).

## Nick
1. **ISP alcohol licenses**: export Licenses.csv from https://apps.isp.idaho.gov/AbcReporting/license/search (Status: Active, then
   Export; county by county if the export caps) into `id-eats/data/raw/official/`. The site's robots.txt keeps automated agents off
   that page, so a person has to do it. Then the session rebuilds: licenses, "serves alcohol", calibration.
2. **GitHub**: yes to create the public repo `nickstrom5/idaho-eats`, push, and turn on Pages from `main` /docs.
3. **Cloudflare**: add `CNAME idaho → nickstrom5.github.io` (DNS only). Switch the site with `ID_DOMAIN=idaho.eatsranked.com` only
   after `dig idaho.eatsranked.com` shows it; then Enforce HTTPS and set the repo's Website field.
4. **eatsranked.com hub**: yes to add Idaho (entry prepared in `playbook/hub/`).
5. **App Store Connect**: register the bundle ID `com.idahoeats.ios` and create the app record "Idaho Eats: Restaurants"
   (the API can't). Then yes to archive with the public Xcode (`DEVELOPER_DIR="/Applications/Xcode 1.app/Contents/Developer"`) and
   upload to TestFlight.
6. **USPTO**: a formal trademark search for "Idaho Eats" (web search found no mark, app or guide).
7. **Screen recording** for App Review from his iPhone (script in `13-app-review-reply.md`), once the TestFlight build is on it.

## Before any submission
- Re-run `pipeline/check_websites.py`, rebuild with `ID_APP=1`, copy `places.json`, re-run unit and UI tests on "ID Eats 6.9" and
  "ID Eats iPad 13", recapture screenshots, re-run `scripts/qa-site.py`.
- Check `DTXcodeBuild` in the archive (public Xcode 27A266a) and bump `CURRENT_PROJECT_VERSION`.
