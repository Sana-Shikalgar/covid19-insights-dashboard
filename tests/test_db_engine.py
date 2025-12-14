"""
Database engine tests - Updated for static model architecture.

All dynamic table creation tests have been REMOVED.
Tests now use only statically defined models from models.py
"""

import pytest
import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, IntegrityError

from src.db_engine import (
    get_engine, create_all_tables, table_exists, get_table_row_count,
    get_session, insert_record, bulk_insert, get_all_records,
    filter_by_col_values, update_record, bulk_replace_table, delete_record
)
from src.models import Base, ExampleTable, SampleTable, CovidDataRaw, CovidDataClean, CovidDataWorking


# ==================== FIXTURES ====================

@pytest.fixture
def engine():
    """Fixture to create and yield a test database engine."""
    engine = get_engine("sqlite:///:memory:")
    create_all_tables(engine)  # Create all tables from models.py
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session(engine):
    """Fixture to provide a fresh session for each test."""
    session = get_session(engine)()
    yield session
    session.rollback()
    session.close()


# ==================== TABLE MANAGEMENT TESTS ====================

def test_engine_connection(engine):
    """Test that the database engine connects successfully."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
    except OperationalError:
        pytest.fail("Database connection failed.")


def test_create_all_tables(engine):
    """Test that create_all_tables creates all models from Base."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    # Check all expected tables exist
    assert "example_table" in table_names
    assert "sample_table" in table_names
    assert "covid_data_raw" in table_names
    assert "covid_data_clean" in table_names
    assert "covid_data_working" in table_names


def test_table_exists(engine):
    """Test table_exists function."""
    assert table_exists(engine, "example_table") is True
    assert table_exists(engine, "nonexistent_table") is False


def test_get_table_row_count_empty(engine):
    """Test row count on empty table."""
    count = get_table_row_count(engine, ExampleTable)
    assert count == 0


def test_get_table_row_count_with_data(engine):
    """Test row count after inserting data."""
    insert_record(engine, ExampleTable, {"iso_code": "TST", "value": 100.0})
    insert_record(engine, ExampleTable, {"iso_code": "TST2", "value": 200.0})
    
    count = get_table_row_count(engine, ExampleTable)
    assert count == 2


def test_table_structure(engine):
    """Test that the created table has expected columns."""
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("example_table")]
    assert set(columns) == {"id", "iso_code", "value", "country"}


# ==================== CREATE OPERATIONS TESTS ====================

def test_insert_single_record(session):
    """Test insert_record function creates a single record successfully."""
    data = {"iso_code": "TestPatient", "value": 98.6}
    record_id = insert_record(session.bind, ExampleTable, data)

    # Verify using query
    saved_record = session.query(ExampleTable).filter_by(iso_code="TestPatient").first()
    assert saved_record is not None
    assert saved_record.iso_code == "TestPatient"
    assert saved_record.value == 98.6
    assert saved_record.id == record_id


def test_insert_record_id_autoincrement(session):
    """Test that the primary key auto-increments correctly."""
    data1 = {"iso_code": "Patient1", "value": 98.6}
    record_id1 = insert_record(session.bind, ExampleTable, data1)
    
    data2 = {"iso_code": "Patient2", "value": 98.0}
    record_id2 = insert_record(session.bind, ExampleTable, data2)
    
    saved1 = session.query(ExampleTable).filter_by(iso_code="Patient1").first()
    saved2 = session.query(ExampleTable).filter_by(iso_code="Patient2").first()
    
    assert saved1.id == 1
    assert saved2.id == 2
    assert saved1.id != saved2.id


def test_insert_record_empty_data_raises(engine):
    """Test that empty record_data raises ValueError."""
    with pytest.raises(ValueError, match="record_data cannot be empty"):
        insert_record(engine, ExampleTable, {})


def test_insert_record_duplicate_raises_integrity_error(engine):
    """Test duplicate iso_code violation (unique constraint)."""
    data = {"iso_code": "DuplicateTest", "value": 1.0}
    insert_record(engine, ExampleTable, data)
    
    with pytest.raises(IntegrityError):
        insert_record(engine, ExampleTable, data)


