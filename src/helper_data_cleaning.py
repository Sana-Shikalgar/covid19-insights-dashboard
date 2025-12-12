import pandas as pd
import numpy as np
import logging


logger = logging.getLogger(__name__)

# -------------------------------------------------------------
# CORE VALIDATION 
# -------------------------------------------------------------
def validate_dataframe_content(df):
    """Check if the DataFrame is not empty."""
    if df.empty:
        logger.error("Dataset loaded but is empty")
        raise ValueError("Dataset is empty")
    logger.info(f"Loaded: {df.shape}")
    return True


# -------------------------------------------------------------
# DATA ASSESSMENT FUNCTIONS
# -------------------------------------------------------------

CORE_COLS = [
    'gdp_per_capita', 'continent', 'new_cases', 'new_deaths',
    'total_cases', 'total_deaths', 'location', 'date', 
    'iso_code', 'population'
]

def check_required_columns(df, core_cols):
    """Check for the presence of all required columns."""
    if not all(col in df.columns for col in core_cols):
        missing_cols = [c for c in core_cols if c not in df.columns]
        logger.error(f"Missing required columns: {missing_cols}")
        raise ValueError("Required columns missing")


def calculate_missing_values(df, core_cols):
    """Calculate and log missing values for core columns."""
    missing = df[core_cols].isnull().sum()
    logger.info(f"Missing values: {missing.to_dict()}")
    return missing


def calculate_missing_percentages(df, missing_counts):
    """Calculate percentage of missing values per column."""
    try:
        missing_percent = (missing_counts / len(df)) * 100
        return missing_percent.round(2)
    except Exception as e:
        logger.error(f"Failed to calculate missing percentages: {e}")
        raise


def print_assessment_summary(df, missing):
    """Print the initial data quality assessment summary."""
    print("\n=== INITIAL ASSESSMENT ===")
    print(f"Shape: {df.shape}")
    print("\nMissing values:")
    print(missing)
    print(f"\nMemory: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
    logger.info(f"Initial assessment: shape={df.shape}")


def assess_data(df):
    """Initial data quality assessment (Orchestrator)."""
    try:
        check_required_columns(df, CORE_COLS)
        missing_counts = calculate_missing_values(df, CORE_COLS)
        missing_percent = calculate_missing_percentages(df, missing_counts)

        missing_summary = pd.DataFrame({
            'missing_count': missing_counts,
            'missing_percent': missing_percent
        })

        logger.info(f"Initial assessment: shape={df.shape}")
        return missing_summary
    except Exception as e:
        logger.error(f"Assessment failed: {e}")
        raise


# -------------------------------------------------------------
# CLEANING FUNCTIONS
# -------------------------------------------------------------

def clean_missing_core_metrics(df):
    """Step 1: Drop rows missing key case/death metrics."""
    try:
        core_cols = ['new_cases', 'new_deaths', 'total_cases', 'total_deaths']
        df_clean = df.dropna(subset=core_cols).copy()
        retention = 100 * (len(df_clean) / len(df))

        logger.info(f"Core metric cleaning: retention={retention:.1f}%, shape: {df_clean.shape}")
        return df_clean
    except Exception as e:
        logger.error(f"Core metrics cleaning failed: {e}")
        raise


def create_continent_location_map(df):
    """Create a map of location to continent from non-missing rows."""
    continent_map = (
        df.dropna(subset=['continent'])
        .drop_duplicates('location')[['location', 'continent']]
        .set_index('location')['continent']
        .to_dict()
    )
    return continent_map


def impute_continent_by_location(df, continent_map):
    """Impute missing continent using location-to-continent map."""
    df['continent'] = df['location'].map(continent_map).fillna(df['continent'])
    return df


def impute_continent_by_aggregate(df):
    """Impute remaining missing continent using aggregate location names."""
    aggregate_map = {
        'Africa': 'Africa', 'Asia': 'Asia', 'Europe': 'Europe',
        'European Union (27)': 'Europe', 'North America': 'North America',
        'Oceania': 'Oceania', 'South America': 'South America',
        'World': 'World', 'High-income countries': 'High-income',
        'Low-income countries': 'Low-income',
        'Lower-middle-income countries': 'Lower-middle-income',
        'Upper-middle-income countries': 'Upper-middle-income'
    }
    df['continent'] = df['continent'].fillna(df['location'].map(aggregate_map)).astype(object)

    return df


def impute_continent(df):
    """Impute continent values using mapping + aggregate logic (Orchestrator)."""
    try:
        continent_map = create_continent_location_map(df)
        df = impute_continent_by_location(df, continent_map)
        df = impute_continent_by_aggregate(df)

        missing = df['continent'].isnull().sum()
        logger.info(f"Continent imputation: missing={missing}")

        if missing > 0:
            logger.warning("Some continent values remain missing after imputation")
        return df
    except Exception as e:
        logger.error(f"Continent imputation failed: {e}")
        raise


def impute_gdp_per_capita(df):
    """Median GDP per capita imputation grouped by continent."""
    try:
        df['gdp_per_capita'] = df.groupby('continent')['gdp_per_capita'].transform(
            lambda x: x.fillna(x.median() if x.notna().any() else np.nan)
        )
        missing = df['gdp_per_capita'].isnull().sum()
        logger.info(f"GDP imputation: missing={missing}")
        return df
    except Exception as e:
        logger.error(f"GDP imputation failed: {e}")
        raise


def final_cleanup(df):
    """Remove any remaining missing values."""
    try:
        initial = len(df)
        df_cleaned = df.dropna()
        retention = 100 * (len(df_cleaned) / initial)

        logger.info(f"Final cleanup: retention={retention:.1f}%, shape: {df_cleaned.shape}")
        return df_cleaned
    except Exception as e:
        logger.error(f"Final cleanup failed: {e}")
        raise


# -------------------------------------------------------------
# DTYPE OPTIMIZATION & VALIDATION
# -------------------------------------------------------------

def convert_to_category(df):
    """Convert specified string columns to category for memory optimization."""
    cols = [c for c in ['continent', 'iso_code', 'location'] if c in df.columns]
    if cols:
        df[cols] = df[cols].astype('category')
    return df


def normalize_date_column(df):
    """Convert and normalize the 'date' column to datetime."""
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    return df


def optimize_dtypes(df):
    """Optimize memory usage (Orchestrator)."""
    try:
        before = df.memory_usage(deep=True).sum() / 1024**2
        
        df = convert_to_category(df)
        df = normalize_date_column(df)

        after = df.memory_usage(deep=True).sum() / 1024**2
        savings = (before - after) / before * 100

        logger.info(f"Dtype optimization: savings={savings:.1f}%")

        return df
    except Exception as e:
        logger.error(f"Dtype optimization failed: {e}")
        raise


def validate_data(df):
    """Final summary of cleaned dataset."""
    try:
        print("\n=== FINAL SUMMARY ===")
        print(f"Shape: {df.shape}")
        print(f"Memory: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
        print(f"Date range: {df['date'].min().date()} → {df['date'].max().date()}")
        print(f"Countries: {df['location'].nunique()}")
        print(f"Continents: {df['continent'].nunique()}")
        logger.info("Validation completed successfully")
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise

