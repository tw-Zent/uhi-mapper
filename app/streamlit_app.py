"""
Interactive public map of Phoenix UHI + vulnerability data.
Deploy target: Streamlit Community Cloud (streamlit.app)
Run locally with: streamlit run app/streamlit_app.py
"""

import streamlit as st
import geopandas as gpd
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="Phoenix UHI & Vulnerability Mapper", layout="wide")

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "phoenix_final.geojson")


@st.cache_data
def load_data():
    gdf = gpd.read_file(DATA_PATH)
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    if "GEOID" in gdf.columns and "tract_id" not in gdf.columns:
        gdf = gdf.rename(columns={"GEOID": "tract_id"})
    return gdf


st.title("🌡️ Phoenix Urban Heat Island & Thermal Vulnerability Mapper")
st.markdown(
    "Real Landsat 8/9 surface temperature + US Census demographics, "
    "360 census tracts, Maricopa County, AZ. "
    "[View source code](https://github.com/tw-Zent/uhi-mapper)"
)

gdf = load_data()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Tracts analyzed", len(gdf))
col2.metric("Mean LST", f"{gdf['lst_mean'].mean():.1f}°C")
hotspots = (gdf["lisa_cluster"] == "Hotspot (High-High)").sum()
col3.metric("Significant hotspots", hotspots)
col4.metric("Significant coldspots", (gdf["lisa_cluster"] == "Coldspot (Low-Low)").sum())

st.divider()

map_choice = st.radio(
    "Select map layer:",
    ["Land Surface Temperature", "Vulnerability Hotspot Clusters", "Vulnerability Index"],
    horizontal=True,
)

gdf_json = gdf.set_index("tract_id").__geo_interface__

if map_choice == "Land Surface Temperature":
    fig = px.choropleth_map(
        gdf, geojson=gdf_json, locations="tract_id", color="lst_mean",
        color_continuous_scale="Inferno", map_style="carto-positron",
        center={"lat": 33.45, "lon": -112.05}, zoom=9.5, opacity=0.75,
        labels={"lst_mean": "Mean LST (°C)"},
        hover_data={"tract_id": True, "lst_mean": ":.1f", "canopy_pct": ":.1f", "impervious_pct": ":.1f"},
    )
elif map_choice == "Vulnerability Hotspot Clusters":
    color_map = {
        "Hotspot (High-High)": "#d73027",
        "Coldspot (Low-Low)": "#4575b4",
        "Spatial Outlier": "#fee090",
        "Not Significant": "#e8e8e8",
    }
    fig = px.choropleth_map(
        gdf, geojson=gdf_json, locations="tract_id", color="lisa_cluster",
        color_discrete_map=color_map, map_style="carto-positron",
        center={"lat": 33.45, "lon": -112.05}, zoom=9.5, opacity=0.75,
        hover_data={"tract_id": True, "vulnerability_index": ":.2f", "lisa_p_value": ":.3f"},
    )
else:
    fig = px.choropleth_map(
        gdf, geojson=gdf_json, locations="tract_id", color="vulnerability_index",
        color_continuous_scale="OrRd", map_style="carto-positron",
        center={"lat": 33.45, "lon": -112.05}, zoom=9.5, opacity=0.75,
        hover_data={"tract_id": True, "pct_elderly": ":.1f", "pct_low_income": ":.1f"},
    )

fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=600)
st.plotly_chart(fig, use_container_width=True)

st.divider()
with st.expander("Methodology & limitations"):
    st.markdown(
        "- LST derived from real Landsat 8/9 Collection 2 Level-2 thermal data (summer 2024, <10% cloud cover)\n"
        "- Vulnerability index combines normalized LST, elderly %, and low-income % (equal weights, US Census ACS 2022)\n"
        "- Hotspot/coldspot clusters identified via Local Moran's I (p < 0.05), seeded for reproducibility\n"
        "- **Limitation**: single-scene LST is sensitive to acquisition timing; production use should composite multiple dates\n"
        "- **Limitation**: equal-weight vulnerability index is a starting assumption, not a validated model"
    )
