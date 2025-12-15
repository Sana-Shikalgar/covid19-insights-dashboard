"""
Pipeline orchestrator for COVID-19 health data system.

Implements the complete data governance pipeline:
1. Raw Data Ingestion (Immutable Layer)
2. Data Cleaning and Validation
3. Operational Copy Creation (Mutable Layer)
4. CRUD Operations (Working Copy Only)
5. Data Analysis and Visualization

All operations follow TDD principles and data governance best practices.
"""

import pandas as pd
from pathlib import Path
from sqlalchemy import Engine
import logging

from src.logging_conf import log_activity, log_user_action
from src.db_engine import (
    get_engine, create_all_tables, table_exists, 
    get_table_row_count, bulk_replace_table
)
from src.data_loader import load_csv_to_df, load_df_to_db, load_db_to_df
from src.data_cleaner import clean_pipeline
from src.helper_data_cleaning import CORE_COLS
from src.models import CovidDataRaw, CovidDataClean, CovidDataWorking

logger = logging.getLogger(__name__)


# ==================== PIPELINE CONFIGURATION ====================

class PipelineConfig:
    """Configuration for the data pipeline."""
    
    RAW_CSV_PATH = "data/raw/owid-covid-data.csv"
    DATABASE_DIR = "database"
    
    # Table configuration
    RAW_TABLE = CovidDataRaw
    CLEAN_TABLE = CovidDataClean
    WORKING_TABLE = CovidDataWorking


# ==================== PIPELINE STATUS ====================

@log_activity("Check pipeline status")
def check_pipeline_status(engine: Engine) -> dict:
    """
    Check which pipeline stages have been completed.
    
    Args:
        engine: Database engine
    
    Returns:
        Dictionary with status of each stage
    """
    status = {
        'raw_exists': table_exists(engine, CovidDataRaw.__tablename__),
        'clean_exists': table_exists(engine, CovidDataClean.__tablename__),
        'working_exists': table_exists(engine, CovidDataWorking.__tablename__),
        'raw_count': 0,
        'clean_count': 0,
        'working_count': 0
    }
    
    # Get row counts if tables exist
    if status['raw_exists']:
        status['raw_count'] = get_table_row_count(engine, CovidDataRaw)
    
    if status['clean_exists']:
        status['clean_count'] = get_table_row_count(engine, CovidDataClean)
    
    if status['working_exists']:
        status['working_count'] = get_table_row_count(engine, CovidDataWorking)
    
    logger.info(f"Pipeline status: {status}")
    return status


@log_activity("Check if pipeline needs execution")
def pipeline_needs_execution(engine: Engine) -> bool:
    """
    Determine if the full pipeline needs to be executed.
    
    Pipeline runs only if ALL three tables are missing or empty.
    
    Args:
        engine: Database engine
    
    Returns:
        True if pipeline should run, False otherwise
    """
    status = check_pipeline_status(engine)
    
    # Pipeline runs if any table is missing or empty
    needs_run = (
        not status['raw_exists'] or status['raw_count'] == 0 or
        not status['clean_exists'] or status['clean_count'] == 0 or
        not status['working_exists'] or status['working_count'] == 0
    )
    
    if needs_run:
        logger.info("Pipeline execution required")
    else:
        logger.info("Pipeline already complete - tables exist and have data")
    
    return needs_run


# ==================== STAGE 1: RAW DATA INGESTION ====================

