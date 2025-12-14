"""
Data loader module for CSV and database operations.
Provides bidirectional conversion between CSV, DataFrame, and Database.

NOTE: Dynamic table creation has been REMOVED.
All operations use statically defined models from models.py
"""

import os
import pandas as pd
import logging
from pathlib import Path
from typing import Dict, Type, Sequence, Union, Optional
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.db_engine import bulk_insert, bulk_replace_table
from src.helper_data_cleaning import normalize_date_column
from src.logging_conf import log_activity

logger = logging.getLogger(__name__)


# ==================== CSV <-> DATAFRAME ====================

@log_activity()
def load_csv_to_df(csv_path: Union[str, Path]) -> pd.DataFrame:
    """
    Load CSV file into pandas DataFrame.
    
    Args:
        csv_path: Path to CSV file
    
    Returns:
        DataFrame with loaded data
    
    Raises:
        FileNotFoundError: If CSV file doesn't exist or path is empty
    """
    # Handle empty or None path
    if not csv_path or csv_path == "":
        logger.error("CSV path is empty")
        raise FileNotFoundError("CSV path cannot be empty")
    
    path = Path(csv_path)
    
    # Check file existence
    if not path.exists():
        logger.error(f"CSV file not found: {path.absolute()}")
        raise FileNotFoundError(f"CSV file not found: {path.absolute()}")
    
    # Load CSV
    df = pd.read_csv(path)
    
    # Normalize date column if present
    if "date" in df.columns:
        df = normalize_date_column(df)
    
    logger.info(f"Loaded CSV: {len(df)} rows, {len(df.columns)} columns from {path.name}")
    return df


@log_activity()
def load_df_to_csv(df: pd.DataFrame, csv_path: str) -> None:
    """
    Write DataFrame to CSV file.
    
    Args:
        df: DataFrame to save
        csv_path: Destination CSV path
    
    Raises:
        ValueError: If DataFrame is None or empty
    """
    if df is None or df.empty:
        logger.error(f"Cannot save empty DataFrame to {csv_path}")
        raise ValueError("DataFrame is empty or None")
    
    try:
        # Create directory if it doesn't exist
        dir_path = os.path.dirname(csv_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        # Save to CSV
        df.to_csv(csv_path, index=False)
        
        logger.info(f"Saved CSV: {len(df)} rows, {len(df.columns)} columns to {csv_path}")
    
    except Exception as e:
        logger.error(f"Failed to save CSV to {csv_path}: {e}")
        raise


# ==================== DATABASE <-> DATAFRAME ====================

@log_activity()
def load_db_to_df(
    engine: Engine, 
    model_class: Type, 
    columns: Optional[Sequence[str]] = None
) -> pd.DataFrame:
    """
    Load all rows from database table into DataFrame.
    
    Args:
        engine: SQLAlchemy engine
        model_class: ORM model class
        columns: Optional list of columns to load (default: all except 'id')
    
    Returns:
        DataFrame with table data
    """
    session = Session(bind=engine)
    
    try:
        # Determine columns to load
        if columns is None:
            columns = [c.name for c in model_class.__table__.columns if c.name != "id"]
        
        # Query all rows
        rows = session.query(model_class).all()
        
        # Convert to DataFrame
        data = [{col: getattr(row, col, None) for col in columns} for row in rows]
        df = pd.DataFrame(data).reset_index(drop=True)
        
        table_name = getattr(model_class, "__tablename__", str(model_class))
        logger.info(f"Loaded from DB: {len(df)} rows, {len(df.columns)} columns from {table_name}")
        
        return df
    
    except Exception as e:
        table_name = getattr(model_class, "__tablename__", str(model_class))
        logger.error(f"Failed to load from {table_name}: {e}")
        raise
    
    finally:
        session.close()


@log_activity()
def load_df_to_db(
    engine: Engine, 
    df: pd.DataFrame, 
    model_class: Type
) -> Type:
    """
    Persist DataFrame into database table.
    
    Uses bulk_replace_table to replace all contents.
    Table must already exist (created via create_all_tables).
    
    Args:
        engine: SQLAlchemy engine
        df: DataFrame to save
        model_class: ORM model class (table must exist)
    
    Returns:
        The model_class used
    
    Raises:
        ValueError: If DataFrame is None or empty
    """
    if df is None or df.empty:
        logger.error(f"Cannot save empty DataFrame to table")
        raise ValueError("DataFrame is empty or None")
    
    try:
        # Replace table contents
        bulk_replace_table(engine, model_class, df)
        logger.info(f"Loaded DataFrame to {model_class.__tablename__}: {len(df)} rows")
        return model_class
    
    except Exception as e:
        logger.error(f"Failed to save to {model_class.__tablename__}: {e}")
        raise


# ==================== CSV <-> DATABASE (Combined Operations) ====================

@log_activity()
def load_csv_to_db(
    engine: Engine, 
    csv_path: Union[str, Path], 
    model_class: Type,
    filter_columns: bool = True
) -> Dict[str, int]:
    """
    Load CSV directly into database table.
    
    Args:
        engine: SQLAlchemy engine
        csv_path: Path to CSV file
        model_class: ORM model class
        filter_columns: If True, filter DataFrame to only model columns
    
    Returns:
        Dictionary with 'inserted' and 'skipped' counts
    """
    # Load CSV
    df = load_csv_to_df(csv_path)
    
    # Filter to valid columns if requested
    if filter_columns:
        valid_cols = [c.name for c in model_class.__table__.columns 
                     if c.name in df.columns and c.name != 'id']
        df_filtered = df[valid_cols]
    else:
        df_filtered = df.drop(columns=['id'], errors='ignore')
    
    # Bulk insert
    records = df_filtered.to_dict(orient="records")
    result = bulk_insert(engine, model_class, records)
    
    logger.info(
        f"CSV->DB: {result['inserted']} inserted, {result['skipped']} skipped "
        f"into {model_class.__tablename__}"
    )
    
    return result


@log_activity()
def load_db_to_csv(
    engine: Engine, 
    model_class: Type, 
    csv_path: str, 
    columns: Optional[Sequence[str]] = None
) -> None:
    """
    Export database table to CSV file.
    Allows empty tables to be exported (schema-only CSV).
    """
    try:
        # Load from database
        df = load_db_to_df(engine, model_class, columns)

        # Ensure destination directory exists
        csv_path = Path(csv_path)
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        # If no rows but we know the schema, construct an empty DF with columns
        if df.empty:
            if columns is not None:
                col_names = list(columns)
            else:
                # get column names from ORM model
                col_names = [c.name for c in model_class.__table__.columns]
            df = pd.DataFrame(columns=col_names)

        # Write CSV directly (empty allowed)
        df.to_csv(csv_path, index=False)

        table_name = getattr(model_class, "__tablename__", str(model_class))
        logger.info(f"Exported {table_name} to {csv_path}: {len(df)} rows")

    except Exception as e:
        table_name = getattr(model_class, "__tablename__", str(model_class))
        logger.error(f"Failed to export {table_name} to {csv_path}: {e}")
        raise
