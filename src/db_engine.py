from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError
from typing import Optional
import logging

# Initialize the ORM base class
Base = declarative_base()


def get_engine(db_url="sqlite:///health_data.db"):
    """
    Create and return a SQLAlchemy database engine.
    Default is a local SQLite database called health_data.db.
    """
    engine = create_engine(db_url, echo=False, future=True)
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



def get_session(engine):
    """
    Create a new SQLAlchemy session bound to the given engine.
    """
    Session = sessionmaker(bind=engine)
    return Session


# NEW IMPLEMENTATION FOR STEP 5: CRUD - Create
def insert_record(engine, iso_code: str, value: Optional[float] = None) -> int:
    """
    Insert a single record into the example_table and return the generated ID.
    
    Args:
        engine: SQLAlchemy engine instance
        name: Name field (required, non-nullable)
        value: Value field (optional)
    
    Returns:
        int: The auto-generated primary key ID of the inserted record
    
    Raises:
        IntegrityError: If unique constraints are violated
    """
    session = get_session(engine)()
    try:
    # Create new record instance
        new_record = ExampleTable(iso_code=iso_code, value=value)
            
        # Add to session and commit
        session.add(new_record)
        session.commit()
            
        # Return the generated ID
        record_id = new_record.id
        session.close()
            
        logging.info(f"Successfully inserted record with ID: {record_id}")
        return record_id
        
    except IntegrityError as e:
        session.rollback()
        logging.error(f"Integrity error during insert: {e}")
        raise
    except Exception as e:
        session.rollback()
        logging.error(f"Error during insert: {e}")
        raise
    finally:
        session.close()


def get_record_by_id(engine, record_id: int) -> Optional[ExampleTable]:
    """
    Retrieve a single record by its primary key ID.
    Helper function for testing/verification.
    """
    session = get_session(engine)()
    
    try:
        record = session.query(ExampleTable).filter(ExampleTable.id == record_id).first()
        session.close()
        return record
    except Exception as e:
        session.rollback()
        session.close()
        logging.error(f"Error retrieving record {record_id}: {e}")
        raise