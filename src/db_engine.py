from sqlalchemy import create_engine, Table, MetaData, Column, Integer, String, Float, Date, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError
from typing import Optional
import pandas as pd
from typing import List, Dict, Any
import logging


logger = logging.getLogger(__name__)


# Initialize the ORM base class
Base = declarative_base()


def get_engine(db_url: Optional[str] = None) -> create_engine:
    db_url = db_url or "sqlite:///health_data.db"
    engine = create_engine(
        db_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={'check_same_thread': False}  # SQLite threading
    )
    logger.info(f"Created engine for DB URL: {db_url}")
    return engine


# Define a sample ORM model for test and setup validation
class ExampleTable(Base):
    """
    Example table schema for initial DB setup and test verification.
    Replace this with actual dataset table models later.
    """
    __tablename__ = "example_table"

    id = Column(Integer, primary_key=True, autoincrement=True)
    iso_code = Column(String(100), nullable=False, unique=True)
    value = Column(Float, nullable=True)
    country = Column(String(255), nullable=True)


def infer_sqlalchemy_type(series):
    if pd.api.types.is_datetime64_any_dtype(series) or "date" in series.name.lower():
        return Date
    if pd.api.types.is_numeric_dtype(series):
        return Float
    if pd.api.types.is_bool_dtype(series):
        return Boolean
    return String(255)


# Creating a dynamic table schema using SQLAlchemy ORM
def create_dynamic_table(engine, table_name: str, df: pd.DataFrame) -> Table:
    """
    Dynamically create table schema from pandas DataFrame (handles 67 fields automatically).
    
    Args:
        engine: SQLAlchemy engine
        table_name: Name for the table (e.g., 'covid_data')
        df: Sample DataFrame to infer schema from first row
    
    Returns:
        SQLAlchemy Table object
    """
    metadata = MetaData()
    
    # Infer column types from DataFrame (handles nulls gracefully)
    columns = []
    for col in df.columns:
        col_type = infer_sqlalchemy_type(df[col])
        # name must be first arg
        columns.append(Column(col, col_type, nullable=True))

    table = Table(table_name, metadata, *columns, extend_existing=True)
    metadata.create_all(engine)
    logger.info(f"Created dynamic table '{table_name}' with {len(columns)} columns")
    return table


def get_session(engine):
    """
    Create session factory with BEST PRACTICES: autoflush=False, autocommit=False.
    This prevents unexpected behavior during tests and operations.
    """
    SessionLocal = sessionmaker(
        bind=engine, 
        autoflush=False,  # Prevents unexpected flushes
        autocommit=False,  # Explicit control over commits
        expire_on_commit=False  # Keeps objects usable after commit
    )
    logger.info("Created new SQLAlchemy session factory with best practices")
    return SessionLocal



def insert_record(engine, model_class, record_data: dict) -> int:
    """
    Insert a single record using a SQLAlchemy ORM model class.

    Args:
        engine: SQLAlchemy engine instance
        model_class: ORM class, e.g. ExampleTable
        record_data: dict of field_name -> value

    Returns:
        int: primary key ID of inserted row
    """
    if not record_data:
        raise ValueError("record_data cannot be empty")

    SessionLocal = get_session(engine)
    session = SessionLocal()
    try:
        new_record = model_class(**record_data)
        session.add(new_record)
        session.commit()
        record_id = new_record.id
        logger.info(f"Inserted into {model_class.__tablename__} ID={record_id}")
        return record_id

    except IntegrityError as e:
        session.rollback()
        logger.error(f"Integrity error inserting into {model_class.__tablename__}: {e}")
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Insert failed for {model_class.__tablename__}: {e}")
        raise
    finally:
        session.close()


def bulk_insert(engine, model_class, records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Bulk insert with duplicate skipping (NO full rollback)."""
    if not records:
        return {"inserted": 0, "skipped": 0}
    
    SessionLocal = get_session(engine)
    inserted = 0
    skipped = 0
    
    for record_data in records:
        session = SessionLocal()
        try:
            # Create and save individually (no transaction coupling)
            new_record = model_class(**record_data)
            session.add(new_record)
            session.commit()  # Commit IMMEDIATELY
            inserted += 1
        except IntegrityError:
            skipped += 1
            session.rollback()
        except Exception:
            skipped += 1
            session.rollback()
        finally:
            session.close()
    
    logger.info(f"Bulk insert: {inserted} inserted, {skipped} skipped")
    return {"inserted": inserted, "skipped": skipped}


def get_all_records(engine, model_class) -> List[Any]:
    """
    Retrieve ALL records from the given model class.
    
    Args:
        engine: SQLAlchemy engine
        model_class: ORM model class (e.g., ExampleTable)
    
    Returns:
        List of all records
    """
    SessionLocal = get_session(engine)
    session = SessionLocal()
    try:
        records = session.query(model_class).all()
        logger.info(f"Fetched all records from {model_class.__tablename__}, count={len(records)}")
        return records
    finally:
        session.close()


def filter_by_columns(engine, model_class, filters: Dict[str, Any]) -> List[Any]:
    """
    Filter records using .filter() on multiple columns.
    
    Args:
        engine: DB engine
        model_class: ExampleTable or other ORM class
        filters: Dict of {column_name: value}, e.g. {"iso_code": "USA", "value": 100.0}
    
    Returns:
        List of matching records
    
    Raises:
        ValueError: Invalid column name
    """
    if not filters:
        return get_all_records(engine, model_class)
    
    SessionLocal = get_session(engine)
    session = SessionLocal()
    try:
        query = session.query(model_class)
        
        for column_name, value in filters.items():
            # Validate column exists using getattr
            column = getattr(model_class, column_name, None)
            if column is None:
                raise ValueError(f"Invalid column name: '{column_name}'")
            
            # Apply filter using .filter()
            query = query.filter(column == value)
        
        records = query.all()
        logger.info(f"Fetch {model_class.__tablename__} with filters as: {filters}")
        return records
    finally:
        session.close()
