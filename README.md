# Urban Heat Island & Thermal Vulnerability Mapper

Combines Landsat 8/9 thermal imagery with demographic data to quantify Urban
Heat Island intensity and identify statistically significant vulnerability
hotspots.

## Pipeline

1. **`src/lst.py`** — Band 10 DN → TOA radiance → brightness temp → LST (NDVI-derived emissivity)
2. **`src/zonal_correlation.py`** — Zonal stats: LST vs. canopy cover vs. impervious surface, per census tract
3. **`src/vulnerability.py`** — Composite vulnerability index + Local Moran's I (LISA) hot/cold spot clustering
4. **`api/main.py`** — FastAPI endpoint: POST a GeoJSON geometry, get back tract-level metrics

## Setup

```bash
pip install -r requirements.txt
pytest tests/ -v
uvicorn api.main:app --reload
```

## Known Limitations (read before presenting this as production-ready)

- **Single-scene LST is noisy.** Cloud contamination, time-of-day, and season
  all shift results. Production version should composite multiple cloud-free
  summer scenes and report a confidence range, not a point estimate.
- **Vulnerability index weights are equal by default (1/3 each)** — this is a
  starting assumption, not a validated model. Should be calibrated against
  known heat-mortality data or made user-adjustable (see solar siting project
  for the slider pattern).
- **Emissivity model is a simple NDVI threshold approach (NDVI-THM).** More
  accurate methods exist (e.g., ASTER GED) but require additional data sources.
- **No ground-truth validation yet.** Before calling this "production-ready,"
  validate LST output against ground station temperature data for at least
  one AOI.

## Next Steps

- [ ] Wire up Landsat STAC ingestion (currently takes local GeoTIFF paths)
- [ ] Add multi-date compositing for LST
- [ ] Validate against NOAA/local weather station ground truth
- [ ] Deploy FastAPI to Cloud Run / Render with live demo link
- [ ] Add sensitivity analysis on vulnerability index weights
