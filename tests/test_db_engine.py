import pytest
import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, IntegrityError
from src.db_engine import *


@pytest.fixture
def engine():
    """Fixture to create and yield a test database engine."""
    engine = get_engine("sqlite:///:memory:")  # In-memory DB for isolation
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def session(engine):
    """Fixture to provide a fresh session for each test."""
    session = get_session(engine)()
    yield session
    session.rollback()
    session.close()


# EXISTING TESTS (keep these unchanged)
def test_engine_connection(engine):
    """Test that the database engine connects successfully."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
    except OperationalError:
        pytest.fail("Database connection failed.")


def test_table_creation(engine):
    """Test that tables defined in Base metadata are created."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    assert "example_table" in table_names, "example_table should be created"


def test_table_structure(engine):
    """Test that the created table has expected columns."""
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("example_table")]
    assert set(columns) == {"id", "iso_code", "value"}, "Unexpected schema structure"


def test_create_single_record(session):
    """Test insert_record function creates a single record successfully."""
    data = {"iso_code": "Test Patient", "value": 98.6}
    record_id = insert_record(session.bind, ExampleTable, data)

    # Assert: Verify using helper function
    saved_record = session.query(ExampleTable).filter_by(iso_code="Test Patient").first()
    assert saved_record is not None
    assert saved_record.iso_code == "Test Patient"
    assert saved_record.value == 98.6
    assert saved_record.id == record_id


def test_create_single_record_id_autoincrement(session):
    """Test that the primary key auto-increments correctly."""
    # Arrange & Act: Insert first record
    data1 = {"iso_code": "Patient 1", "value": 98.6}
    record_id1 = insert_record(session.bind, ExampleTable, data1)
    
    # Act: Insert second record
    data2 = {"iso_code": "Patient 2", "value": 98.0}
    record_id2 = insert_record(session.bind, ExampleTable, data2)
    
    # Assert: Verify ID assignment and uniqueness
    saved1 = session.query(ExampleTable).filter_by(iso_code="Patient 1").first()
    saved2 = session.query(ExampleTable).filter_by(iso_code="Patient 2").first()
    assert saved1.id == 1
    assert saved2.id == 2
    assert saved1.id != saved2.id


def test_insert_record_session_failure_raises_exception(engine, monkeypatch):
    """Test that generic session failures are properly handled and re-raised."""
    import src.db_engine as database

    class FailingSession:
        def add(self, obj):
            raise RuntimeError("Simulated database connection failure")
        def commit(self): 
            pass
        def rollback(self): 
            pass
        def close(self): 
            pass

    def fake_get_session(engine):
        return lambda: FailingSession()

    monkeypatch.setattr(database, "get_session", fake_get_session)

    with pytest.raises(RuntimeError, match="Simulated database connection failure"):
        data = {"iso_code": "Test", "value": 90.0}
        database.insert_record(engine, ExampleTable, data)



def test_insert_record_duplicate_name_raises_integrity_error(engine):
    """Test duplicate name violation (assumes unique constraint on name)."""
    # First insert succeeds
    data = {"iso_code": "DuplicateTest", "value": 1.0}
    insert_record(engine, ExampleTable, data)
    
    # Second insert should fail (if you add unique=True to iso_code column)
    with pytest.raises(IntegrityError):
        data = {"iso_code": "DuplicateTest", "value": 2.0}
        insert_record(engine, ExampleTable, data)


def test_create_dynamic_table_basic(engine):
    """Basic: creates table with columns."""
    df = pd.DataFrame({'iso_code': ['USA'], 'total_cases': [100.0]})
    create_dynamic_table(engine, "test", df)
    inspector = inspect(engine)
    assert "test" in inspector.get_table_names()
    assert len(inspector.get_columns("test")) == 2


def test_create_dynamic_table_all_nulls(engine):
    """Edge case: all null values."""
    df = pd.DataFrame({'iso_code': [None], 'total_cases': [None]})
    create_dynamic_table(engine, "null_test", df)
    inspector = inspect(engine)
    assert "null_test" in inspector.get_table_names()
    assert len(inspector.get_columns("null_test")) == 2


def test_create_dynamic_table_empty(engine):
    """Edge case: empty DataFrame."""
    df = pd.DataFrame(columns=['iso_code'])
    create_dynamic_table(engine, "empty", df)
    inspector = inspect(engine)
    assert "empty" in inspector.get_table_names()


def test_bulk_insert_multiple_records(engine):
    """Test bulk_insert inserts multiple records successfully."""
    records = [
        {"iso_code": "USA1", "value": 100.0},
        {"iso_code": "USA2", "value": 200.0},
        {"iso_code": "USA3", "value": 300.0}
    ]
    
    result = bulk_insert(engine, ExampleTable, records)
    
    # Verify return value
    assert isinstance(result, dict)
    assert result["inserted"] == 3
    assert result["skipped"] == 0
    
    # Verify records in DB
    inspector = inspect(engine)
    count = engine.connect().execute(text("SELECT COUNT(*) FROM example_table")).scalar()
    assert count == 3


def test_bulk_insert_empty_list(engine):
    """Test bulk_insert handles empty list gracefully."""
    result = bulk_insert(engine, ExampleTable, [])
    assert result["inserted"] == 0
    assert result["skipped"] == 0


def test_bulk_insert_with_duplicates(engine):
    """Test bulk_insert skips duplicates (unique constraint)."""
    # First insert succeeds
    insert_record(engine, ExampleTable, {"iso_code": "DUP", "value": 100.0})
    
    records = [
        {"iso_code": "NEW1", "value": 200.0},
        {"iso_code": "DUP", "value": 999.0},  # Duplicate
        {"iso_code": "NEW2", "value": 300.0}
    ]
    
    result = bulk_insert(engine, ExampleTable, records)
    assert result["inserted"] == 2  # NEW1, NEW2
    assert result["skipped"] == 1   # DUP


def test_bulk_insert_mixed_data_types(engine):
    """Test bulk_insert handles partial records (nulls)."""
    records = [
        {"iso_code": "USA", "value": 100.0},      # Full
        {"iso_code": "GBR"},                       # Missing value (null)
        {"iso_code": "FRA", "value": None}         # Explicit null
    ]
    
    result = bulk_insert(engine, ExampleTable, records)
    assert result["inserted"] == 3
    
    # Verify null handling
    count_nulls = engine.connect().execute(text("SELECT COUNT(*) FROM example_table WHERE value IS NULL")).scalar()
    assert count_nulls == 2


def test_bulk_insert_invalid_record(engine):
    """Test bulk_insert handles invalid feild name (triggers except Exception)."""
    records = [
        {"iso_code": "VALID1", "value": 100.0},  # Succeeds
        {"iso_code": "INVALID"},                 # Missing required fields 
        {"iso_code": "VALID2", "vaue": 200.0}   # Typo in field name -> Exception
    ]
    
    result = bulk_insert(engine, ExampleTable, records)
    assert result["inserted"] == 2  # VALID1, VALID2
    assert result["skipped"] == 1   # INVALID triggers except Exception

