"""
Fetch admin boundaries (census tracts / equivalent) for any city, dispatching
to the right source based on city config. Adding a new country's boundary
source means adding one function here — pipeline.py never changes.
"""

import geopandas as gpd
import requests
import zipfile
import io


def get_admin_boundaries(city_config: dict) -> gpd.GeoDataFrame:
    """Unified entry point. Returns a GeoDataFrame with at minimum:
    ['tract_id', 'geometry'] columns, regardless of source country.
    """
    source = city_config["boundary_source"]
    if source == "tiger":
        return _fetch_tiger_tracts(city_config)
    elif source == "gadm":
        return _fetch_gadm_boundaries(city_config)
    else:
        raise ValueError(f"Unknown boundary_source: {source}")


def _fetch_tiger_tracts(city_config: dict) -> gpd.GeoDataFrame:
    """US Census TIGER/Line tracts, filtered to the target county."""
    params = city_config["boundary_params"]
    state_fips = params["state_fips"]
    county_fips = params["county_fips"]
    year = params.get("year", 2023)

    url = f"https://www2.census.gov/geo/tiger/TIGER{year}/TRACT/tl_{year}_{state_fips}_tract.zip"
    resp = requests.get(url)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        z.extractall(f"/tmp/tiger_{state_fips}")

    gdf = gpd.read_file(f"/tmp/tiger_{state_fips}/tl_{year}_{state_fips}_tract.shp")
    gdf = gdf[gdf["COUNTYFP"] == county_fips].copy()
    gdf = gdf.rename(columns={"GEOID": "tract_id"})
    return gdf[["tract_id", "geometry"]]


def _fetch_gadm_boundaries(city_config: dict) -> gpd.GeoDataFrame:
    """Global admin boundaries via GADM (works for any country, e.g. India).
    Uses GADM's GeoPackage distribution, clipped to the city bbox.
    """
    params = city_config["boundary_params"]
    country_code = params["country_code"]
    level = params.get("gadm_level", 3)

    url = f"https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg/gadm41_{country_code}.gpkg"
    gdf = gpd.read_file(url, layer=f"ADM_ADM_{level}")

    bbox = city_config["bbox"]
    gdf = gdf.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]].copy()

    id_col = f"GID_{level}"
    gdf = gdf.rename(columns={id_col: "tract_id"})
    return gdf[["tract_id", "geometry"]]
