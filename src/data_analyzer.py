import pandas as pd
from typing import List, Optional, Dict
import logging 
from src.logging_conf import log_activity

logger = logging.getLogger(__name__)

# --------------------------------------------------
# Summary metrics (no grouping)
# --------------------------------------------------
@log_activity()
def calculate_summary_metrics(
    df: pd.DataFrame,
    numeric_columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Calculate basic summary statistics (mean, min, max, count)
    for numeric columns in the DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame containing the data.
    numeric_columns : list[str], optional
        List of numeric columns to summarise. If None, all numeric
        columns are automatically selected.

    Returns
    -------
    pd.DataFrame
        A DataFrame with one row per numeric column and the
        calculated summary metrics.
    """
    if df.empty:
        return pd.DataFrame()

    if numeric_columns is None:
        numeric_columns = df.select_dtypes(include="number").columns.tolist()

    summary_df = (
        df[numeric_columns]
        .agg(["mean", "min", "max", "count"])
        .transpose()
        .reset_index()
        .rename(columns={"index": "metric"})
    )
    logger.info(f"Calculate basic summury metrics for numeric columns in the Dataframe.")
    return summary_df


# --------------------------------------------------
# Grouped summary metrics
# --------------------------------------------------
@log_activity()
def generate_grouped_summary(
    df: pd.DataFrame,
    group_by: List[str],
    numeric_columns: Optional[List[str]] = None,
    metrics: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Generate grouped summary statistics (mean, min, max, count)
    for one or more grouping columns.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.
    group_by : list[str]
        Column(s) to group by (e.g. ['location'], ['continent', 'year']).
    numeric_columns : list[str], optional
        Numeric columns to aggregate. If None, all numeric columns are used.
    metrics : list[str], optional
        Aggregation metrics to apply. Defaults to ['mean', 'min', 'max', 'count'].

    Returns
    -------
    pd.DataFrame
        A grouped summary DataFrame suitable for plotting or export.
    """
    if df.empty:
        logger.warning("The dataframe is empty.")
        return pd.DataFrame()

    if numeric_columns is None:
        numeric_columns = df.select_dtypes(include="number").columns.tolist()

    if metrics is None:
        metrics = ["mean", "min", "max", "count"]

    grouped_df = (
        df.groupby(group_by)[numeric_columns]
        .agg(metrics)
    )

    # Flatten multi-level column names
    grouped_df.columns = [
        f"{col}_{metric}" for col, metric in grouped_df.columns
    ]

    logger.info(f"Generate grouped summary statistics on: {group_by}")
    return grouped_df.reset_index()


# --------------------------------------------------
# Time trend analysis
# --------------------------------------------------
@log_activity()
def generate_time_trend(
    df: pd.DataFrame,
    time_column: str,
    value_column: str,
    group_by: Optional[List[str]] = None,
    freq: Optional[str] = None,
) -> pd.DataFrame:
    """
    Generate a time-based trend (mean value over time).

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.
    time_column : str
        Column representing time (e.g. 'date', 'year', 'month').
    value_column : str
        Numeric column to analyse over time.
    group_by : list[str], optional
        Additional columns to group by (e.g. ['location']).
    freq : str, optional
        Pandas resampling frequency ('D', 'M', 'Y').
        Only applicable when time_column is a datetime column.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing time-based trend values.
    """
    if df.empty:
        logger.warning("The dataframe is empty.")
        return pd.DataFrame()

    data = df.copy()

    if freq:
        data[time_column] = pd.to_datetime(data[time_column])
        data = data.set_index(time_column)

        if group_by:
            trend_df = (
                data.groupby(group_by)
                .resample(freq)[value_column]
                .mean()
                .reset_index()
            )
        else:
            trend_df = (
                data.resample(freq)[value_column]
                .mean()
                .reset_index()
            )
    else:
        if group_by:
            trend_df = (
                data.groupby(group_by + [time_column])[value_column]
                .mean()
                .reset_index()
            )
        else:
            trend_df = (
                data.groupby(time_column)[value_column]
                .mean()
                .reset_index()
            )

    logger.info(f"Generate time based trend on {group_by} via {time_column}")
    return trend_df


# --------------------------------------------------
# High-level analysis wrapper
# --------------------------------------------------
@log_activity()
def run_analysis(
    df: pd.DataFrame,
    group_by: Optional[List[str]] = None,
    time_column: Optional[str] = None,
    value_column: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Run a standard analysis pipeline on the given DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    group_by : list[str], optional
        Grouping columns for summary analysis.
    time_column : str, optional
        Time column for trend analysis.
    value_column : str, optional
        Numeric column for trend analysis.

    Returns
    -------
    dict[str, pd.DataFrame]
        Dictionary containing generated analysis results.
    """
    results = {
        "summary": calculate_summary_metrics(df)
    }

    if group_by:
        results["grouped_summary"] = generate_grouped_summary(df, group_by)

    if time_column and value_column:
        results["trend"] = generate_time_trend(
            df,
            time_column=time_column,
            value_column=value_column,
        )
    logger.info(f"Run complete summary.")
    return results
