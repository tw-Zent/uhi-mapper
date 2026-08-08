"""
Fetch real Landsat 8/9 scenes + census tract boundaries for Phoenix, AZ.

RUN THIS LOCALLY, not in a restricted sandbox — needs open internet access to
USGS/AWS and the Census Bureau.

Setup:
    pip install pystac-client planetary-computer rasterio requests geopandas

Usage:
    python fetch_real_data.py
"""

import requests
from pystac_client import Client
import planetary_computer as pc

# ---- 1. Landsat scene search (Microsoft Planetary Computer STAC, free, no auth needed) ----

PHOENIX_BBOX = [-112.20, 33.30, -111.90, 33.60]  # west, south, east, north

def fetch_landsat_scene(bbox=PHOENIX_BBOX, date_range="2024-06-01/2024-08-31", max_cloud=10):
    """Find a low-cloud summer Landsat 8/9 scene over Phoenix and return signed asset URLs."""
    catalog = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")

    search = catalog.search(
        collections=["landsat-c2-l2"],
        bbox=bbox,
        datetime=date_range,
        query={"eo:cloud_cover": {"lt": max_cloud}, "platform": {"in": ["landsat-8", "landsat-9"]}},
    )

    items = list(search.items())
    if not items:
        raise RuntimeError("No low-cloud scenes found — widen date_range or raise max_cloud.")

    # Pick the clearest scene
    item = min(items, key=lambda i: i.properties.get("eo:cloud_cover", 100))
    signed = pc.sign(item)

    print(f"Selected scene: {item.id}, cloud cover: {item.properties.get('eo:cloud_cover')}%")
    return {
        "band10_thermal": signed.assets["lwir11"].href,  # TIRS Band 10, ST or L2 thermal
        "red": signed.assets["red"].href,
        "nir": signed.assets["nir08"].href,
        "mtl_metadata": signed.assets.get("mtl.txt", signed.assets.get("mtl.json")).href if "mtl.txt" in signed.assets or "mtl.json" in signed.assets else None,
        "item_id": item.id,
    }


# ---- 2. Census tract boundaries (US Census TIGER/Line, free, no auth) ----

MARICOPA_COUNTY_FIPS = "04013"  # Maricopa County, AZ (contains Phoenix)

def fetch_census_tracts(county_fips=MARICOPA_COUNTY_FIPS, year=2023, out_path="data/maricopa_tracts.zip"):
    """Download census tract TIGER/Line shapefile for Maricopa County."""
    state_fips = county_fips[:2]
    url = f"https://www2.census.gov/geo/tiger/TIGER{year}/TRACT/tl_{year}_{state_fips}_tract.zip"
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"Downloaded census tracts to {out_path} (filter to county FIPS {county_fips} after loading)")
    return out_path


# ---- 3. Demographic data (Census ACS 5-year estimates, free, no auth for low-volume use) ----

def fetch_acs_demographics(county_fips=MARICOPA_COUNTY_FIPS, year=2022):
    """Pull elderly % and low-income % per tract from Census ACS API."""
    state_fips, county = county_fips[:2], county_fips[2:]
    # B01001: age/sex; B19013: median household income
    url = (
        f"https://api.census.gov/data/{year}/acs/acs5"
        f"?get=NAME,B01001_020E,B01001_021E,B19013_001E"
        f"&for=tract:*&in=state:{state_fips}+county:{county}"
    )
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    print("Fetching Landsat scene...")
    scene = fetch_landsat_scene()
    print(scene)

    print("\nFetching census tracts...")
    fetch_census_tracts()

    print("\nFetching ACS demographics...")
    demo = fetch_acs_demographics()
    print(f"Retrieved {len(demo) - 1} tract records")
