"""
Land Surface Temperature (LST) retrieval from Landsat 8/9 TIRS Band 10.

Pipeline: DN -> TOA Radiance -> Brightness Temperature -> LST (via NDVI-derived emissivity)

Limitation (documented, not hidden): single-scene LST is sensitive to acquisition
time, cloud contamination, and season. For production use, composite multiple
cloud-free summer scenes and report a confidence interval, not a point estimate.
"""

import numpy as np
import rasterio


# Landsat 8/9 Band 10 TOA radiance -> brightness temp constants (from MTL metadata)
K1_CONST = 774.8853  # W/(m^2 * sr * um), Landsat 8/9 Band 10 default
K2_CONST = 1321.0789  # Kelvin, Landsat 8/9 Band 10 default


def dn_to_radiance(dn: np.ndarray, ml: float, al: float) -> np.ndarray:
    """Convert raw Band 10 digital numbers to TOA spectral radiance.

    ml, al = RADIANCE_MULT_BAND_10 / RADIANCE_ADD_BAND_10 from the scene's MTL.txt.
    """
    return ml * dn.astype(np.float64) + al


def radiance_to_brightness_temp(radiance: np.ndarray, k1: float = K1_CONST, k2: float = K2_CONST) -> np.ndarray:
    """Convert TOA radiance to at-sensor brightness temperature (Kelvin)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        tb = k2 / np.log((k1 / radiance) + 1)
    return tb


def compute_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Standard NDVI. nir/red should be TOA reflectance, same shape."""
    nir = nir.astype(np.float64)
    red = red.astype(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / (nir + red)
    return np.clip(ndvi, -1, 1)


def fractional_vegetation_cover(ndvi: np.ndarray, ndvi_min: float = 0.2, ndvi_max: float = 0.5) -> np.ndarray:
    """Fv from NDVI, clipped to [0, 1]. ndvi_min/max are bare-soil / full-veg thresholds
    and should be calibrated per-scene rather than hardcoded in production."""
    fv = ((ndvi - ndvi_min) / (ndvi_max - ndvi_min)) ** 2
    return np.clip(fv, 0, 1)


def land_surface_emissivity(fv: np.ndarray, water_mask: np.ndarray = None,
                             emissivity_soil: float = 0.97, emissivity_veg: float = 0.99) -> np.ndarray:
    """Simple mixed-pixel emissivity model. water_mask, if provided, forces e=0.991 there."""
    epsilon = emissivity_soil * (1 - fv) + emissivity_veg * fv
    if water_mask is not None:
        epsilon = np.where(water_mask, 0.991, epsilon)
    return epsilon


def brightness_temp_to_lst(tb: np.ndarray, emissivity: np.ndarray, wavelength_um: float = 10.895) -> np.ndarray:
    """Convert brightness temperature to LST (Kelvin) correcting for surface emissivity.

    Uses the standard approximation: LST = TB / (1 + (lambda * TB / rho) * ln(epsilon))
    where rho = h*c/sigma (1.438e-2 m K).
    """
    rho = 1.438e-2  # m*K
    wavelength_m = wavelength_um * 1e-6
    with np.errstate(divide="ignore", invalid="ignore"):
        lst = tb / (1 + (wavelength_m * tb / rho) * np.log(emissivity))
    return lst


def kelvin_to_celsius(k: np.ndarray) -> np.ndarray:
    return k - 273.15


def run_lst_pipeline(band10_path: str, red_path: str, nir_path: str,
                      ml: float, al: float, out_path: str) -> str:
    """End-to-end: read bands, compute LST in Celsius, write single-band GeoTIFF.

    Assumes red/nir/band10 are already co-registered and resampled to the same grid
    (Band 10 is native 100m resampled to 30m by USGS; red/nir are native 30m).
    """
    with rasterio.open(band10_path) as src10:
        dn = src10.read(1)
        profile = src10.profile

    with rasterio.open(red_path) as srcr:
        red = srcr.read(1)
    with rasterio.open(nir_path) as srcn:
        nir = srcn.read(1)

    radiance = dn_to_radiance(dn, ml, al)
    tb = radiance_to_brightness_temp(radiance)
    ndvi = compute_ndvi(nir, red)
    fv = fractional_vegetation_cover(ndvi)
    emissivity = land_surface_emissivity(fv)
    lst_k = brightness_temp_to_lst(tb, emissivity)
    lst_c = kelvin_to_celsius(lst_k)

    profile.update(dtype="float32", count=1, nodata=np.nan)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(lst_c.astype("float32"), 1)

    return out_path
