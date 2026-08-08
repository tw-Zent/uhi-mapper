
"""
Week 4: REST API exposing UHI thermal metrics and vulnerability scores for a
GeoJSON bounding box or point. Run with: uvicorn api.main:app --reload
"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import geopandas as gpd
from shapely.geometry import shape, Point

app = FastAPI(
    title="Urban Heat Island & Thermal Vulnerability API",
    description="Query LST and vulnerability index for a location or bounding box.",
    version="0.1.0",
)

# In production, load once at startup and query via PostGIS instead of in-memory GeoDataFrame.
_TRACTS_GDF: gpd.GeoDataFrame | None = None

# Path to bundled sample data, relative to repo root (Render runs from repo root)
_DEFAULT_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "phoenix_final.geojson")


class GeoQuery(BaseModel):
    geometry: dict  # GeoJSON geometry (Point or Polygon)


class TractMetrics(BaseModel):
    tract_id: str
    lst_mean_c: float
    canopy_pct: float
    impervious_pct: float
    vulnerability_index: float
    lisa_cluster: str


def load_tracts(path: str) -> None:
    global _TRACTS_GDF
    gdf = gpd.read_file(path)
    # Normalize to WGS84 (lat/lon) so incoming GeoJSON queries (also WGS84) intersect correctly
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    if "GEOID" in gdf.columns and "tract_id" not in gdf.columns:
        gdf = gdf.rename(columns={"GEOID": "tract_id"})
    _TRACTS_GDF = gdf


@app.on_event("startup")
def startup_load_default_data():
    """Auto-load the bundled Phoenix dataset on boot, so /query works immediately
    without a manual load_tracts() call. Fails soft — /health will still report
    tracts_loaded: false and /query will 503 with a clear message if the file
    is missing, rather than crashing the whole service."""
    try:
        if os.path.exists(_DEFAULT_DATA_PATH):
            load_tracts(_DEFAULT_DATA_PATH)
            print(f"Loaded {len(_TRACTS_GDF)} tracts from {_DEFAULT_DATA_PATH}")
        else:
            print(f"No default data found at {_DEFAULT_DATA_PATH} — /query will 503 until load_tracts() is called")
    except Exception as e:
        print(f"Failed to load default tracts: {e}")


@app.get("/health")
def health():
    return {"status": "ok", "tracts_loaded": _TRACTS_GDF is not None,
             "tract_count": len(_TRACTS_GDF) if _TRACTS_GDF is not None else 0}


@app.post("/query", response_model=list[TractMetrics])
def query_metrics(q: GeoQuery):
    if _TRACTS_GDF is None:
        raise HTTPException(status_code=503, detail="Tract data not loaded. Call load_tracts() at startup.")

    geom = shape(q.geometry)
    matches = _TRACTS_GDF[_TRACTS_GDF.intersects(geom)]

    if matches.empty:
        raise HTTPException(status_code=404, detail="No tracts found for the given geometry.")

    results = []
    for _, row in matches.iterrows():
        results.append(
            TractMetrics(
                tract_id=str(row.get("tract_id", row.name)),
                lst_mean_c=float(row.get("lst_mean", float("nan"))),
                canopy_pct=float(row.get("canopy_pct", float("nan"))),
                impervious_pct=float(row.get("impervious_pct", float("nan"))),
                vulnerability_index=float(row.get("vulnerability_index", float("nan"))),
                lisa_cluster=str(row.get("lisa_cluster", "Unknown")),
            )
        )
    return results
