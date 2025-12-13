# src/data_cleaning.py

import pandas as pd
from typing import Optional
import logging

from src.logging_conf import log_activity
from src.helper_data_cleaning import (
    clean_missing_core_metrics,
    impute_continent,
    impute_gdp_per_capita,
    final_cleanup,
    convert_to_category,
    normalize_date_column,
)


logger = logging.getLogger(__name__)


@log_activity()
def handle_missing_data(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    """
    Handle missing values on a DataFrame that has already had high-missing /
    redundant columns removed during earlier EDA.

    Behaviour:
    - If df is None → ValueError
    - If df is empty → return empty DataFrame unchanged
    - Drop rows with missing core epidemic metrics
      (new_cases, new_deaths, total_cases, total_deaths)
    - Impute continent using helper (location + aggregate names)
    - Impute gdp_per_capita by continent median
    - Drop any remaining rows containing NaN
    """
    if df is None:
        logger.error("handle_missing_data: The input DataFrame is None.")
        raise ValueError("Input DataFrame is None")

    if df.empty:
        logger.warning("handle_missing_data: The input DataFrame is empty. Returning unchanged.")
        return df.copy() # Preserve columns but nothing to do

    df_clean = df.copy()
    logger.info("handle_missing_data: Starting missing core metrics cleaning.")

    # Drop rows with missing core metrics (no imputation for these)
    df_clean = clean_missing_core_metrics(df_clean)
    logger.info(f"handle_missing_data: Dropped rows with missing core metrics. Remaining rows: {len(df_clean)}.")

    # If everything is gone after dropping core metrics, short-circuit
    if df_clean.empty:
        logger.warning("handle_missing_data: All rows dropped after removing missing core metrics. Returning empty DataFrame.")
        return df_clean

    # Impute continent if both columns present
    if "continent" in df_clean.columns and "location" in df_clean.columns:
        df_clean = impute_continent(df_clean)

    # Impute GDP per capita grouped by continent (if column present)
    if "gdp_per_capita" in df_clean.columns and "continent" in df_clean.columns:
        df_clean = impute_gdp_per_capita(df_clean)

    # Final cleanup: drop any remaining rows with NaN
    df_clean = final_cleanup(df_clean)
    logger.info(f"handle_missing_data: Final cleanup done. Rows remaining: {len(df_clean)}.")

    return df_clean


@log_activity()
def standardize_types(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    """
    Standardize data types for a cleaned DataFrame:

    - If df is None → ValueError
    - If df is empty → return empty DataFrame
    - Convert continent, iso_code, location to category when present
    - Convert date to datetime (invalid strings → NaT)
    """
    if df is None:
        logger.error("standardize_types: Input DataFrame is None.")
        raise ValueError("Input DataFrame is None")

    if df.empty:
        logger.warning("standardize_types: Input DataFrame is empty. Returning unchanged.")
        return df.copy()

    df_std = df.copy()

    # Category conversion (only if columns exist)
    df_std = convert_to_category(df_std)

    # Date conversion if date exists
    if "date" in df_std.columns:
        df_std = normalize_date_column(df_std)
        logger.info("standardize_types: Normalized 'date' column to datetime.")

    logger.info("standardize_types: Type standardization complete.")
    return df_std


@log_activity()
def clean_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """
    Full cleaning pipeline combining:
    1. handle_missing_data
    2. standardize_types
    """
    logger.info("clean_pipeline: Starting full cleaning pipeline.")
    cleaned = handle_missing_data(df)
    final = standardize_types(cleaned)
    logger.info("clean_pipeline: Full cleaning pipeline completed.")
    return final
