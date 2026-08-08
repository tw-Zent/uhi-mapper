import numpy as np
from src.lst import (
    dn_to_radiance,
    radiance_to_brightness_temp,
    compute_ndvi,
    fractional_vegetation_cover,
    land_surface_emissivity,
    brightness_temp_to_lst,
    kelvin_to_celsius,
)


def test_dn_to_radiance_linear():
    dn = np.array([[100, 200]])
    result = dn_to_radiance(dn, ml=0.0003, al=0.1)
    expected = np.array([[0.13, 0.16]])
    np.testing.assert_allclose(result, expected, rtol=1e-6)


def test_ndvi_range_bounded():
    nir = np.array([[0.5, 0.0]])
    red = np.array([[0.1, 0.5]])
    ndvi = compute_ndvi(nir, red)
    assert ndvi.max() <= 1.0
    assert ndvi.min() >= -1.0


def test_ndvi_known_values():
    nir = np.array([[0.6]])
    red = np.array([[0.2]])
    ndvi = compute_ndvi(nir, red)
    np.testing.assert_allclose(ndvi, [[0.5]], rtol=1e-6)


def test_fvc_clipped_0_1():
    ndvi = np.array([[-1.0, 0.0, 0.35, 1.0]])
    fv = fractional_vegetation_cover(ndvi)
    assert fv.min() >= 0.0
    assert fv.max() <= 1.0


def test_emissivity_between_soil_and_veg():
    fv = np.array([[0.0, 1.0]])
    e = land_surface_emissivity(fv, emissivity_soil=0.97, emissivity_veg=0.99)
    np.testing.assert_allclose(e, [[0.97, 0.99]], rtol=1e-6)


def test_brightness_temp_reasonable_range():
    # Realistic Landsat radiance values should produce plausible temps (250-330 K)
    radiance = np.array([[8.5]])
    tb = radiance_to_brightness_temp(radiance)
    assert 250 < tb[0, 0] < 330


def test_kelvin_to_celsius():
    k = np.array([273.15])
    c = kelvin_to_celsius(k)
    np.testing.assert_allclose(c, [0.0], atol=1e-6)


def test_lst_pipeline_end_to_end_plausible():
    tb = np.array([[300.0]])
    emissivity = np.array([[0.98]])
    lst_k = brightness_temp_to_lst(tb, emissivity)
    lst_c = kelvin_to_celsius(lst_k)
    # LST should be close to but slightly above brightness temp for realistic emissivity
    assert lst_c[0, 0] > 0
    assert lst_c[0, 0] < 100
