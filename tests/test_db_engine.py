import pytest
import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, IntegrityError
from src.db_engine import *
from src.data_cleaner import clean_pipeline


@pytest.fixture
def engine():
    """Fixture to create and yield a test database engine."""
    engine = get_engine("sqlite:///:memory:")  # In-memory DB for isolation
    Base.metadata.create_all(engine)
    try:
        yield engine
        Base.metadata.drop_all(engine)
    finally:
        engine.dispose() 


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
    assert set(columns) == {"id", "iso_code", "value", "country"}, "Unexpected schema structure"


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


def test_get_all_records(engine):
    """Test get_all retrieves ALL records from table."""
    # Setup test data
    insert_record(engine, ExampleTable, {"iso_code": "USA", "value": 100.0})
    insert_record(engine, ExampleTable, {"iso_code": "GBR", "value": 200.0})
    
    records = get_all_records(engine, ExampleTable)
    
    assert len(records) == 2
    assert any(r.iso_code == "USA" for r in records)
    assert any(r.iso_code == "GBR" for r in records)


def test_get_all_empty_table(engine):
    """Test get_all returns empty list for empty table."""
    records = get_all_records(engine, ExampleTable)
    assert len(records) == 0


def test_flexible_filter_single_column(engine):
    """Test filter_by_columns with one column filter."""
    # Setup data
    insert_record(engine, ExampleTable, {"iso_code": "USA", "value": 100.0})
    insert_record(engine, ExampleTable, {"iso_code": "GBR", "value": 200.0})
    
    filters = {"iso_code": "USA"}
    records = filter_by_columns(engine, ExampleTable, filters)
    
    assert len(records) == 1
    assert records[0].iso_code == "USA"


def test_flexible_filter_multiple_columns(engine):
    """Test filter_by_columns with multiple columns including country."""
    # Setup data with repeated countries
    insert_record(engine, ExampleTable, {"iso_code": "USA1", "value": 100.0, "country": "United States"})
    insert_record(engine, ExampleTable, {"iso_code": "USA2", "value": 150.0, "country": "United States"})  # Same country!
    insert_record(engine, ExampleTable, {"iso_code": "GBR1", "value": 100.0, "country": "United Kingdom"})
    insert_record(engine, ExampleTable, {"iso_code": "USA", "value": 100.0, "country": "United States"})  

    # Filter: USA1 with specific value + country
    filters = {"country": "United States", "value": 100.0}
    records = filter_by_columns(engine, ExampleTable, filters)
    
    assert len(records) == 2
    assert records[0].country == "United States"
    assert records[0].value == 100.0


def test_flexible_filter_invalid_column(engine):
    """Test error handling for non-existent columns."""
    filters = {"invalid_column": "test"}
    
    with pytest.raises(ValueError, match="Invalid column"):
        filter_by_columns(engine, ExampleTable, filters)


def test_flexible_filter_no_matches(engine):
    """Test returns empty list when no records match."""
    filters = {"iso_code": "NONEXISTENT"}
    records = filter_by_columns(engine, ExampleTable, filters)
    assert len(records) == 0


def test_flexible_filter_empty_filters(engine):
    """Test empty filters returns all records."""
    insert_record(engine, ExampleTable, {"iso_code": "USA", "value": 100.0})
    insert_record(engine, ExampleTable, {"iso_code": "GBR", "value": 200.0})
    
    filters = {}
    records = filter_by_columns(engine, ExampleTable, filters)
    assert len(records) == 2


def df_from_records(records):
    return pd.DataFrame(
        [{"iso_code": r.iso_code, "country": r.country, "value": r.value} for r in records]
    ).sort_values(["iso_code", "country"]).reset_index(drop=True)


# ---------- update_record tests ----------

def test_update_single_record_value(engine):
    """Update a single record's value field and verify other fields remain unchanged."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    rows_updated = update_record(
        engine,
        ExampleTable,
        filters={"iso_code": "AFG"},
        updates={"value": 150.0},
    )

    assert rows_updated == 1

    records = get_all_records(engine, ExampleTable)
    assert len(records) == 1
    rec = records[0]
    assert rec.iso_code == "AFG"
    assert rec.country == "Afghanistan"
    assert rec.value == 150.0


def test_update_record_no_match_does_not_change_table(engine):
    """Ensure no rows are updated and table contents stay the same when the filter matches nothing."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    rows_updated = update_record(
        engine,
        ExampleTable,
        filters={"iso_code": "XXX"},
        updates={"value": 999.0},
    )

    assert rows_updated == 0

    records = get_all_records(engine, ExampleTable)
    assert len(records) == 1
    assert records[0].value == 100.0


