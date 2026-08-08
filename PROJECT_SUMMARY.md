# Project Summary & Handoff — Phoenix UHI & Thermal Vulnerability Mapper

**Purpose of this doc:** full technical context for anyone picking up this project cold — what's built, how it works, what's real vs. stubbed, and every gotcha hit along the way. Written for a developer, not a hiring manager (see `PORTFOLIO_WRITEUP.md` for that framing).

---

## 1. What this project is

Part of a 3-project climate tech portfolio (UHI Mapper → Forest Carbon MRV → Solar/Wind Siting, in that build order). This is project #1, the anchor piece, chosen for scientific rigor + FastAPI deployment differentiation.

**Live artifacts:**
- Code: `github.com/tw-Zent/uhi-mapper` (public)
- API: `https://uhi-mapper-api.onrender.com` (Render free tier)
- Interactive map: `https://gvxadwr9clucdhef.streamlit.app` (Streamlit Community Cloud free tier)
- Both free-tier services sleep after inactivity — first request after idle takes 30-50s to wake.

**Built entirely from a smartphone** — no local dev machine. Google Colab used for anything needing real network access (satellite/census data fetch); GitHub's mobile web editor used for all code edits and folder structure fixes. This constrained several workflow decisions documented below.

---

## 2. Repo structure

```
uhi-mapper/
├── config/
│   └── cities.yaml              # Phoenix config entry + template for future cities
├── src/
│   ├── lst.py                   # LST derivation math (see §4 — IMPORTANT CAVEAT)
│   ├── zonal_correlation.py     # zonal stats: LST vs canopy vs impervious
│   ├── vulnerability.py         # vulnerability index + Local Moran's I (seeded)
│   ├── pipeline.py              # city-agnostic orchestrator (added in multi-city refactor)
│   └── data_sources/
│       ├── boundaries.py        # admin boundary fetch (TIGER for US, GADM stub for global)
│       └── demographics.py      # demographic fetch (Census ACS working, WorldPop STUBBED)
├── api/
│   └── main.py                  # FastAPI: /health, /query
├── app/
│   └── streamlit_app.py         # interactive Plotly choropleth map
├── notebooks/
│   └── phoenix_uhi_colab.ipynb  # mobile-run notebook that fetched the REAL data (see §4)
├── scripts/
│   └── fetch_real_data.py       # alternate local fetch script, NOT what was actually used
├── tests/
│   └── test_lst.py              # 8 unit tests on src/lst.py math, all passing
├── data/
│   └── phoenix_final.geojson    # the actual real output — 360 Maricopa County tracts, feeds both API and Streamlit app
├── README.md
├── PORTFOLIO_WRITEUP.md         # hiring-manager-facing narrative + results
└── MULTI_CITY_BLUEPRINT.md      # plan for extending to India + global cities
```

---

## 3. Data pipeline — what actually ran

Real data was fetched via `notebooks/phoenix_uhi_colab.ipynb`, run cell-by-cell in Google Colab (not via `scripts/fetch_real_data.py`, which exists but was never the actual execution path).

**Sources:**
| Data | Source | Auth needed |
|---|---|---|
| Landsat 8/9 Collection 2 Level-2 | Microsoft Planetary Computer STAC | None |
| Census tracts (Maricopa County) | US Census TIGER/Line 2023 | None |
| Demographics (elderly %, low-income %) | US Census ACS 5-year 2022 | **Free API key required** — sign up at `api.census.gov/data/key_signup.html`. Census used to allow small unauthenticated queries; this changed, cost real debugging time. |
| Canopy / impervious surface | ESA WorldCover 2021 | None (via Planetary Computer STAC) |

