import pytest
import pandas as pd
import numpy as np

from src.data_cleaner import handle_missing_data, standardize_types, clean_pipeline


# ---------- Fixtures ----------

@pytest.fixture
def sample_df():
    """
    Sample DataFrame mimicking filtered_covid_data.csv
    (after manual column selection).
    """
    data = {
        "iso_code": ["AFG", "GBR", "USA", "FRA"],
        "location": ["Afghanistan", "United Kingdom", "United States", "France"],
        "continent": ["Asia", np.nan, "North America", np.nan],
        "date": ["2020-01-01", "2020-01-02", "bad-date", ""],
        "new_cases": [10, np.nan, 30, 40],
        "new_deaths": [1, 2, np.nan, 4],
        "total_cases": [100, 200, 300, np.nan],
        "total_deaths": [1, 2, 3, 4],
        "gdp_per_capita": [1000.0, np.nan, 3000.0, np.nan],
    }
    return pd.DataFrame(data)


@pytest.fixture
def empty_df():
    return pd.DataFrame()


@pytest.fixture
def df_all_missing_core():
    """All core metrics missing → everything should be dropped."""
    return pd.DataFrame({
        "iso_code": ["AFG", "GBR"],
        "location": ["Afghanistan", "United Kingdom"],
        "continent": ["Asia", "Europe"],
        "date": ["2020-01-01", "2020-01-02"],
        "new_cases": [np.nan, np.nan],
        "new_deaths": [np.nan, np.nan],
        "total_cases": [np.nan, np.nan],
        "total_deaths": [np.nan, np.nan],
        "gdp_per_capita": [np.nan, np.nan],
    })


# ---------- handle_missing_data tests ----------

def test_handle_missing_data_drops_rows_with_missing_core_metrics(sample_df):
    """
    Rows with missing new_cases/new_deaths/total_cases/total_deaths
    should be dropped (no imputation for core epidemic metrics).
    """
    cleaned = handle_missing_data(sample_df)

    # All remaining rows must have no missing core metrics
    assert cleaned["new_cases"].isna().sum() == 0
    assert cleaned["new_deaths"].isna().sum() == 0
    assert cleaned["total_cases"].isna().sum() == 0
    assert cleaned["total_deaths"].isna().sum() == 0

    # At least one row should remain if there was at least one fully observed row
    assert len(cleaned) < len(sample_df)
    assert len(cleaned) >= 1


def test_handle_missing_data_empty_dataframe(empty_df):
    """
    Empty DataFrame should return empty DataFrame without error.
    """
    cleaned = handle_missing_data(empty_df)
    assert cleaned.empty
    assert list(cleaned.columns) == []


def test_handle_missing_data_all_missing_core_metrics(df_all_missing_core):
    """
    If all rows have missing core metrics, the result should be empty
    after dropping and final_cleanup.
    """
    cleaned = handle_missing_data(df_all_missing_core)
    assert cleaned.empty


def test_handle_missing_data_imputes_gdp_per_capita_by_continent():
    """
    gdp_per_capita should be imputed per continent median (where at least one
    non-null value exists), matching impute_gdp_per_capita logic.
    """
    df = pd.DataFrame({
        "iso_code": ["A", "B", "C"],
        "location": ["LocA", "LocB", "LocC"],
        "continent": ["X", "X", "Y"],
        "date": ["2020-01-01"] * 3,
        "new_cases": [1, 2, 3],
        "new_deaths": [0, 1, 1],
        "total_cases": [10, 20, 30],
        "total_deaths": [1, 2, 3],
        "gdp_per_capita": [1000.0, np.nan, np.nan],
    })

    cleaned = handle_missing_data(df)

    # For continent X: median of [1000] → 1000
    # For continent Y: no non-null → remains NaN, then final_cleanup drops that row
    assert cleaned["gdp_per_capita"].isna().sum() == 0
    assert set(cleaned["gdp_per_capita"].unique()) == {1000.0}
    # Row with continent Y and NaN GDP should be gone
    assert "Y" not in cleaned["continent"].unique()


def test_handle_missing_data_raises_on_none_input():
    with pytest.raises(ValueError):
        handle_missing_data(None)


# ---------- standardize_types tests ----------

def test_standardize_types_converts_date_to_datetime(sample_df):
    """
    String dates → datetime; invalid dates → NaT.
    """
    std = standardize_types(sample_df)

    assert "date" in std.columns
    assert pd.api.types.is_datetime64_any_dtype(std["date"])
    # First two valid dates
    assert std["date"].iloc[0] == pd.Timestamp("2020-01-01")
    assert std["date"].iloc[1] == pd.Timestamp("2020-01-02")
    # 'bad-date' and '' → NaT
    assert std["date"].isna().sum() == 2


def test_standardize_types_converts_to_category(sample_df):
    """
    continent, iso_code, location → category when present.
    """
    std = standardize_types(sample_df)

    assert std["continent"].dtype.name == "category"
    assert std["iso_code"].dtype.name == "category"
    assert std["location"].dtype.name == "category"


def test_standardize_types_handles_empty_and_none():
    df = pd.DataFrame()
    std = standardize_types(df)
    assert std.empty

    with pytest.raises(ValueError):
        standardize_types(None)


def test_standardize_types_without_date_column():
    df = pd.DataFrame({
        "iso_code": ["AFG", "GBR"],
        "location": ["Afghanistan", "United Kingdom"],
        "continent": ["Asia", "Europe"],
    })

    std = standardize_types(df)

    assert "date" not in std.columns
    # Still converted to category
    assert std["iso_code"].dtype.name == "category"
    assert std["location"].dtype.name == "category"
    assert std["continent"].dtype.name == "category"


# ---------- clean_pipeline tests ----------

def test_clean_pipeline_end_to_end(sample_df):
    """
    Full pipeline: missing handling + type standardization.
    """
    result = clean_pipeline(sample_df)

    # No missing values left after handle_missing_data + final_cleanup
    assert not result.isna().any().any()

    # Core metrics present and clean
    for col in ["new_cases", "new_deaths", "total_cases", "total_deaths"]:
        assert col in result.columns
        assert result[col].isna().sum() == 0

    # Date and categories standardized
    assert pd.api.types.is_datetime64_any_dtype(result["date"])
    assert result["continent"].dtype.name == "category"
    assert result["iso_code"].dtype.name == "category"
    assert result["location"].dtype.name == "category"


def test_clean_pipeline_with_empty_dataframe(empty_df):
    result = clean_pipeline(empty_df)
    assert result.empty