def test_update_record_raises_when_filters_empty(engine):
    """Raise ValueError when attempting an update without any filter conditions."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    with pytest.raises(ValueError):
        update_record(
            engine,
            ExampleTable,
            filters={},
            updates={"value": 200.0},
        )


def test_update_record_raises_when_updates_empty(engine):
    """Raise ValueError when attempting an update with no columns to update."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    with pytest.raises(ValueError):
        update_record(
            engine,
            ExampleTable,
            filters={"iso_code": "AFG"},
            updates={},
        )


def test_update_record_raises_on_invalid_filter_column(engine):
    """Raise ValueError if filters reference columns that do not exist on the model."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    with pytest.raises(ValueError) as excinfo:
        update_record(
            engine,
            ExampleTable,
            filters={"not_a_column": "x"},
            updates={"value": 200.0},
        )
    assert "Invalid filter columns" in str(excinfo.value)


def test_update_record_raises_on_invalid_update_column(engine):
    """Raise ValueError if updates reference columns that do not exist on the model."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    with pytest.raises(ValueError) as excinfo:
        update_record(
            engine,
            ExampleTable,
            filters={"iso_code": "AFG"},
            updates={"not_a_column": 200.0},
        )
    assert "Invalid update columns" in str(excinfo.value)


def test_update_record_updates_multiple_rows(engine):
    """Update multiple matching rows at once and verify all affected rows get the new value."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG1", "country": "Afghanistan", "value": 100.0})
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 150.0})

    rows_updated = update_record(
        engine,
        ExampleTable,
        filters={"country": "Afghanistan"},
        updates={"value": 200.0},
    )

    assert rows_updated == 2

    records = get_all_records(engine, ExampleTable)
    assert len(records) == 2
    assert all(r.value == 200.0 for r in records)


def test_update_record_exception_triggers_rollback(engine):
    """
    Force an internal SQL error in update_record to exercise the except block
    and ensure the table remains unchanged.
    """
    # Arrange: insert a valid row
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    # Assert: use an un-bindable value for 'value' to cause an exception
    with pytest.raises(Exception):
        update_record(
            engine,
            ExampleTable,
            filters={"iso_code": "AFG"},
            updates={"value": {"not": "serializable"}},  # bad type for DB
        )

    # Verify row is unchanged after rollback
    records = get_all_records(engine, ExampleTable)
    assert len(records) == 1
    rec = records[0]
    assert rec.iso_code == "AFG"
    assert rec.country == "Afghanistan"
    assert rec.value == 100.0


# ---------- bulk_replace_table tests ----------

def test_bulk_replace_table_on_empty_table(engine):
    """Insert a full dataset into an empty table using bulk_replace_table."""
    df = pd.DataFrame([
        {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0},
        {"iso_code": "GBR", "country": "United Kingdom", "value": 200.0},
    ])

    bulk_update_table(engine, ExampleTable, df)

    records = get_all_records(engine, ExampleTable)
    assert len(records) == 2

    data = {(r.iso_code, r.country): r.value for r in records}
    assert data[("AFG", "Afghanistan")] == 100.0
    assert data[("GBR", "United Kingdom")] == 200.0


def test_bulk_replace_table_deletes_old_rows(engine):
    """Replace existing rows so that old records are removed and only new ones remain."""
    insert_record(engine, ExampleTable, {"iso_code": "OLD", "country": "Oldland", "value": 1.0})

    df = pd.DataFrame([
        {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0},
    ])

    bulk_update_table(engine, ExampleTable, df)

    records = get_all_records(engine, ExampleTable)
    assert len(records) == 1
    assert records[0].iso_code == "AFG"


def test_bulk_replace_table_with_empty_dataframe_clears_table(engine):
    """Clear all rows from the table when given an empty DataFrame."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    df_empty = pd.DataFrame(columns=["iso_code", "country", "value"])

    bulk_update_table(engine, ExampleTable, df_empty)

    records = get_all_records(engine, ExampleTable)
    assert len(records) == 0


def test_create_record_raises_on_empty_record_data(engine):
    """
    Ensure an empty record_data dict raises a clear ValueError instead of doing nothing.
    """
    with pytest.raises(ValueError) as excinfo:
        insert_record(engine, ExampleTable, {})

    assert "record_data cannot be empty" in str(excinfo.value)


def test_bulk_replace_table_raises_on_missing_required_columns(engine):
    """Raise an exception when DataFrame is missing required model columns."""
    df = pd.DataFrame([
        {"country": "Afghanistan", "value": 100.0},  # missing 'country'
    ])

    with pytest.raises(Exception):
        bulk_update_table(engine, ExampleTable, df)


def test_bulk_replace_table_idempotent_for_same_dataframe(engine):
    """Running bulk_replace_table twice with the same DataFrame yields the same final table state."""
    df = pd.DataFrame([
        {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0},
    ])

    bulk_update_table(engine, ExampleTable, df)
    bulk_update_table(engine, ExampleTable, df)

    records = get_all_records(engine, ExampleTable)
    assert len(records) == 1
    assert records[0].iso_code == "AFG"
    assert records[0].value == 100.0
