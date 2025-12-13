from sqlalchemy import create_engine, update, insert, Table, Engine, MetaData, Column, Integer, String, Float, Date, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, DeclarativeMeta
from sqlalchemy.exc import IntegrityError
from typing import Optional
import pandas as pd
from typing import List, Dict, Any, Type, Union
import logging
import warnings
from src.logging_conf import log_activity

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore")

# Initialize the ORM base class
Base = declarative_base()


@log_activity()
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


# Similar to the actual db
class SampleTable(Base):
    """
    Example table schema matching CORE_COLS for COVID data testing.
    """
    __tablename__ = "sample_table"

    id = Column(Integer, primary_key=True, autoincrement=True)
    iso_code = Column(String(10), nullable=False)
    location = Column(String(100), nullable=True)
    continent = Column(String(50), nullable=True)
    date = Column(Date, nullable=True)
    total_cases = Column(Float, nullable=True)
    new_cases = Column(Float, nullable=True)
    total_deaths = Column(Float, nullable=True)
    new_deaths = Column(Float, nullable=True)
    gdp_per_capita = Column(Float, nullable=True)
    population = Column(Float, nullable=True)


def ensure_orm_model(target: Any, base: Any = Base) -> Type[DeclarativeMeta]:
    """
    Given either an ORM model or a Table, return an ORM model.

    - If target is already an ORM model (has __table__ and __tablename__),
      return it unchanged.
    - If target is a Table, create a dynamic ORM class bound to that table.
    """
    if hasattr(target, "__table__") and hasattr(target, "__tablename__"):
        # Already an ORM model
        return target

    if isinstance(target, Table):
        DynamicModel = type(
            f"{target.name.capitalize()}Model",
            (base,),
            {
                "__tablename__": target.name,
                "__table__": target,
            },
        )
        return DynamicModel

    raise TypeError(f"Unsupported target type for ensure_orm_model: {type(target)!r}")


def infer_sqlalchemy_type(series):
    if pd.api.types.is_datetime64_any_dtype(series) or "date" in series.name.lower():
        return Date
    if pd.api.types.is_numeric_dtype(series):
        return Float
    if pd.api.types.is_bool_dtype(series):
        return Boolean
    return String(255)


# CREATE
# Creating a dynamic table schema using SQLAlchemy ORM
@log_activity()
def create_dynamic_table(engine: Engine, table_name: str, df: pd.DataFrame) -> Table:
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
    
    # Always create 'id' as primary key first
    columns = [Column('id', Integer, primary_key=True, autoincrement=True)]
    for col in df.columns:
        col_type = infer_sqlalchemy_type(df[col])
        # name must be first arg
        columns.append(Column(col, col_type, nullable=True))

    table = Table(table_name, metadata, *columns, extend_existing=True)
    metadata.create_all(engine)
    logger.info(f"Created dynamic table '{table_name}' with {len(columns)} columns")
    return table


@log_activity(message="Create new SQLAlchemy session.")
def get_session(engine: Engine):
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


@log_activity(message="Insert a single record.")
def insert_record(engine: Engine, model_class, record_data: dict) -> int:
    """
    Insert a single record using a SQLAlchemy ORM model class.

    Args:
        engine: SQLAlchemy engine instance
        model_class: ORM class
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


@log_activity(message="Bulk insert.")
def bulk_insert(engine: Engine, model_class: Union[Type, Table], records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Bulk insert records, handling duplicates by skipping them when using ORM.
    
    CRITICAL FIX: Reverting ORM path (Path 2) to the individual loop to satisfy 
    the TDD requirement for duplicate skipping (partial success).
    """
    if not records:
        return {"inserted": 0, "skipped": 0}
    
    SessionLocal = get_session(engine)
    
    # Path 1: SQLAlchemy Core Table object
    if isinstance(model_class, Table):
        inserted = 0
        try:
            with engine.begin() as conn:
                # Core Insert is typically faster but doesn't handle duplicates gracefully without specific DB syntax
                result = conn.execute(insert(model_class), records)
                inserted = result.rowcount or 0
                skipped = 0 
            logger.info(f"Bulk insert (Core Table): {inserted} inserted, {skipped} skipped (approx)")
            return {"inserted": inserted, "skipped": skipped}
        except IntegrityError as e:
            # Core failures roll back the whole batch
            logger.error(f"Bulk insert (Core) failed due to IntegrityError: {e}")
            return {"inserted": 0, "skipped": len(records)} 
        except Exception as e:
            logger.error(f"Bulk insert (Core) failed: {e}")
            raise
            
    # Path 2: SQLAlchemy ORM Model object (Individual loop for robust duplicate skipping)
    else:
        inserted = 0
        skipped = 0
        
        for record_data in records:
            # Use a new session for each insert to commit/rollback individually
            session = SessionLocal() 
            try:
                # Use model_class(**record_data) for ORM insertion
                new_record = model_class(**record_data)
                session.add(new_record)
                session.commit()
                inserted += 1
            except IntegrityError:
                skipped += 1
                session.rollback()
            except Exception as e:
                # Handles missing required fields (like 'value' after the fix) or typo errors
                skipped += 1
                session.rollback()
                logger.warning(f"Skipped record due to error or missing required field: {e}")
            finally:
                session.close()
        
        logger.info(f"Bulk insert (ORM Loop): {inserted} inserted, {skipped} skipped")
        return {"inserted": inserted, "skipped": skipped}

