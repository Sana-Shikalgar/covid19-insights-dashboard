import os
import pandas as pd
import logging
from pathlib import Path
from typing import Dict, Type, Sequence, Union
from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text

from src.db_engine import bulk_insert, bulk_update_table, create_dynamic_table, ensure_orm_model
from src.helper_data_cleaning import normalize_date_column
from src.logging_conf import log_activity

logger = logging.getLogger(__name__)


@log_activity()
def load_csv_to_df(csv_path: Union[str, Path]) -> pd.DataFrame:
    """Load COVID CSV - raises clear FileNotFoundError."""
    path = Path(csv_path) if csv_path != "" else None

    if csv_path == "" or csv_path is None:
        logger.error("CSV not found: empty path provided")
        raise FileNotFoundError("CSV not found: empty path provided")
    
    if not path.exists():
        logger.error(f"CSV file not found at path: {path.absolute()}")
        raise FileNotFoundError("CSV not found at specified path")

    df = pd.read_csv(path)

    if "date" in df.columns:
        normalize_date_column(df)

    logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    return df


@log_activity()
def load_df_to_csv(df: pd.DataFrame, csv_path: str) -> None:
    """Write a DataFrame to CSV, raising if df is None or empty (DF -> CSV)."""
    if df is None or df.empty:
        logger.error("load_df_to_csv called with empty or None DataFrame for path '%s'", csv_path)
        raise ValueError("DataFrame is empty or None")
    
    try:
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        df.to_csv(csv_path, index=False)
        logger.info("load_df_to_csv: wrote DataFrame to %s (rows=%d, cols=%d)", csv_path, len(df), len(df.columns))
    
    except Exception as e:
        logger.error("load_df_to_csv failed for path %s: %s", csv_path, e)
        raise


@log_activity()
def load_db_to_df(engine: Engine, model_class: Type, columns: Sequence[str] | None = None) -> pd.DataFrame:
    """Load all rows from a table into a DataFrame."""
    orm_model = ensure_orm_model(model_class)
    session = Session(bind=engine)
    try:
        if columns is None:
            columns = [c.name for c in model_class.columns if c.name != "id"]
        rows = session.query(orm_model).all()
        data = [{col: getattr(row, col, None) for col in columns} for row in rows]
        df = pd.DataFrame(data).reset_index(drop=True)
        logger.info("load_db_to_df: loaded %d rows and %d columns from %s", len(df), len(df.columns), model_class)
        return df
    except Exception as e:
        logger.error("load_db_to_df failed for table %s: %s", getattr(model_class, "__tablename__", str(orm_model)), e)
        raise
    finally:
        session.close()


@log_activity()
def load_df_to_db(engine: Engine, df: pd.DataFrame, table_name: str, model_class: Type | None = None) -> Type:
    """
    Persist a DataFrame into a database table.
    """
    if df is None or df.empty:
        logger.error("load_df_to_db called with empty or None DataFrame for table '%s'", table_name)
        raise ValueError("DataFrame is empty or None")

    try:
        # Dynamic path: no model_class supplied
        if model_class is None:
            TargetTable = create_dynamic_table(engine, table_name, df)
            bulk_insert(engine, TargetTable, df.to_dict(orient="records"))
            logger.info(
                "load_df_to_db: created table %s and inserted %d rows",
                TargetTable.name,
                len(df),
            )
            return TargetTable

        # ORM model path: decide based on table existence
        table = model_class.__table__
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names(schema=table.schema)
        actual_name = table.name

        if actual_name in existing_tables:
            # Table exists -> bulk replace contents
            bulk_update_table(engine, model_class, df)
            logger.info(
                "load_df_to_db: bulk-updated existing table %s with %d rows",
                actual_name,
                len(df),
            )
            return model_class

        # Table does not exist yet: create from df for schema, then insert via ORM model
        TargetTable = create_dynamic_table(engine, table_name, df)
        bulk_insert(engine, model_class, df.to_dict(orient="records"))
        logger.info(
            "load_df_to_db: created new table %s and inserted %d rows",
            TargetTable.name,
            len(df),
        )
        return model_class

    except Exception as e:
        logger.error(
            "load_df_to_db failed for target '%s' (model=%s): %s",
            table_name,
            getattr(model_class, "__name__", "None"),
            e,
        )
        raise


@log_activity()
def load_csv_to_db(engine: Engine, csv_path: Union[str, Path], model_class) -> Dict[str, int]:
    """
    CSV -> DataFrame -> filter to model columns -> bulk_insert.
    """
    df = load_csv_to_df(csv_path)

    # Filter only columns that exist on the model
    valid_cols = [c.name for c in model_class.__table__.c if c.name in df.columns]
    df_filtered = df[valid_cols]

    records = df_filtered.to_dict(orient="records")
    result = bulk_insert(engine, model_class, records)

    logger.info(
        "Loaded %d rows into %s: %d inserted, %d skipped",
        len(df_filtered),
        model_class.__tablename__,
        result["inserted"],
        result["skipped"],
    )
    return result


@log_activity()
def load_db_to_csv(engine: Engine, model_class: Type, csv_path: str, columns: Sequence[str] | None = None) -> None:
    """Export a DB table to CSV via DataFrame (DB -> DF -> CSV)."""
    try:
        df = load_db_to_df(engine, model_class, columns)
        load_df_to_csv(df=df, csv_path=csv_path)
        logger.info("load_db_to_csv: exported table %s to %s (rows=%d, cols=%d)", model_class, csv_path, len(df), len(df.columns))
    
    except Exception as e:
        logger.error("load_db_to_csv failed for table %s to path %s: %s", getattr(model_class, "__tablename__", str(model_class)), csv_path, e)
        raise
