"""
Database engine module for SQLAlchemy operations.
Provides CRUD operations and table management for COVID-19 health data.

NOTE: Dynamic table creation has been REMOVED.
All table structures are defined statically in models.py
"""

from sqlalchemy import create_engine, update, insert, Engine, MetaData, inspect
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError
from typing import Optional, List, Dict, Any, Type
import pandas as pd
import logging
from pathlib import Path

# Import Base from models (single source of truth)
from src.models import Base

from src.logging_conf import log_activity

logger = logging.getLogger(__name__)



# ==================== ENGINE & SESSION ====================

@log_activity()
def get_engine(db_url: Optional[str] = None, db_dir: str = "database") -> Engine:
    """
    Create and configure SQLAlchemy engine.
    
    Args:
        db_url: Database URL (default: sqlite:///database/health_data.db)
        db_dir: Directory for database files (default: 'database')
    
    Returns:
        Configured SQLAlchemy Engine instance
    """
    if db_url is None:
        # Ensure database directory exists
        db_path = Path(db_dir)
        db_path.mkdir(exist_ok=True, parents=True)
        
        db_file = db_path / "health_data.db"
        db_url = f"sqlite:///{db_file}"
    
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


@log_activity(message="Create SQLAlchemy session factory")
def get_session(engine: Engine) -> sessionmaker:
    """
    Create session factory with best practices.
    
    Args:
        engine: SQLAlchemy engine instance
    
    Returns:
        Configured sessionmaker factory
    """
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False
    )
    logger.info("Created SQLAlchemy session factory")
    return SessionLocal


# ==================== TABLE MANAGEMENT ====================

@log_activity()
def create_all_tables(engine: Engine) -> None:
    """
    Create all tables defined in Base metadata if they don't exist.
    
    Args:
        engine: SQLAlchemy engine
    """
    Base.metadata.create_all(engine)
    logger.info("Created all tables from Base metadata")


@log_activity()
def table_exists(engine: Engine, table_name: str) -> bool:
    """
    Check if a table exists in the database.
    
    Args:
        engine: SQLAlchemy engine
        table_name: Name of table to check
    
    Returns:
        True if table exists, False otherwise
    """
    inspector = inspect(engine)
    exists = table_name in inspector.get_table_names()
    logger.info(f"Table '{table_name}' exists: {exists}")
    return exists


@log_activity()
def get_table_row_count(engine: Engine, model_class: Type) -> int:
    """
    Get the number of rows in a table.
    
    Args:
        engine: SQLAlchemy engine
        model_class: ORM model class
    
    Returns:
        Number of rows in table
    """
    SessionLocal = get_session(engine)
    session = SessionLocal()
    
    try:
        count = session.query(model_class).count()
        table_name = getattr(model_class, "__tablename__", str(model_class))
        logger.info(f"Table '{table_name}' has {count} rows")
        return count
    finally:
        session.close()


# ==================== CREATE OPERATIONS ====================