# READ
@log_activity(message="Get all the records.")
def get_all_records(engine: Engine, model_class) -> List[Any]:
    """
    Retrieve ALL records from the given model class.
    
    Args:
        engine: SQLAlchemy engine
        model_class: ORM model class
    
    Returns:
        List of all records
    """
    SessionLocal = get_session(engine)
    session = SessionLocal()

    try:
        records = session.query(model_class).all()
        table_name = getattr(model_class, "__tablename__", getattr(model_class, "name", str(model_class)))
        logger.info(f"Fetched all records from {table_name}, count={len(records)}")
        return records
    finally:
        session.close()


@log_activity(message="Filter db with values.")
def filter_by_col_values(engine: Engine, model_class, filters: Dict[str, Any]) -> List[Any]:
    """
    Filter records using .filter() on multiple columns.
    
    Args:
        engine: DB engine
        model_class: other ORM class
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


# UPDATE
@log_activity(message="Update a single record.")
def update_record(engine: Engine, model_class: Type, filters: Dict[str, Any], updates: Dict[str, Any]) -> int:
    """
    Update records in the given model_class table.

    Args:
        engine: SQLAlchemy Engine (e.g., from get_engine or test fixture).
        model_class: ORM mapped class.
        filters: column_name → value dict used in WHERE clause.
        updates: column_name → new_value dict used in SET clause.

    Returns:
        Number of rows updated.

    Raises:
        ValueError if any filter/update column does not exist on the model.
        Any SQLAlchemy error will propagate after being logged.
    """

    if not filters:
        logger.error("update_record called without any filter conditions; refusing full-table update")
        raise ValueError("At least one filter condition is required for update_record.")

    if not updates:
        logger.error("update_record called without any update values; nothing to update")
        raise ValueError("At least one update value is required for update_record.")

    # Validate that all filter/update keys exist as table columns
    model_columns = {c.name for c in model_class.__table__.columns}

    invalid_filters = [k for k in filters.keys() if k not in model_columns]
    if invalid_filters:
        logger.error(f"update_record received invalid filter columns: {invalid_filters}")
        raise ValueError(f"Invalid filter columns: {invalid_filters}")


    invalid_updates = [k for k in updates.keys() if k not in model_columns]
    if invalid_updates:
        logger.error(f"update_record received invalid update columns: {invalid_updates}")
        raise ValueError(f"Invalid update columns: {invalid_updates}")
   
    SessionLocal = get_session(engine)
    session = SessionLocal()

    try:
        # Build UPDATE statement: UPDATE table SET ... WHERE ...
        stmt = update(model_class)
        for col_name, value in filters.items():
            column = getattr(model_class, col_name)
            stmt = stmt.where(column == value)

        stmt = stmt.values(**updates)

        result = session.execute(stmt)
        session.commit()

        rows_updated = result.rowcount or 0
        logger.info(
            f"update_record: updated {rows_updated} rows in {model_class.__name__} filters={filters}, updates={updates}"
        )
        return rows_updated
    
    except Exception as e:
        session.rollback()
        logger.error(
            f"update_record failed for {model_class.__name__} filters={filters}, updates={updates}: {e}"
        )
        raise

    finally:
        session.close()


@log_activity(message="Bulk Update.")
def bulk_update_table(engine: Engine, model_class: Type, df: pd.DataFrame) -> Boolean:
    """
    Replace all rows in the given table with rows from df.

    Assumes df has columns matching the ORM model's column names (at least
    for all non-nullable, non-autogenerated columns).
    """

    SessionLocal = get_session(engine)
    session = SessionLocal()

    try:
        # Clear existing rows
        deleted = session.query(model_class).delete()
        session.commit()
        logger.info(f"bulk_replace_table: deleted {deleted} existing rows from {model_class.__name__}")

        # If df is empty, we are done (table remains empty)
        if df.empty:
            return    
        
        # Convert DataFrame rows to list[dict] for bulk_insert_mappings
        records = df.to_dict(orient="records")

        session.bulk_insert_mappings(model_class, records)
        session.commit()

        logger.info(f"bulk_replace_table: inserted {len(records)} rows into {model_class.__name__}")

    except Exception as e:
        session.rollback()
        logger.error(f"bulk_replace_table failed for {model_class.__name__}: {e}")
        raise

    finally:
        session.close()


# DELETE
@log_activity(message="Delete record(s).")
def delete_record(engine: Engine, model_class: Type, filters: Dict[str, Any]) -> int:
    """
    Delete records in the given model_class table based on filters.

    Args:
        engine: SQLAlchemy Engine (e.g., from get_engine)
        model_class: ORM mapped class
        filters: column_name -> value dict used in WHERE clause

    Returns:
        Number of rows deleted.

    Raises:
        ValueError if filters are missing or include invalid column names.
    """
    if not filters:
        logger.error("delete_record called without any filter conditions; refusing full-table delete")
        raise ValueError("At least one filter condition is required for delete_record.")

    # Validate filter keys exist on the table
    model_columns = {c.name for c in model_class.__table__.columns}
    invalid_filters = [k for k in filters.keys() if k not in model_columns]
    if invalid_filters:
        logger.error(f"delete_record received invalid filter columns: {invalid_filters}")
        raise ValueError(f"Invalid filter columns: {invalid_filters}")

    SessionLocal = get_session(engine)
    session = SessionLocal()
    try:
        query = session.query(model_class)
        for col_name, value in filters.items():
            column = getattr(model_class, col_name)
            query = query.filter(column == value)
        rows_deleted = query.delete(synchronize_session=False)
        session.commit()
        logger.info(
            f"delete_record: deleted {rows_deleted} rows from {model_class.__name__} with filters={filters}"
        )
        return rows_deleted
    except Exception as e:
        session.rollback()
        logger.error(
            f"delete_record failed for {model_class.__name__} with filters={filters}: {e}"
        )
        raise
    finally:
        session.close()