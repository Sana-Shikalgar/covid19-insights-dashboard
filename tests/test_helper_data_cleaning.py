import pytest
import pandas as pd
import numpy as np
import logging

from src.helper_data_cleaning import (
    validate_dataframe_content,

    CORE_COLS,
    check_required_columns,
    calculate_missing_values,
    calculate_missing_percentages,
    
    assess_data,
    
    clean_missing_core_metrics,
    create_continent_location_map,
    
    impute_continent_by_location,
    impute_continent_by_aggregate,
    impute_continent,
    impute_gdp_per_capita,

    final_cleanup,
    
    convert_to_category,
    normalize_date_column,
    optimize_dtypes,
    
    validate_data,
)


# ------Dataframe Validation
def test_validate_dataframe_content_raises_on_empty():
    df = pd.DataFrame()
    with pytest.raises(ValueError):
        validate_dataframe_content(df)


def test_validate_dataframe_content_ok(caplog):
    df = pd.DataFrame({"a": [1, 2]})
    with caplog.at_level(logging.INFO):
        validate_dataframe_content(df)
    assert any("Loaded: (2, 1)" in record.message for record in caplog.records)


# ------Assessment helpers (CORE_COLS, missing values)
def test_check_required_columns_raises_when_missing():
    df = pd.DataFrame({"gdp_per_capita": [1.0], "continent": ["Asia"]})
    with pytest.raises(ValueError):
        check_required_columns(df, CORE_COLS)


def test_check_required_columns_passes_when_all_present():
    df = pd.DataFrame(
        {col: [1] for col in CORE_COLS}  # dummy data for all core columns
    )
    # Should not raise
    check_required_columns(df, CORE_COLS)


def test_calculate_missing_values_counts_correctly():
    df = pd.DataFrame({
        "gdp_per_capita": [1.0, np.nan],
        "continent": ["Asia", None],
    })
    missing = calculate_missing_values(df, ["gdp_per_capita", "continent"])
    assert missing["gdp_per_capita"] == 1
    assert missing["continent"] == 1


def test_calculate_missing_percentages_basic():
    df = pd.DataFrame({"a": [1, None, 3, None]})
    counts = df.isna().sum()
    perc = calculate_missing_percentages(df, counts)
    # 2/4 = 50%
    assert perc["a"] == 50.0


def test_calculate_missing_percentages_empty_df_returns_empty():
    df = pd.DataFrame()
    missing_counts = pd.Series(dtype="int64")

    result = calculate_missing_percentages(df, missing_counts)
    assert isinstance(result, pd.Series)
    assert result.empty


def test_calculate_missing_percentages_raises_when_df_is_invalid():
    """len(df) fails → exception path is executed."""
    from src.helper_data_cleaning import calculate_missing_percentages

    df = None  # invalid, len(None) raises TypeError
    missing_counts = pd.Series([1, 2, 3])

    with pytest.raises(Exception):
        calculate_missing_percentages(df, missing_counts)


def test_calculate_missing_percentages_raises_when_missing_counts_invalid():
    """Division fails → exception path is executed."""
    from src.helper_data_cleaning import calculate_missing_percentages

    df = pd.DataFrame({"a": [1, 2, 3]})
    missing_counts = "not_a_series"  # invalid type for division

    with pytest.raises(Exception):
        calculate_missing_percentages(df, missing_counts)


def test_assess_data_returns_summary_dataframe():
    df = pd.DataFrame(
        {col: [1.0, np.nan] for col in CORE_COLS}
    )
    summary = assess_data(df)
    assert isinstance(summary, pd.DataFrame)
    assert set(summary.columns) == {"missing_count", "missing_percent"}
    assert set(summary.index) == set(CORE_COLS)


def test_assess_data_raises_when_required_columns_missing():
    # Missing many CORE_COLS on purpose
    df = pd.DataFrame({"gdp_per_capita": [1.0], "continent": ["Asia"]})

    with pytest.raises(Exception):
        assess_data(df)


# ------ Cleaning Functions
def test_clean_missing_core_metrics_drops_rows_with_missing_core_values():
    """
    cleaning_missing_core_metrics
    """
    df = pd.DataFrame({
        "new_cases": [1, np.nan, 3],
        "new_deaths": [0, 1, np.nan],
        "total_cases": [10, 20, 30],
        "total_deaths": [1, 2, 3],
    })
    cleaned = clean_missing_core_metrics(df)
    # Only first row is fully observed
    assert cleaned.shape[0] == 1
    assert cleaned["new_cases"].isna().sum() == 0
    assert cleaned["new_deaths"].isna().sum() == 0


def test_clean_missing_core_metrics_raises_on_invalid_input():
    # Passing a list instead of DataFrame will make df.dropna fail
    bad_input = ["not", "a", "dataframe"]

    with pytest.raises(Exception):
        clean_missing_core_metrics(bad_input)  # type: ignore[arg-type]


def test_create_continent_location_map_uses_non_missing_rows_only():
    df = pd.DataFrame({
        "location": ["A", "B", "C"],
        "continent": ["X", np.nan, "Y"],
    })
    m = create_continent_location_map(df)
    assert m == {"A": "X", "C": "Y"}
    assert "B" not in m


def test_impute_continent_by_location_fills_from_map():
    df = pd.DataFrame({
        "location": ["A", "B"],
        "continent": [np.nan, "Y"],
    })
    cmap = {"A": "X"}
    out = impute_continent_by_location(df.copy(), cmap)
    assert out.loc[0, "continent"] == "X"
    assert out.loc[1, "continent"] == "Y"


