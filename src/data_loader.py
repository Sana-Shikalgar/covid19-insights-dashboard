import pandas as pd
from pathlib import Path
from typing import Union
from typing import Dict
from src.db_engine import bulk_insert
import logging


logger = logging.getLogger(__name__)


def load_csv_data(csv_path: Union[str, Path]) -> pd.DataFrame:
    """Load COVID CSV - raises clear FileNotFoundError."""
    path = Path(csv_path) if csv_path != "" else None

    if csv_path == "" or csv_path is None:
        logger.error("CSV not found: empty path provided")
        raise FileNotFoundError("CSV not found: empty path provided")
    
    if not path.exists():
        logger.error(f"CSV file not found at path: {path.absolute()}")
        raise FileNotFoundError("CSV not found at specified path")

    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    return df


def load_csv_to_db(engine, csv_path: Union[str, Path], model_class) -> Dict[str, int]:
    """
    CSV → DataFrame → List[dict] → bulk_insert (your existing function!)
    
    Args:
        engine: SQLAlchemy engine
        csv_path: Path to CSV
        model_class: ORM model (default: ExampleTable)
    
    Returns:
        {"inserted": X, "skipped": Y} from bulk_insert
    """
    df = load_csv_data(csv_path)

    valid_cols = [c.name for c in model_class.__table__.c if c.name in df.columns]
    df_filtered = df[valid_cols]

    records = df_filtered.to_dict(orient='records')
    result = bulk_insert(engine, model_class, records)
    
    logger.info(f"Loaded {len(df_filtered)} rows into {model_class.__tablename__}: "
                 f"{result['inserted']} inserted, {result['skipped']} skipped")
    return result