def test_insert_record_session_failure_raises_exception(engine, monkeypatch):
    """Test that generic session failures are properly handled."""
    import src.db_engine as database

    class FailingSession:
        def add(self, obj):
            raise RuntimeError("Simulated database connection failure")
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass

    def fake_get_session(engine):
        return lambda: FailingSession()

    monkeypatch.setattr(database, "get_session", fake_get_session)

    with pytest.raises(RuntimeError, match="Simulated database connection failure"):
        database.insert_record(engine, ExampleTable, {"iso_code": "Test", "value": 90.0})


def test_bulk_insert_multiple_records(engine):
    """Test bulk_insert inserts multiple records successfully."""
    records = [
        {"iso_code": "USA1", "value": 100.0},
        {"iso_code": "USA2", "value": 200.0},
        {"iso_code": "USA3", "value": 300.0}
    ]
    
    result = bulk_insert(engine, ExampleTable, records)
    
    assert isinstance(result, dict)
    assert result["inserted"] == 3
    assert result["skipped"] == 0
    
    # Verify in DB
    count = get_table_row_count(engine, ExampleTable)
    assert count == 3


def test_bulk_insert_empty_list(engine):
    """Test bulk_insert handles empty list gracefully."""
    result = bulk_insert(engine, ExampleTable, [])
    assert result["inserted"] == 0
    assert result["skipped"] == 0


def test_bulk_insert_with_duplicates(engine):
    """Test bulk_insert skips duplicates (unique constraint)."""
    insert_record(engine, ExampleTable, {"iso_code": "DUP", "value": 100.0})
    
    records = [
        {"iso_code": "NEW1", "value": 200.0},
        {"iso_code": "DUP", "value": 999.0},  # Duplicate
        {"iso_code": "NEW2", "value": 300.0}
    ]
    
    result = bulk_insert(engine, ExampleTable, records)
    assert result["inserted"] == 2
    assert result["skipped"] == 1


def test_bulk_insert_mixed_data_types(engine):
    """Test bulk_insert handles partial records (nulls)."""
    records = [
        {"iso_code": "USA", "value": 100.0},
        {"iso_code": "GBR"},  # Missing value (null)
        {"iso_code": "FRA", "value": None}
    ]
    
    result = bulk_insert(engine, ExampleTable, records)
    assert result["inserted"] == 3
    
    # Verify nulls
    count_nulls = engine.connect().execute(
        text("SELECT COUNT(*) FROM example_table WHERE value IS NULL")
    ).scalar()
    assert count_nulls == 2


def test_bulk_insert_invalid_record(engine):
    """Test bulk_insert handles invalid field name."""
    records = [
        {"iso_code": "VALID1", "value": 100.0},
        {"iso_code": "INVALID"},  # Missing required fields if any
        {"iso_code": "VALID2", "vaue": 200.0}  # Typo - triggers exception
    ]
    
    result = bulk_insert(engine, ExampleTable, records)
    assert result["inserted"] == 2
    assert result["skipped"] == 1


# ==================== READ OPERATIONS TESTS ====================

def test_get_all_records(engine):
    """Test get_all retrieves ALL records from table."""
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


def test_filter_by_col_values_single_column(engine):
    """Test filter with one column filter."""
    insert_record(engine, ExampleTable, {"iso_code": "USA", "value": 100.0})
    insert_record(engine, ExampleTable, {"iso_code": "GBR", "value": 200.0})
    
    filters = {"iso_code": "USA"}
    records = filter_by_col_values(engine, ExampleTable, filters)
    
    assert len(records) == 1
    assert records[0].iso_code == "USA"


def test_filter_by_col_values_multiple_columns(engine):
    """Test filter with multiple columns."""
    insert_record(engine, ExampleTable, {"iso_code": "USA1", "value": 100.0, "country": "United States"})
    insert_record(engine, ExampleTable, {"iso_code": "USA2", "value": 150.0, "country": "United States"})
    insert_record(engine, ExampleTable, {"iso_code": "GBR1", "value": 100.0, "country": "United Kingdom"})
    
    filters = {"country": "United States", "value": 100.0}
    records = filter_by_col_values(engine, ExampleTable, filters)
    
    assert len(records) == 1
    assert records[0].iso_code == "USA1"


def test_filter_by_col_values_invalid_column(engine):
    """Test error handling for non-existent columns."""
    filters = {"invalid_column": "test"}
    
    with pytest.raises(ValueError, match="Invalid column"):
        filter_by_col_values(engine, ExampleTable, filters)