def test_impute_continent_raises_when_required_columns_missing():
    # No 'location' column → .drop_duplicates('location') will fail
    df = pd.DataFrame({
        "continent": ["Asia", "Europe"],
    })

    with pytest.raises(Exception):
        impute_continent(df)


def test_impute_continent_by_aggregate_uses_aggregate_names():
    df = pd.DataFrame({
        "location": ["Europe", "Unknown"],
        "continent": [np.nan, np.nan],
    })
    out = impute_continent_by_aggregate(df.copy())
    # "Europe" → "Europe" from aggregate_map
    assert out.loc[0, "continent"] == "Europe"
    # "Unknown" stays NaN
    assert pd.isna(out.loc[1, "continent"])


def test_impute_continent_end_to_end():
    df = pd.DataFrame({
        "location": ["Afghanistan", "Europe", "Unknown"],
        "continent": ["Asia", np.nan, np.nan],
        "new_cases": [1, 2, 3],
        "new_deaths": [0, 0, 0],
        "total_cases": [10, 20, 30],
        "total_deaths": [1, 2, 3],
    })

    out = impute_continent(df.copy())

    # Existing mapping preserved
    assert out.loc[0, "continent"] == "Asia"
    # Aggregate name "Europe" → "Europe"
    assert out.loc[1, "continent"] == "Europe"
    # Unknown still possibly NaN
    assert pd.isna(out.loc[2, "continent"])


def test_impute_gdp_per_capita_by_continent_median():
    df = pd.DataFrame({
        "continent": ["X", "X", "Y"],
        "gdp_per_capita": [1000.0, np.nan, np.nan],
        "new_cases": [1, 2, 3],
        "new_deaths": [0, 0, 0],
        "total_cases": [10, 20, 30],
        "total_deaths": [1, 2, 3],
    })

    out = impute_gdp_per_capita(df.copy())

    # For continent X → median of [1000] = 1000
    assert out.loc[0, "gdp_per_capita"] == 1000.0
    assert out.loc[1, "gdp_per_capita"] == 1000.0
    # For Y there was no non-null → stays NaN
    assert pd.isna(out.loc[2, "gdp_per_capita"])


def test_impute_gdp_per_capita_raises_on_missing_columns():
    # No 'gdp_per_capita' column
    df = pd.DataFrame({
        "continent": ["Asia", "Europe"],
        "new_cases": [1, 2],
    })

    with pytest.raises(Exception):
        impute_gdp_per_capita(df)


def test_final_cleanup_drops_all_remaining_nans():
    df = pd.DataFrame({
        "a": [1, np.nan, 3],
        "b": [4, 5, np.nan],
    })
    cleaned = final_cleanup(df)
    # Only first row has no NaNs
    assert cleaned.shape == (1, 2)
    assert not cleaned.isna().any().any()


def test_final_cleanup_raises_on_invalid_input():
    bad_input = "not a dataframe"

    with pytest.raises(Exception):
        final_cleanup(bad_input)  # type: ignore[arg-type]


# ----- DType optimizer and validation
def test_convert_to_category_changes_dtypes():
    df = pd.DataFrame({
        "continent": ["Asia", "Europe"],
        "iso_code": ["AFG", "GBR"],
        "location": ["Afghanistan", "United Kingdom"],
    })
    out = convert_to_category(df.copy())
    assert out["continent"].dtype.name == "category"
    assert out["iso_code"].dtype.name == "category"
    assert out["location"].dtype.name == "category"


def test_normalize_date_column_parses_and_coerces():
    df = pd.DataFrame({
        "date": ["2020-01-01", "bad-date", "", None],
    })
    out = normalize_date_column(df.copy())
    assert pd.api.types.is_datetime64_any_dtype(out["date"])
    # One valid, three invalid → 3 NaT
    assert out["date"].notna().sum() == 1
    assert out["date"].isna().sum() == 3


def test_optimize_dtypes_combines_category_and_date():
    df = pd.DataFrame({
        "continent": ["Asia", "Europe"],
        "iso_code": ["AFG", "GBR"],
        "location": ["Afghanistan", "United Kingdom"],
        "date": ["2020-01-01", "2020-01-02"],
    })
    out = optimize_dtypes(df.copy())

    assert out["continent"].dtype.name == "category"
    assert out["iso_code"].dtype.name == "category"
    assert out["location"].dtype.name == "category"
    assert pd.api.types.is_datetime64_any_dtype(out["date"])


def test_optimize_dtypes_raises_on_invalid_input():
    bad_input = {"continent": ["Asia", "Europe"]}  # dict, not DataFrame

    with pytest.raises(Exception):
        optimize_dtypes(bad_input)  # type: ignore[arg-type]


def test_validate_data_runs_without_error(capsys):
    df = pd.DataFrame({
        "continent": ["Asia", "Europe"],
        "iso_code": ["AFG", "GBR"],
        "location": ["Afghanistan", "United Kingdom"],
        "date": pd.to_datetime(["2020-01-01", "2020-01-02"]),
    })
    validate_data(df)
    out, _ = capsys.readouterr()
    assert "FINAL SUMMARY" in out
    assert "Shape:" in out


def test_validate_data_raises_when_required_columns_missing():
    df = pd.DataFrame({
        "continent": ["Asia"],
        "location": ["Afghanistan"],
        # no 'date' column
    })

    with pytest.raises(Exception):
        validate_data(df)
