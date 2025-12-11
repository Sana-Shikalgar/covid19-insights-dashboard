from sqlalchemy import create_engine, Table, MetaData, Column, Integer, String, Float, Date, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError
from typing import Optional
import logging
import pandas as pd

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
    return engine


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
    logging.info(f"Created dynamic table '{table_name}' with {len(columns)} columns")
    return table


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
        logging.info(f"Inserted into {model_class.__tablename__} ID={record_id}")
        return record_id

    except IntegrityError as e:
        session.rollback()
        logging.error(f"Integrity error inserting into {model_class.__tablename__}: {e}")
        raise
    except Exception as e:
        session.rollback()
        logging.error(f"Insert failed for {model_class.__tablename__}: {e}")
        raise
    finally:
        session.close()