@log_activity(message="Insert single record")
def insert_record(engine: Engine, model_class: Type, record_data: dict) -> int:
    """
    Insert a single record using ORM model.
    
    Args:
        engine: SQLAlchemy engine
        model_class: ORM model class
        record_data: Dictionary of field_name -> value
    
    Returns:
        Primary key ID of inserted row
    
    Raises:
        ValueError: If record_data is empty
        IntegrityError: If duplicate key or constraint violation
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
        logger.info(f"Inserted record into {model_class.__tablename__} with ID={record_id}")
        return record_id
    
    except IntegrityError as e:
        session.rollback()
        logger.error(f"Integrity error in {model_class.__tablename__}: {e}")
        raise
    
    except Exception as e:
        session.rollback()
        logger.error(f"Insert failed for {model_class.__tablename__}: {e}")
        raise
    
    finally:
        session.close()


@log_activity(message="Bulk insert records")
def bulk_insert(
    engine: Engine, 
    model_class: Type, 
    records: List[Dict[str, Any]]
) -> Dict[str, int]:
    """
    Bulk insert records with duplicate handling.
    
    Args:
        engine: SQLAlchemy engine
        model_class: ORM model class
        records: List of record dictionaries
    
    Returns:
        Dictionary with 'inserted' and 'skipped' counts
    """
    if not records:
        return {"inserted": 0, "skipped": 0}
    
    SessionLocal = get_session(engine)
    inserted = 0
    skipped = 0
    
    for record_data in records:
        session = SessionLocal()
        try:
            new_record = model_class(**record_data)
            session.add(new_record)
            session.commit()
            inserted += 1
        
        except IntegrityError:
            session.rollback()
            skipped += 1
        
        except Exception as e:
            session.rollback()
            skipped += 1
            logger.warning(f"Skipped record due to error: {e}")
        
        finally:
            session.close()
    
    logger.info(f"Bulk insert: {inserted} inserted, {skipped} skipped")
    return {"inserted": inserted, "skipped": skipped}


# ==================== READ OPERATIONS ====================

@log_activity(message="Fetch all records")
def get_all_records(engine: Engine, model_class: Type, limit: Optional[int] = None) -> List[Any]:
    """
    Retrieve all records from a table.
    
    Args:
        engine: SQLAlchemy engine
        model_class: ORM model class
    
    Returns:
        List of all record objects
    """
    SessionLocal = get_session(engine)
    session = SessionLocal()
    
    try:
        query = session.query(model_class)
        
        # Apply limit if specified
        if limit is not None:
            query = query.limit(limit)
        
        records = query.all()
        table_name = getattr(model_class, "__tablename__", str(model_class))
        logger.info(f"Fetched {len(records)} records from {table_name}")
        return records
    
    finally:
        session.close()


@log_activity(message="Filter records")
def filter_by_col_values(
    engine: Engine, 
    model_class: Type, 
    filters: Dict[str, Any]
) -> List[Any]:
    """
    Filter records by column values.
    
    Args:
        engine: SQLAlchemy engine
        model_class: ORM model class
        filters: Dictionary of column_name -> value pairs
    
    Returns:
        List of matching records
    
    Raises:
        ValueError: If invalid column name in filters
    """
    if not filters:
        return get_all_records(engine, model_class)
    
    SessionLocal = get_session(engine)
    session = SessionLocal()
    
    try:
        query = session.query(model_class)
        
        # Validate and apply filters
        for column_name, value in filters.items():
            column = getattr(model_class, column_name, None)
            if column is None:
                raise ValueError(f"Invalid column name: '{column_name}'")
            query = query.filter(column == value)
        
        records = query.all()
        logger.info(f"Filtered {model_class.__tablename__} with {filters}: {len(records)} records")
        return records
    
    finally:
        session.close()


# ==================== UPDATE OPERATIONS ====================

@log_activity(message="Update records")
def update_record(
    engine: Engine, 
    model_class: Type, 
    filters: Dict[str, Any], 
    updates: Dict[str, Any]
) -> int:
    """
    Update records matching filter conditions.
    
    Args:
        engine: SQLAlchemy engine
        model_class: ORM model class
        filters: WHERE clause conditions (column -> value)
        updates: SET clause values (column -> new_value)
    
    Returns:
        Number of rows updated
    
    Raises:
        ValueError: If filters or updates are empty, or contain invalid columns
    """
    # Validation
    if not filters:
        raise ValueError("At least one filter condition is required")
    
    if not updates:
        raise ValueError("At least one update value is required")
    
    # Validate column names
    model_columns = {c.name for c in model_class.__table__.columns}
    
    invalid_filters = [k for k in filters.keys() if k not in model_columns]
    if invalid_filters:
        raise ValueError(f"Invalid filter columns: {invalid_filters}")
    
    invalid_updates = [k for k in updates.keys() if k not in model_columns]
    if invalid_updates:
        raise ValueError(f"Invalid update columns: {invalid_updates}")
    
    # Execute update
    SessionLocal = get_session(engine)
    session = SessionLocal()
    
    try:
        stmt = update(model_class)
        
        # Apply filters
        for col_name, value in filters.items():
            column = getattr(model_class, col_name)
            stmt = stmt.where(column == value)
        
        # Apply updates
        stmt = stmt.values(**updates)
        
        result = session.execute(stmt)
        session.commit()
        
        rows_updated = result.rowcount or 0
        logger.info(f"Updated {rows_updated} rows in {model_class.__name__}")
        return rows_updated
    
    except Exception as e:
        session.rollback()
        logger.error(f"Update failed for {model_class.__name__}: {e}")
        raise
    
    finally:
        session.close()


@log_activity(message="Bulk replace table contents")
def bulk_replace_table(engine: Engine, model_class: Type, df: pd.DataFrame) -> None:
    """
    Replace all rows in table with DataFrame contents.
    
    Args:
        engine: SQLAlchemy engine
        model_class: ORM model class
        df: DataFrame with new data
    """
    SessionLocal = get_session(engine)
    session = SessionLocal()
    
    try:
        # Delete existing rows
        deleted = session.query(model_class).delete()
        session.commit()
        logger.info(f"Deleted {deleted} existing rows from {model_class.__name__}")
        
        # Insert new rows if DataFrame not empty
        if not df.empty:
            records = df.to_dict(orient="records")
            session.bulk_insert_mappings(model_class, records)
            session.commit()
            logger.info(f"Inserted {len(records)} new rows into {model_class.__name__}")
    
    except Exception as e:
        session.rollback()
        logger.error(f"Bulk replace failed for {model_class.__name__}: {e}")
        raise
    
    finally:
        session.close()


# ==================== DELETE OPERATIONS ====================

@log_activity(message="Delete records")
def delete_record(
    engine: Engine, 
    model_class: Type, 
    filters: Dict[str, Any]
) -> int:
    """
    Delete records matching filter conditions.
    
    Args:
        engine: SQLAlchemy engine
        model_class: ORM model class
        filters: WHERE clause conditions (column -> value)
    
    Returns:
        Number of rows deleted
    
    Raises:
        ValueError: If filters are empty or contain invalid columns
    """
    # Validation
    if not filters:
        raise ValueError("At least one filter condition is required")
    
    # Validate column names
    model_columns = {c.name for c in model_class.__table__.columns}
    invalid_filters = [k for k in filters.keys() if k not in model_columns]
    if invalid_filters:
        raise ValueError(f"Invalid filter columns: {invalid_filters}")
    
    # Execute delete
    SessionLocal = get_session(engine)
    session = SessionLocal()
    
    try:
        query = session.query(model_class)
        
        # Apply filters
        for col_name, value in filters.items():
            column = getattr(model_class, col_name)
            query = query.filter(column == value)
        
        rows_deleted = query.delete(synchronize_session=False)
        session.commit()
        
        logger.info(f"Deleted {rows_deleted} rows from {model_class.__name__}")
        return rows_deleted
    
    except Exception as e:
        session.rollback()
        logger.error(f"Delete failed for {model_class.__name__}: {e}")
        raise
    
    finally:
        session.close()