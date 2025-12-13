import pandas as pd
import pytest

from src.data_analyzer import (
    calculate_summary_metrics,
    generate_grouped_summary,
    generate_time_trend,
    run_analysis,
)


# --------------------------------------------------
# Fixtures
# --------------------------------------------------
@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "iso_code": ["A", "A", "B", "B"],
        "location": ["X", "X", "Y", "Y"],
        "continent": ["C1", "C1", "C2", "C2"],
        "date": pd.to_datetime([
            "2020-01-01",
            "2020-01-02",
            "2020-01-01",
            "2020-01-02",
        ]),
        "year": [2020, 2020, 2020, 2020],
        "month": [1, 1, 1, 1],
        "total_cases": [10, 20, 5, 15],
        "new_cases": [1, 2, 1, 3],
    })


# --------------------------------------------------
# calculate_summary_metrics
# --------------------------------------------------
def test_calculate_summary_metrics_basic(sample_df):
    summary = calculate_summary_metrics(sample_df)

    assert not summary.empty
    assert "metric" in summary.columns
    assert "mean" in summary.columns
    assert "min" in summary.columns
    assert "max" in summary.columns
    assert "count" in summary.columns


def test_calculate_summary_metrics_specific_columns(sample_df):
    summary = calculate_summary_metrics(
        sample_df,
        numeric_columns=["total_cases"]
    )

    assert len(summary) == 1
    assert summary.loc[0, "metric"] == "total_cases"
    assert summary.loc[0, "mean"] == 12.5


def test_calculate_summary_metrics_empty_df():
    empty_df = pd.DataFrame()
    summary = calculate_summary_metrics(empty_df)

    assert summary.empty


# --------------------------------------------------
# generate_grouped_summary
# --------------------------------------------------
def test_generate_grouped_summary_single_group(sample_df):
    grouped = generate_grouped_summary(
        sample_df,
        group_by=["location"]
    )

    assert not grouped.empty
    assert "location" in grouped.columns
    assert "total_cases_mean" in grouped.columns
    assert "total_cases_count" in grouped.columns


def test_generate_grouped_summary_multiple_groups(sample_df):
    grouped = generate_grouped_summary(
        sample_df,
        group_by=["continent", "year"]
    )

    assert len(grouped) == 2
    assert "continent" in grouped.columns
    assert "year" in grouped.columns


def test_generate_grouped_summary_specific_metrics(sample_df):
    grouped = generate_grouped_summary(
        sample_df,
        group_by=["location"],
        numeric_columns=["total_cases"],
        metrics=["mean", "max"]
    )

    assert "total_cases_mean" in grouped.columns
    assert "total_cases_max" in grouped.columns
    assert "total_cases_min" not in grouped.columns


def test_generate_grouped_summary_empty_df():
    empty_df = pd.DataFrame()
    grouped = generate_grouped_summary(
        empty_df,
        group_by=["location"]
    )

    assert grouped.empty


# --------------------------------------------------
# generate_time_trend
# --------------------------------------------------
def test_generate_time_trend_no_group(sample_df):
    trend = generate_time_trend(
        sample_df,
        time_column="date",
        value_column="total_cases"
    )

    assert not trend.empty
    assert "date" in trend.columns
    assert "total_cases" in trend.columns


def test_generate_time_trend_with_group(sample_df):
    trend = generate_time_trend(
        sample_df,
        time_column="date",
        value_column="total_cases",
        group_by=["location"]
    )

    assert "location" in trend.columns
    assert "date" in trend.columns


def test_generate_time_trend_monthly(sample_df):
    trend = generate_time_trend(
        sample_df,
        time_column="date",
        value_column="total_cases",
        freq="ME"
    )

    assert not trend.empty
    assert "date" in trend.columns


def test_generate_time_trend_empty_df():
    empty_df = pd.DataFrame()
    trend = generate_time_trend(
        empty_df,
        time_column="date",
        value_column="total_cases"
    )

    assert trend.empty


# --------------------------------------------------
# run_analysis
# --------------------------------------------------
def test_run_analysis_summary_only(sample_df):
    results = run_analysis(sample_df)

    assert "summary" in results
    assert isinstance(results["summary"], pd.DataFrame)


def test_run_analysis_grouped(sample_df):
    results = run_analysis(
        sample_df,
        group_by=["continent"]
    )

    assert "grouped_summary" in results
    assert isinstance(results["grouped_summary"], pd.DataFrame)


def test_run_analysis_with_trend(sample_df):
    results = run_analysis(
        sample_df,
        time_column="date",
        value_column="total_cases"
    )

    assert "trend" in results
    assert isinstance(results["trend"], pd.DataFrame)