**Pipeline steps (as actually run, in the Colab notebook):**
1. Search STAC for a low-cloud (<10%) Landsat scene over Phoenix bbox, summer 2024
2. Clip thermal (Band 10), red, NIR bands to the AOI
3. Convert to LST — **using a simplified Collection-2-Level-2-specific formula**, not `src/lst.py`'s full radiative chain (see §4)
4. Fetch Maricopa tracts (TIGER), reproject to match raster CRS
5. Zonal stats: mean LST per tract
6. Fetch WorldCover, zonal stats for canopy % (class 10) and impervious % (class 50)
7. Fetch ACS demographics, merge on GEOID
8. Build vulnerability index (equal weights: LST norm + elderly norm + low-income norm, ÷3 each)
9. Local Moran's I (LISA) clustering, p<0.05 significance
10. Export CSV + GeoJSON, downloaded to phone, uploaded back to Claude for merging/mapping

**Result:** 365 tracts fetched → 360 after merging LST + demographics (some tracts dropped in the merge, not deeply investigated why — likely tracts with null ACS values) → 357 used in the static portfolio map after filtering 3 oversized peripheral desert tracts (>50 km²) that visually dominated the choropleth.

**Cluster results (from the actual deployed `data/phoenix_final.geojson`):**
- Not Significant: 272
- Hotspot (High-High): 38
- Coldspot (Low-Low): 34
- Spatial Outlier: 16

The hotspot cluster sits in South/Central Phoenix, consistent with published environmental justice / UHI research for the region — used as an informal validation point, not a rigorous ground-truth check.

---

## 4. ⚠️ Important known inconsistency: two different LST code paths

**This is the single most important thing for a new developer to understand before extending the pipeline.**

`src/lst.py` implements a full physics-based radiative chain (DN → TOA radiance → brightness temperature → NDVI-derived emissivity → LST), designed around **Landsat Collection 1 / raw DN** style inputs using `ML`/`AL` radiance rescale factors from scene metadata. This module is unit-tested (8/8 passing) and was validated against synthetic data early in the project.

**However**, the actual real-data run in the Colab notebook used **Landsat Collection 2 Level-2** data, which ships pre-processed — Band 10 in C2 L2 is already scaled toward surface temperature in Kelvin using *different* scale factors (`mult=0.00341802, add=149.0`, applied directly to get Kelvin, no separate brightness-temperature/emissivity correction step). The notebook implements this simplified conversion **inline**, not by calling `src/lst.py`.

**Net effect:** the "production" LST module in `src/` was never actually exercised against the real Phoenix data that's now live in the API and map. The numbers you see deployed came from the notebook's simpler formula. This isn't necessarily wrong — C2 L2's built-in scaling is a legitimate approach — but it means:
- `src/lst.py`'s emissivity/NDVI correction logic is unvalidated against real imagery
- Before extending to new cities, decide: standardize on the notebook's simpler C2 L2 approach (recommended — it's what's proven to work), or actually wire `src/lst.py` into the real pipeline and validate it end-to-end first
- Don't assume `src/lst.py` is what generated the deployed results — it isn't

---

## 5. Known bugs fixed during development (useful context for similar issues)

1. **CRS mismatch → MemoryError in zonal_stats.** Tract polygons were in UTM (meters), WorldCover raster was in lat/lon (degrees) — caused rasterstats to try allocating a 714 TiB array. Fix: always reproject vector data to match raster CRS (`gdf.to_crs(raster_crs)`) before calling `zonal_stats`.

