"""Download the Overture Maps extracts that idaho.py reads -> data/id/

- overture_id_bbox.parquet     every place in Idaho's bounding box (name, category, address, point)
- overture_id_sources.parquet  which datasets each Idaho eating/drinking listing came from (Meta, Foursquare, ...)
- id_shapes.json               simplified state and county outlines for the map
- id_state_detail.geojson      the state outline at full detail, for the in-state test (drops Spokane, Pullman, Ontario, Jackson rows)
- id_counties_detail.geojson   county polygons for assigning each place to a county (not shipped)
- addresses_id.parquet         Overture address points statewide, to place ISP ABC liquor licenses (they have no coordinates)
- localities_id.json           city outlines (Boise, Meridian, ...) for calibration areas

Reads the public Overture bucket over S3 with DuckDB (no account needed). Adapted from co-eats/pipeline/fetch_overture.py and
fetch_extras.py.
"""
import os, json, time
import duckdb
from shapely import wkb
from shapely.geometry import mapping

RELEASE = "2026-09-23.1"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "id")
# Idaho (42°N–49°N, 111°03'W–117°14'W) plus a margin for border towns (dropped later by the state polygon)
BBOX = "bbox.xmin BETWEEN -117.4 AND -110.9 AND bbox.ymin BETWEEN 41.9 AND 49.1"
EAT = "('restaurant','casual_eatery','bar','fast_food_restaurant','coffee_shop','cafe','smoothie_juice_bar','brewery','food_court')"
os.makedirs(OUT, exist_ok=True)

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
places = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=places/type=place/*.parquet"

t = time.time()
if not os.path.exists(f"{OUT}/overture_id_bbox.parquet"):
    con.execute(f"""
COPY (
  SELECT id, names.primary AS name, basic_category AS cat, taxonomy.primary AS tax, taxonomy.hierarchy AS hier, confidence,
         operating_status AS status, brand.names.primary AS brand, addresses[1].freeform AS street, addresses[1].locality AS city,
         addresses[1].postcode AS zip, addresses[1].region AS region, ST_Y(geometry) AS lat, ST_X(geometry) AS lon, websites[1] AS web,
         phones[1] AS phone
  FROM read_parquet('{places}', hive_partitioning=1) WHERE {BBOX}
) TO '{OUT}/overture_id_bbox.parquet' (FORMAT PARQUET)""")
    print("places in bbox", round(time.time() - t), "s", flush=True)
if not os.path.exists(f"{OUT}/overture_id_sources.parquet"):
    con.execute(f"""
COPY (
  SELECT id, list_transform(sources, x -> x.dataset) AS ds, list_transform(sources, x -> x.update_time) AS ut,
         list_transform(sources, x -> x.record_id) AS rid,
         len(socials) AS n_soc, len(websites) AS n_web, len(phones) AS n_ph
  FROM read_parquet('{places}', hive_partitioning=1)
  WHERE {BBOX} AND basic_category IN {EAT}
) TO '{OUT}/overture_id_sources.parquet' (FORMAT PARQUET)""")
    print("sources", round(time.time() - t), "s", flush=True)

areas = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=divisions/type=division_area/*.parquet"
rows = con.execute(f"""
  SELECT subtype, class, names.primary AS name, ST_AsWKB(geometry) AS g
  FROM read_parquet('{areas}', hive_partitioning=1)
  WHERE country = 'US' AND region = 'US-ID' AND subtype IN ('region', 'county', 'locality')
    AND bbox.xmin > -117.6 AND bbox.xmax < -110.7 AND bbox.ymin > 41.7 AND bbox.ymax < 49.3""").fetchall()


def rings(geom, tol, min_area):
    geom = geom.simplify(tol, preserve_topology=True)
    polys = [p for p in getattr(geom, "geoms", [geom]) if p.geom_type == "Polygon" and p.area >= min_area]
    return [[[round(x, 3), round(y, 3)] for x, y in p.exterior.coords] for p in polys]


out = {"state": None, "counties": []}
for sub, cls, name, g in rows:
    if cls != "land" or sub == "locality":
        continue
    geom = wkb.loads(bytes(g)).buffer(0)
    if sub == "region":
        json.dump(mapping(geom.simplify(0.0005, preserve_topology=True)), open(f"{OUT}/id_state_detail.geojson", "w"))
        out["state"] = [[r] for r in rings(geom, 0.002, 0.0002)]
    else:
        out["counties"].append({"name": name, "c": rings(geom, 0.004, 0.0005)})
json.dump({name: mapping(wkb.loads(bytes(g)).buffer(0).simplify(0.0003, preserve_topology=True))
           for sub, cls, name, g in rows if sub == "county" and cls == "land"}, open(f"{OUT}/id_counties_detail.geojson", "w"))
json.dump(out, open(f"{OUT}/id_shapes.json", "w"), separators=(",", ":"))
json.dump({name: mapping(wkb.loads(bytes(g)).buffer(0).simplify(0.0002, preserve_topology=True))
           for sub, cls, name, g in rows if sub == "locality" and cls == "land"}, open(f"{OUT}/localities_id.json", "w"))
print("outlines: state", len(out["state"] or []), "rings +", len(out["counties"]), "counties;",
      sum(1 for r in rows if r[0] == "locality"), "localities;", round(time.time() - t), "s", flush=True)

if not os.path.exists(f"{OUT}/addresses_id.parquet"):
    addr = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=addresses/type=address/*.parquet"
    con.execute(f"""COPY (SELECT number, street, unit, postcode, postal_city, address_levels[1].value AS state,
      address_levels[-1].value AS muni, ST_Y(geometry) lat, ST_X(geometry) lon FROM read_parquet('{addr}', hive_partitioning=1)
      WHERE country = 'US' AND bbox.xmin BETWEEN -117.3 AND -111.0 AND bbox.ymin BETWEEN 41.95 AND 49.05)
      TO '{OUT}/addresses_id.parquet' (FORMAT PARQUET)""")
    print(con.execute(f"select count(*), count(*) filter (where state='ID') from '{OUT}/addresses_id.parquet'").fetchall(),
          round(time.time() - t), "s", flush=True)