def test_filter_by_col_values_no_matches(engine):
    """Test returns empty list when no records match."""
    filters = {"iso_code": "NONEXISTENT"}
    records = filter_by_col_values(engine, ExampleTable, filters)
    assert len(records) == 0


def test_filter_by_col_values_empty_filters(engine):
    """Test empty filters returns all records."""
    insert_record(engine, ExampleTable, {"iso_code": "USA", "value": 100.0})
    insert_record(engine, ExampleTable, {"iso_code": "GBR", "value": 200.0})
    
    filters = {}
    records = filter_by_col_values(engine, ExampleTable, filters)
    assert len(records) == 2


# ==================== UPDATE OPERATIONS TESTS ====================

def test_update_single_record_value(engine):
    """Update a single record's value field."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    rows_updated = update_record(
        engine, ExampleTable,
        filters={"iso_code": "AFG"},
        updates={"value": 150.0}
    )

    assert rows_updated == 1

    records = get_all_records(engine, ExampleTable)
    rec = records[0]
    assert rec.iso_code == "AFG"
    assert rec.value == 150.0


def test_update_record_no_match(engine):
    """Ensure no rows updated when filter matches nothing."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "value": 100.0})

    rows_updated = update_record(
        engine, ExampleTable,
        filters={"iso_code": "XXX"},
        updates={"value": 999.0}
    )

    assert rows_updated == 0


def test_update_record_raises_when_filters_empty(engine):
    """Raise ValueError when no filter conditions."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "value": 100.0})

    with pytest.raises(ValueError, match="At least one filter condition"):
        update_record(engine, ExampleTable, filters={}, updates={"value": 200.0})


def test_update_record_raises_when_updates_empty(engine):
    """Raise ValueError when no update values."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "value": 100.0})

    with pytest.raises(ValueError, match="At least one update value"):
        update_record(engine, ExampleTable, filters={"iso_code": "AFG"}, updates={})


def test_update_record_raises_on_invalid_filter_column(engine):
    """Raise ValueError if filters reference invalid columns."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "value": 100.0})

    with pytest.raises(ValueError, match="Invalid filter columns"):
        update_record(engine, ExampleTable, 
                     filters={"not_a_column": "x"},
                     updates={"value": 200.0})


def test_update_record_raises_on_invalid_update_column(engine):
    """Raise ValueError if updates reference invalid columns."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "value": 100.0})

    with pytest.raises(ValueError, match="Invalid update columns"):
        update_record(engine, ExampleTable,
                     filters={"iso_code": "AFG"},
                     updates={"not_a_column": 200.0})


def test_update_record_updates_multiple_rows(engine):
    """Update multiple matching rows at once."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG1", "country": "Afghanistan", "value": 100.0})
    insert_record(engine, ExampleTable, {"iso_code": "AFG2", "country": "Afghanistan", "value": 150.0})

    rows_updated = update_record(
        engine, ExampleTable,
        filters={"country": "Afghanistan"},
        updates={"value": 200.0}
    )

    assert rows_updated == 2


def test_update_record_exception_triggers_rollback(engine):
    """Force an error to exercise rollback."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "value": 100.0})

    with pytest.raises(Exception):
        update_record(engine, ExampleTable,
                     filters={"iso_code": "AFG"},
                     updates={"value": {"not": "serializable"}})

    # Verify unchanged after rollback
    records = get_all_records(engine, ExampleTable)
    assert records[0].value == 100.0


def test_bulk_replace_table_on_empty_table(engine):
    """Insert data into empty table using bulk_replace_table."""
    df = pd.DataFrame([
        {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0},
        {"iso_code": "GBR", "country": "United Kingdom", "value": 200.0}
    ])

    bulk_replace_table(engine, ExampleTable, df)

    records = get_all_records(engine, ExampleTable)
    assert len(records) == 2


def test_bulk_replace_table_deletes_old_rows(engine):
    """Replace existing rows."""
    insert_record(engine, ExampleTable, {"iso_code": "OLD", "value": 1.0})

    df = pd.DataFrame([{"iso_code": "AFG", "value": 100.0}])
    bulk_replace_table(engine, ExampleTable, df)

    records = get_all_records(engine, ExampleTable)
    assert len(records) == 1
    assert records[0].iso_code == "AFG"


