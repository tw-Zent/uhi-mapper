"""
Week 2: Zonal statistics linking LST to tree canopy cover and built-up (impervious)
surface percentage, per census tract / neighborhood polygon.
"""

import geopandas as gpd
import pandas as pd
from rasterstats import zonal_stats


def compute_zonal_lst(tracts_path: str, lst_raster_path: str) -> gpd.GeoDataFrame:
    """Mean/std/min/max LST per tract polygon."""
    tracts = gpd.read_file(tracts_path)
    stats = zonal_stats(tracts, lst_raster_path, stats=["mean", "std", "min", "max"], nodata="nan")
    stats_df = pd.DataFrame(stats).add_prefix("lst_")
    return pd.concat([tracts.reset_index(drop=True), stats_df], axis=1)


def compute_zonal_canopy(tracts_gdf: gpd.GeoDataFrame, canopy_raster_path: str) -> gpd.GeoDataFrame:
    """Mean tree canopy % per tract, assuming a 0-100 canopy cover raster."""
    stats = zonal_stats(tracts_gdf, canopy_raster_path, stats=["mean"], nodata=-9999)
    tracts_gdf["canopy_pct"] = [s["mean"] for s in stats]
    return tracts_gdf


def compute_zonal_impervious(tracts_gdf: gpd.GeoDataFrame, impervious_raster_path: str) -> gpd.GeoDataFrame:
    """Mean impervious surface % per tract."""
    stats = zonal_stats(tracts_gdf, impervious_raster_path, stats=["mean"], nodata=-9999)
    tracts_gdf["impervious_pct"] = [s["mean"] for s in stats]
    return tracts_gdf


def correlation_summary(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Pearson correlation between mean LST, canopy %, and impervious %."""
    cols = ["lst_mean", "canopy_pct", "impervious_pct"]
    missing = [c for c in cols if c not in gdf.columns]
    if missing:
        raise ValueError(f"Missing columns for correlation: {missing}")
    return gdf[cols].corr()