2. **Census API "Invalid Key" / JSONDecodeError.** Census now requires a free API key even for small queries (previously didn't). Symptom was an HTML error page returned with `status_code=200`, which broke naive `.json()` parsing — always check `resp.text` on JSON decode failures rather than trusting the status code alone.

3. **GEOID vs tract_id mismatch.** TIGER data uses `GEOID` (string, zero-padded to 11 digits); the pipeline schema uses `tract_id`. Also a dtype mismatch (`str` vs `int64`) caused silent merge failures. Always `.astype(str).str.zfill(11)` before merging census-sourced geometries with other tabular data.

4. **Moran's I non-reproducibility.** `Moran_Local`'s permutation test is stochastic by default — re-running produced slightly different hotspot/coldspot counts each time (e.g. 38 vs 36 hotspots across two runs on identical input). Fixed by adding a `seed` parameter (default 42) to `run_morans_i` and `run_local_morans_i` in `src/vulnerability.py`. **Caveat:** this fix was added *after* `data/phoenix_final.geojson` was generated and deployed — the live data was not regenerated with the seeded version. If exact reproducibility matters, regenerate.

5. **Plotly deprecation.** `px.choropleth_mapbox` / `mapbox_style` param is deprecated in favor of `px.choropleth_map` / `map_style`. The Streamlit app uses the current (non-deprecated) API.

6. **GitHub mobile upload flattens folders.** Uploading multiple files via GitHub's mobile web file picker drops folder nesting — everything lands at repo root regardless of original structure. Fix used: open each misplaced file → edit → rename field accepts a full path (e.g. `src/data_sources/boundaries.py`) → GitHub auto-creates the folder structure on commit. Tedious but reliable. No better mobile-only workaround was found.

---

## 6. What's stubbed / not implemented

- **`src/data_sources/demographics.py` → `_fetch_worldpop()`** raises `NotImplementedError` deliberately. This is the demographic source planned for all non-US cities (India, global). Needs: zonal aggregation of WorldPop gridded rasters against tract/admin boundaries, plus a decision on what proxies `pct_low_income` globally (WorldPop doesn't have an income equivalent — nightlight-derived poverty index or another proxy needs to be chosen and documented, not faked as comparable to US ACS figures).

- **`src/data_sources/boundaries.py` → `_fetch_gadm_boundaries()`** is written but **never tested against real data**. Untested assumptions in there: GADM's GeoPackage layer naming convention, that `cx[]` bbox slicing performs adequately at city scale, and the `GID_{level}` column existing at every admin level for every country.

- **`src/pipeline.py` → `run_city()`** was written and validated once against Phoenix (reproduced the same vulnerability/cluster logic as the original notebook run — see commit/test history), but has **never been run against a second city**. The multi-city abstraction is unproven beyond Phoenix.

- **No ground-truth validation** of LST against actual weather station data anywhere in the project. Flagged as a known limitation in the portfolio writeup, not resolved.

---

## 7. Deployment configuration (for redeploying or debugging)

**Render (API):**
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- Auto-loads `data/phoenix_final.geojson` on startup via a FastAPI `@app.on_event("startup")` hook (see `api/main.py`) — if this file is missing or moved, `/query` will 503 but `/health` will still respond (fails soft by design).
- Auto-deploys on every push to `main`.

**Streamlit Cloud (map):**
- Main file path: `app/streamlit_app.py`
- Also auto-deploys on push to `main`.
- Reads the same `data/phoenix_final.geojson` — if that file changes, both services need to pick it up (Render needs a restart/redeploy to reload; Streamlit's `@st.cache_data` will also need a manual "Clear cache" or redeploy to pick up changes).

**Both services currently point at the same static `data/phoenix_final.geojson`** — there's no live re-processing pipeline; updating the data means regenerating that file (via the Colab notebook) and committing it.

---

## 8. Recommended next steps (in priority order)

1. **Resolve the §4 LST inconsistency** before building anything else on top — decide which LST code path is canonical.
2. **Regenerate `data/phoenix_final.geojson`** with the now-seeded Moran's I for true reproducibility, if exactness matters going forward.
3. **Implement WorldPop demographics** — this blocks any non-US city.
4. **Test `run_city()` against a second city** (Ahmedabad was the planned first India city per the blueprint) to actually prove the multi-city abstraction works, not just that it was written.
5. Only after 3-4 are proven: build out Forest Carbon MRV and Solar Siting projects using the same config-driven pattern.

---

*Last updated: reflects state as of the live deployment described in this document. If you extend this project, update this file — it's meant to stay current, not be a one-time snapshot.*
