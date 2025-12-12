# src/main.py
import os
import logging

from src.db_engine import get_engine
from src.data_loader import (
    load_db_to_df,
    load_df_to_db,
    load_csv_to_db,
    load_csv_to_df,
)
from src.helper_data_cleaning import assess_data, CORE_COLS
from src.data_cleaner import (
    handle_missing_data,
    standardize_types,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    project_root = os.path.dirname(os.path.abspath(__file__))

    # Single DB file
    database_path = os.path.join(project_root, "database", "covid_dashboard.db")
    os.makedirs(os.path.dirname(database_path), exist_ok=True)

    engine = get_engine(f"sqlite:///{database_path}")

    # 1) Load raw CSV into a dynamic table "raw_data"
    try:
        raw_csv_path = os.path.join(project_root, "data", "raw", "owid-covid-data.csv")
        logger.info("Step 1: Loading raw CSV into raw_data table")
        
        # FIXED: Use load_df_to_df + load_df_to_db (correct flow for dynamic tables)
        raw_df = load_csv_to_df(raw_csv_path)  # Load CSV -> DF
        RawTable = load_df_to_db(              # DF -> dynamic table
            engine=engine,
            df=raw_df,
            table_name="raw_data",
            model_class=None,                  # Dynamic table
        )
    except FileNotFoundError as e:
        logger.error(f"Expected CSV not found at {raw_csv_path}")
        raise


    # 2) Select CORE_COLS from raw_data -> cleaned pipeline -> cleaned_data table
    logger.info("Step 2: Creating cleaned_data table from raw_data")

    raw_db_df = load_db_to_df(engine, RawTable)
    print("Raw data shape:", raw_db_df.shape)  # Should print (429435, 67)
    semi_df = raw_db_df[CORE_COLS].copy()
    print("Semi-cleaned shape:", semi_df.shape) # After CORE_COLS filter

    # Cleaning pipeline (reusing your higher-level functions)
    cleaned_step1 = handle_missing_data(semi_df)
    cleaned_final = standardize_types(cleaned_step1)

    # Optional: initial assessment log
    assess_data(cleaned_final)

    CleanedTable = load_df_to_db(
        engine=engine,
        df=cleaned_final,
        table_name="cleaned_data",
        model_class=None,           # dynamic cleaned table
    )

    logger.info(
        "Pipeline completed. Raw table=%s, Cleaned table=%s",
        getattr(RawTable, "name", str(RawTable)),
        getattr(CleanedTable, "name", str(CleanedTable)),
    )


if __name__ == "__main__":
    main()
