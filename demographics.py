"""
Fetch demographic data (elderly %, low-income %, population) for any city,
dispatching to the right source based on city config.

Output schema is always: ['tract_id', 'pct_elderly', 'pct_low_income', 'population']
regardless of source, so downstream vulnerability index code never changes.
"""

import pandas as pd
import requests


def get_demographics(city_config: dict, census_api_key: str = None) -> pd.DataFrame:
    """Unified entry point. Returns a DataFrame with:
    ['tract_id', 'pct_elderly', 'pct_low_income', 'population']
    """
    source = city_config["demographic_source"]
    if source == "census_acs":
        return _fetch_census_acs(city_config, census_api_key)
    elif source == "worldpop":
        return _fetch_worldpop(city_config)
    else:
        raise ValueError(f"Unknown demographic_source: {source}")


def _fetch_census_acs(city_config: dict, census_api_key: str) -> pd.DataFrame:
    """US Census ACS 5-year estimates. US cities only."""
    if not census_api_key:
        raise ValueError("census_api_key required for census_acs source")

    params = city_config["demographic_params"]
    state_fips, county_fips, year = params["state_fips"], params["county_fips"], params["year"]

    elderly_cols = ["B01001_020E","B01001_021E","B01001_022E","B01001_023E","B01001_024E","B01001_025E",
                     "B01001_044E","B01001_045E","B01001_046E","B01001_047E","B01001_048E","B01001_049E"]

    url1 = (f"https://api.census.gov/data/{year}/acs/acs5"
            f"?get=NAME,{','.join(elderly_cols)},B01001_001E"
            f"&for=tract:*&in=state:{state_fips}+county:{county_fips}&key={census_api_key}")
    url2 = (f"https://api.census.gov/data/{year}/acs/acs5"
            f"?get=NAME,B17001_002E,B17001_001E"
            f"&for=tract:*&in=state:{state_fips}+county:{county_fips}&key={census_api_key}")

    r1 = requests.get(url1); r1.raise_for_status()
    r2 = requests.get(url2); r2.raise_for_status()

    df1 = pd.DataFrame(r1.json()[1:], columns=r1.json()[0])
    df2 = pd.DataFrame(r2.json()[1:], columns=r2.json()[0])
    df = df1.merge(df2, on=["state", "county", "tract", "NAME"])

    numeric_cols = [c for c in df.columns if c.startswith(("B0", "B1"))]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

    df["pct_elderly"] = 100 * df[elderly_cols].sum(axis=1) / df["B01001_001E"]
    df["pct_low_income"] = 100 * df["B17001_002E"] / df["B17001_001E"]
    df["population"] = df["B01001_001E"]
    df["tract_id"] = df["state"] + df["county"] + df["tract"]

    return df[["tract_id", "pct_elderly", "pct_low_income", "population"]]


def _fetch_worldpop(city_config: dict) -> pd.DataFrame:
    """WorldPop gridded population/age data — global default for non-US cities.

    NOTE: WorldPop provides gridded rasters (population count, age structure),
    not pre-aggregated tract tables. This requires zonal-stats aggregation to
    tract polygons (from boundaries.py) rather than a direct API table pull.
    Implementation stub — wire up to actual tract geometries at call time
    via WorldPop's REST API (https://www.worldpop.org/rest/data) or hub
    GeoTIFF downloads, then zonal_stats against the same tracts used
    elsewhere in the pipeline.

    pct_low_income has no consistent global equivalent from WorldPop alone —
    for non-US cities, this should be substituted with a locally-appropriate
    proxy (e.g. nightlight-derived poverty index, or omitted with a documented
    limitation) rather than faked as directly comparable to US Census figures.
    """
    raise NotImplementedError(
        "WorldPop integration is stubbed — implement zonal aggregation against "
        "city boundaries and document the pct_low_income proxy choice before "
        "using for a non-US city."
    )