@log_activity("Stage 1: Raw data ingestion")
def stage1_ingest_raw_data(
    engine: Engine, 
    csv_path: str = PipelineConfig.RAW_CSV_PATH
) -> pd.DataFrame:
    """
    Stage 1: Ingest raw CSV data into immutable raw table.
    
    This stage:
    - Loads CSV file from data directory
    - Persists to CovidDataRaw table (all fields nullable)
    - Returns DataFrame for next stage
    
    Args:
        engine: Database engine
        csv_path: Path to raw CSV file
    
    Returns:
        Raw DataFrame
    
    Raises:
        FileNotFoundError: If CSV file doesn't exist
    """
    log_user_action("Pipeline Stage 1: Starting raw data ingestion")
    
    # Check if raw table already has data
    if table_exists(engine, CovidDataRaw.__tablename__):
        row_count = get_table_row_count(engine, CovidDataRaw)
        if row_count > 0:
            logger.info(f"Raw table already populated with {row_count} rows - loading from DB")
            return load_db_to_df(engine, CovidDataRaw)
    
    # Load CSV
    logger.info(f"Loading raw CSV from {csv_path}")
    df_raw = load_csv_to_df(csv_path)
    
    # Filter to only columns that exist in CovidDataRaw model
    model_cols = [c.name for c in CovidDataRaw.__table__.columns if c.name != 'id']
    available_cols = [col for col in model_cols if col in df_raw.columns]
    df_filtered = df_raw[available_cols]
    
    # Persist to raw table
    logger.info(f"Persisting {len(df_filtered)} rows to raw table")
    load_df_to_db(engine, df_filtered, CovidDataRaw)
    
    log_user_action("Pipeline Stage 1: Raw data ingestion complete", 
                   {"rows": len(df_filtered), "columns": len(df_filtered.columns)})
    
    return df_filtered


# ==================== STAGE 2: DATA CLEANING ====================

@log_activity("Stage 2: Data cleaning and validation")
def stage2_clean_and_validate(
    engine: Engine, 
    df_raw: pd.DataFrame
) -> pd.DataFrame:
    """
    Stage 2: Clean and validate data, persist to clean reference table.
    
    This stage:
    - Applies full cleaning pipeline
    - Validates all fields are non-null
    - Persists to CovidDataClean table (all fields NOT NULL)
    - Returns cleaned DataFrame
    
    Args:
        engine: Database engine
        df_raw: Raw DataFrame from Stage 1
    
    Returns:
        Cleaned DataFrame
    """
    log_user_action("Pipeline Stage 2: Starting data cleaning")
    
    # Check if clean table already has data
    if table_exists(engine, CovidDataClean.__tablename__):
        row_count = get_table_row_count(engine, CovidDataClean)
        if row_count > 0:
            logger.info(f"Clean table already populated with {row_count} rows - loading from DB")
            return load_db_to_df(engine, CovidDataClean)

    # Select only CORE_COLS from raw DataFrame
    df_raw_core = df_raw[CORE_COLS] 

    # Apply cleaning pipeline
    logger.info(f"Applying cleaning pipeline to {len(df_raw)} rows")
    df_clean = clean_pipeline(df_raw_core)
    
    # Filter to only core columns (clean table has subset of raw columns)
    model_cols = [c.name for c in CovidDataClean.__table__.columns if c.name != 'id']
    df_clean_filtered = df_clean[model_cols]
    
    # Validate no nulls remain
    null_counts = df_clean_filtered.isnull().sum()
    if null_counts.any():
        logger.warning(f"Null values found after cleaning: {null_counts[null_counts > 0].to_dict()}")
        # Drop rows with any nulls to ensure clean table integrity
        df_clean_filtered = df_clean_filtered.dropna()
    
    # Persist to clean table
    logger.info(f"Persisting {len(df_clean_filtered)} rows to clean reference table")
    load_df_to_db(engine, df_clean_filtered, CovidDataClean)
    
    log_user_action("Pipeline Stage 2: Data cleaning complete",
                   {"rows": len(df_clean_filtered), "null_rows_dropped": len(df_clean) - len(df_clean_filtered)})
    
    return df_clean_filtered


# ==================== STAGE 3: WORKING COPY CREATION ====================