def test_bulk_replace_table_with_empty_dataframe_clears_table(engine):
    """Clear all rows when given empty DataFrame."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "value": 100.0})

    df_empty = pd.DataFrame(columns=["iso_code", "value"])
    bulk_replace_table(engine, ExampleTable, df_empty)

    records = get_all_records(engine, ExampleTable)
    assert len(records) == 0


def test_bulk_replace_table_idempotent(engine):
    """Running twice with same DataFrame yields same result."""
    df = pd.DataFrame([{"iso_code": "AFG", "value": 100.0}])

    bulk_replace_table(engine, ExampleTable, df)
    bulk_replace_table(engine, ExampleTable, df)

    records = get_all_records(engine, ExampleTable)
    assert len(records) == 1
    assert records[0].iso_code == "AFG"


# ==================== DELETE OPERATIONS TESTS ====================

def test_delete_record_single_match(engine):
    """Test deleting single record with exact match."""
    insert_record(engine, SampleTable, {'iso_code': 'IND', 'total_cases': 1000.0})
    insert_record(engine, SampleTable, {'iso_code': 'USA', 'total_cases': 2000.0})
    
    rows_deleted = delete_record(engine, SampleTable, {'iso_code': 'IND'})
    assert rows_deleted == 1


def test_delete_record_multiple_matches(engine):
    """Test deleting multiple records matching filters."""
    insert_record(engine, SampleTable, {'iso_code': 'IND', 'total_cases': 1000.0})
    insert_record(engine, SampleTable, {'iso_code': 'IND', 'total_cases': 1500.0})
    insert_record(engine, SampleTable, {'iso_code': 'USA', 'total_cases': 2000.0})
    
    rows_deleted = delete_record(engine, SampleTable, {'iso_code': 'IND'})
    assert rows_deleted == 2


def test_delete_record_no_matches(engine):
    """Test deleting with no matching records."""
    rows_deleted = delete_record(engine, SampleTable, {'iso_code': 'BRA'})
    assert rows_deleted == 0


def test_delete_record_invalid_column(engine):
    """Test error on invalid column name."""
    with pytest.raises(ValueError, match="Invalid filter columns"):
        delete_record(engine, SampleTable, {'invalid_col': 'value'})


def test_delete_record_no_filters(engine):
    """Test error when no filters provided."""
    with pytest.raises(ValueError, match="At least one filter condition"):
        delete_record(engine, SampleTable, {})


def test_delete_record_multiple_filters(engine):
    """Test multiple filter conditions."""
    insert_record(engine, SampleTable, {'iso_code': 'USA', 'total_cases': 2000.0})
    insert_record(engine, SampleTable, {'iso_code': 'USA', 'total_cases': 3000.0})
    
    rows_deleted = delete_record(engine, SampleTable, {'iso_code': 'USA', 'total_cases': 2000.0})
    assert rows_deleted == 1


# ==================== COVID DATA MODEL TESTS ====================

def test_covid_data_raw_nullable_fields(engine):
    """Test that CovidDataRaw accepts null values."""
    data = {
        'iso_code': 'TST',
        'location': 'Test',
        'continent': None,  # Nullable
        'date': None,       # Nullable
        'total_cases': None # Nullable
    }
    
    record_id = insert_record(engine, CovidDataRaw, data)
    assert record_id > 0


def test_covid_data_clean_not_null_enforced(engine):
    """Test that CovidDataClean enforces NOT NULL constraints."""
    import pandas as pd
    
    # This should fail because clean table has NOT NULL constraints
    data = {
        'iso_code': 'TST',
        'location': 'Test',
        'continent': None,  # NOT NULL - should fail
        'date': pd.Timestamp('2020-01-01'),
        'total_cases': 100.0,
        'new_cases': 10.0,
        'total_deaths': 5.0,
        'new_deaths': 1.0,
        'gdp_per_capita': 50000.0,
        'population': 5000000.0
    }
    
    with pytest.raises(IntegrityError):
        insert_record(engine, CovidDataClean, data)


def test_covid_data_working_matches_clean_schema(engine):
    """Test that working table has same constraints as clean."""
    inspector = inspect(engine)
    
    clean_cols = {col['name']: col for col in inspector.get_columns('covid_data_clean')}
    working_cols = {col['name']: col for col in inspector.get_columns('covid_data_working')}
    
    # Same columns
    assert set(clean_cols.keys()) == set(working_cols.keys())
    
    # Same nullability
    for col_name in clean_cols:
        assert clean_cols[col_name]['nullable'] == working_cols[col_name]['nullable']