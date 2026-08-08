# Multi-City Extension & Public Hosting Blueprint

**Applies to:** UHI Mapper, Forest Carbon MRV, Solar Siting Engine (and any future geospatial project)
**Goal:** Turn a single-city case study into a generalizable, publicly deployed framework covering India + global cities.

---

## 1. City Selection Framework

Don't add cities randomly — each one should prove a different capability.

| Tier | Purpose | Example picks |
|---|---|---|
| **Anchor city** | Primary portfolio story, deepest analysis, Western-reader-friendly | Phoenix (UHI), keep as headline |
| **India cities** | Prove domain relevance + real local data handling | Delhi, Ahmedabad (Heat Action Plan precedent), Mumbai |
| **Global stress-test** | Prove the pipeline generalizes beyond US/India data formats | 1 EU city (e.g. Madrid — different census/tract system), 1 different-hemisphere city |

**Rule of thumb:** 4-5 cities total is enough to claim "generalizable framework." More than that dilutes depth for breadth — you validated this concern yourself with the 3-projects decision earlier.

## 2. Data Source Abstraction Layer

The current pipeline hardcodes Phoenix-specific sources (Maricopa TIGER, US Census ACS). Multi-city requires swapping these per-country without rewriting pipeline logic.

**Build this once:**
```
config/
  cities.yaml          # bbox, country, admin-boundary source, demographic source per city
src/
  data_sources/
    boundaries.py       # get_admin_boundaries(city_config) -> unified GeoDataFrame
    demographics.py      # get_demographics(city_config) -> unified schema (pct_elderly, pct_low_income, population)
    satellite.py          # already source-agnostic (STAC works globally) -- no change needed
```

**Per-country demographic source mapping (the hard part):**
| Country | Admin boundaries | Demographic data |
|---|---|---|
| USA | Census TIGER/Line | Census ACS API |
| India | GADM or Bhuvan (ISRO) | Census of India 2011 (dated) or SECC / WorldPop gridded estimates |
| EU | Eurostat NUTS/LAU | Eurostat regional statistics |
| Global fallback | GADM (any country) | WorldPop (gridded population + age structure, works anywhere, no per-country wrangling) |

Recommendation: use **WorldPop** as the default demographic source for non-US cities — it's globally consistent, avoids chasing down a different government API per country, and is a defensible methodological choice to state explicitly ("used a consistent global data source for cross-city comparability" reads as *better* engineering than stitching together 5 different national APIs).

## 3. Unified Output Schema

Every city, regardless of source, must produce the same output columns so cross-city comparison/aggregation just works:

```
tract_id, city, country, lst_mean, canopy_pct, impervious_pct,
pct_elderly, pct_low_income, population, vulnerability_index, lisa_cluster
```

This schema is what makes "multi-city" a real feature and not just "I ran the script 5 times."

## 4. Public Hosting Architecture

| Layer | What | Where |
|---|---|---|
| **Code** | Full pipeline, configs, notebooks | GitHub (public repo) |
| **Processed data** | Per-city GeoJSON/CSV outputs | GitHub repo `/data/` if small (<100MB total), else... |
| **Large raster data** | LST GeoTIFFs, WorldCover clips | Hugging Face Datasets (free, public, versioned) or a public S3/R2 bucket |
| **Live API** | FastAPI querying processed data | Render / Railway (free tier) |
| **Interactive map** | Cross-city comparison map | Streamlit Cloud (free) or GitHub Pages + Mapbox GL static build |

**Simplest realistic stack for you:** GitHub (code + small data) + Render (API) + Streamlit Cloud (map UI). All free, all deployable from the same repo.

## 5. Standard Repo Structure (applies to all 3 projects going forward)

```
project-name/
  config/cities.yaml
  src/
    data_sources/         # per-source ingestion, swappable
    pipeline.py             # core science, city-agnostic
  api/main.py
  app/streamlit_app.py    # public interactive map
  notebooks/               # per-city Colab notebooks (mobile-friendly ingestion)
  data/processed/          # small, versioned outputs per city
  README.md
  PORTFOLIO_WRITEUP.md
```

## 6. Rollout Order (recommended)

1. Refactor UHI Mapper's existing Phoenix code into this abstracted structure (config-driven, not hardcoded) — proves the pattern works before adding cities
2. Add 1 India city (Ahmedabad — has published Heat Action Plan data to validate against, same as Phoenix's South-Phoenix validation)
3. Add 1 global city to prove non-US/non-India generalization
4. Deploy publicly (GitHub + Render + Streamlit)
5. Repeat steps 1-4 for Forest Carbon MRV and Solar Siting once UHI pattern is proven

## Open decisions before building

- Confirm anchor-city framing strategy (keep Phoenix as headline, cities as "also generalizes to" section) vs. equal-weight multi-city story
- Confirm demographic data policy: WorldPop-for-all (consistent, defensible) vs. best-available-per-country (more accurate per city, less comparable across cities)
