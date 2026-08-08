"""
City-agnostic pipeline orchestrator. Given a city name (from config/cities.yaml),
runs the full UHI + vulnerability pipeline and returns a unified GeoDataFrame.

This is what makes the project multi-city: add a config entry, call run_city(),
done. No per-city code branches outside data_sources/.
"""

import yaml
import pandas as pd
import geopandas as gpd

from src.data_sources.boundaries import get_admin_boundaries
from src.data_sources.demographics import get_demographics
from src.vulnerability import build_vulnerability_index, run_local_morans_i


def load_city_config(city_name: str, config_path: str = "config/cities.yaml") -> dict:
    with open(config_path) as f:
        all_cities = yaml.safe_load(f)["cities"]
    if city_name not in all_cities:
        raise KeyError(f"City '{city_name}' not found in {config_path}. "
                        f"Available: {list(all_cities.keys())}")
    return all_cities[city_name]


def run_city(city_name: str, lst_gdf: gpd.GeoDataFrame, census_api_key: str = None,
             config_path: str = "config/cities.yaml") -> gpd.GeoDataFrame:
    """Run the full pipeline for one city.

    lst_gdf: GeoDataFrame with ['tract_id'-joinable geometry, 'lst_mean', 'canopy_pct',
             'impervious_pct'] already computed upstream (LST + zonal stats happen in
             the Colab notebook, since they need live STAC access). This function
             handles the city-agnostic part: boundaries + demographics + vulnerability
             + clustering.
    """
    city_config = load_city_config(city_name, config_path)

    demo_df = get_demographics(city_config, census_api_key=census_api_key)

    merged = lst_gdf.merge(demo_df, on="tract_id", how="inner")
    merged["city"] = city_config["display_name"]
    merged["country"] = city_config["country"]

    merged = build_vulnerability_index(
        merged, lst_col="lst_mean", elderly_col="pct_elderly", low_income_col="pct_low_income"
    )
    merged = run_local_morans_i(merged, value_col="vulnerability_index")

    # Unified output schema — same columns regardless of source city
    output_cols = ["tract_id", "city", "country", "geometry", "lst_mean", "canopy_pct",
                    "impervious_pct", "pct_elderly", "pct_low_income", "population",
                    "vulnerability_index", "lisa_cluster", "lisa_p_value"]
    return merged[[c for c in output_cols if c in merged.columns]]
