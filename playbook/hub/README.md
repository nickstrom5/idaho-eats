# Adding Idaho to the eatsranked.com hub (not done: needs Nick's OK, and it's another repo)

The hub lives in `../eatsranked/` (repo nickstrom5/eatsranked). This session only works in `id-eats/`, so the change is prepared here:
1. Append `eatsranked-entry.json` to `"states"` in `eatsranked/tools/site-data.json`.
2. Copy `idaho.png` to `eatsranked/docs/icons/idaho.png` (check the size the other icons use).
3. Run `eatsranked/tools/build.py`, check (white text on huckleberry #4B2A5C is 11.8:1; russet #C9A06B is a fill/accent only), then commit and
   push with the no-reply email (Nick's yes first).
When idaho.eatsranked.com resolves, change the four github.io URLs to https://idaho.eatsranked.com/.