@log_activity("Stage 3: Working copy creation")
def stage3_create_working_copy(
    engine: Engine, 
    df_clean: pd.DataFrame
) -> pd.DataFrame:
    """
    Stage 3: Create working copy from clean reference table.
    
    This stage:
    - Copies all data from clean table to working table
    - Working table is the ONLY table where CRUD operations are allowed
    - Returns working DataFrame
    
    Args:
        engine: Database engine
        df_clean: Cleaned DataFrame from Stage 2
    
    Returns:
        Working copy DataFrame
    """
    log_user_action("Pipeline Stage 3: Creating working copy")
    
    # Check if working table already has data
    if table_exists(engine, CovidDataWorking.__tablename__):
        row_count = get_table_row_count(engine, CovidDataWorking)
        if row_count > 0:
            logger.info(f"Working table already populated with {row_count} rows")
            return load_db_to_df(engine, CovidDataWorking)
    
    # Create working copy
    logger.info(f"Creating working copy with {len(df_clean)} rows")
    load_df_to_db(engine, df_clean, CovidDataWorking)
    
    log_user_action("Pipeline Stage 3: Working copy created",
                   {"rows": len(df_clean)})
    
    return df_clean.copy()


# ==================== STAGE 4: PIPELINE EXECUTION ====================

@log_activity("Execute full pipeline")
def execute_pipeline(
    engine: Engine = None, 
    csv_path: str = PipelineConfig.RAW_CSV_PATH,
    force: bool = False
) -> dict:
    """
    Execute the complete data pipeline.
    
    Runs all stages in sequence:
    1. Raw data ingestion
    2. Data cleaning and validation
    3. Working copy creation
    
    Args:
        engine: Database engine (creates new if None)
        csv_path: Path to raw CSV file
        force: If True, re-run pipeline even if tables exist
    
    Returns:
        Dictionary with pipeline results
    """
    log_user_action("Pipeline: Starting full execution")
    
    # Create engine if not provided
    if engine is None:
        engine = get_engine(db_dir=PipelineConfig.DATABASE_DIR)
    
    # Create all tables
    create_all_tables(engine)
    
    # Check if pipeline needs to run
    if not force and not pipeline_needs_execution(engine):
        logger.info("Pipeline already complete - skipping execution")
        status = check_pipeline_status(engine)
        return {
            'executed': False,
            'reason': 'Tables already exist with data',
            'status': status
        }
    
    # Stage 1: Raw data ingestion
    df_raw = stage1_ingest_raw_data(engine, csv_path)
    
    # Stage 2: Data cleaning
    df_clean = stage2_clean_and_validate(engine, df_raw)
    
    # Stage 3: Working copy
    df_working = stage3_create_working_copy(engine, df_clean)
    
    # Get final status
    status = check_pipeline_status(engine)
    
    log_user_action("Pipeline: Full execution complete", 
                   {"raw_rows": status['raw_count'],
                    "clean_rows": status['clean_count'],
                    "working_rows": status['working_count']})
    
    return {
        'executed': True,
        'status': status,
        'raw_shape': df_raw.shape,
        'clean_shape': df_clean.shape,
        'working_shape': df_working.shape
    }


# ==================== UTILITY FUNCTIONS ====================

@log_activity("Reset working copy from clean reference")
def reset_working_copy(engine: Engine) -> int:
    """
    Reset working copy by re-copying from clean reference table.
    
    This allows users to discard all CRUD changes and start fresh.
    
    Args:
        engine: Database engine
    
    Returns:
        Number of rows copied
    """
    log_user_action("Resetting working copy from clean reference")
    
    # Load clean reference data
    df_clean = load_db_to_df(engine, CovidDataClean)
    
    # Replace working table contents
    bulk_replace_table(engine, CovidDataWorking, df_clean)
    
    logger.info(f"Reset working copy: {len(df_clean)} rows")
    return len(df_clean)


@log_activity("Load data by layer")
def load_data_by_layer(engine: Engine, layer: str) -> pd.DataFrame:
    """
    Load data from specified layer.
    
    Args:
        engine: Database engine
        layer: 'raw', 'clean', or 'working'
    
    Returns:
        DataFrame from specified layer
    
    Raises:
        ValueError: If invalid layer specified
    """
    from src.models import get_model_by_layer
    
    model = get_model_by_layer(layer)
    df = load_db_to_df(engine, model)
    
    log_user_action(f"Loaded data from {layer} layer", {"rows": len(df)})
    return df