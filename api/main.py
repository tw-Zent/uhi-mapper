"""
Week 4: REST API exposing UHI thermal metrics and vulnerability scores for a
GeoJSON bounding box or point. Run with: uvicorn api.main:app --reload
"""

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
    _TRACTS_GDF = gpd.read_file(path)


@app.get("/health")
def health():
    return {"status": "ok", "tracts_loaded": _TRACTS_GDF is not None}


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
