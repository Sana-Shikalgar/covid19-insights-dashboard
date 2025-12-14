"""
Data loader tests - Updated for static model architecture.

All dynamic table creation tests have been REMOVED.
Tests now use only statically defined models from models.py
"""

import pytest
import pandas as pd
from pathlib import Path

from src.data_loader import (
    load_csv_to_df, load_df_to_csv, load_db_to_df, load_df_to_db,
    load_csv_to_db, load_db_to_csv
)
from src.db_engine import get_engine, create_all_tables, get_all_records, insert_record
from src.models import ExampleTable, CovidDataRaw


# ==================== FIXTURES ====================

@pytest.fixture
def engine():
    """In-memory SQLite DB for each test."""
    engine = get_engine("sqlite:///:memory:")
    create_all_tables(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def sample_covid_path():
    """Path to test CSV."""
    return Path("data/sample/test_data.csv")


@pytest.fixture
def csv_exists(sample_covid_path):
    """Skip tests if CSV missing."""
    if not sample_covid_path.exists():
        pytest.skip("Sample CSV not found - create data/sample/test_data.csv")
    return sample_covid_path


@pytest.fixture
def sample_data():
    """Sample DataFrame matching ExampleTable schema."""
    return pd.DataFrame({
        'iso_code': ['USA', 'GBR', 'FRA'],
        'value': [100.0, 200.0, 300.0],
        'country': ['United States', 'United Kingdom', 'France']
    })


# ==================== CSV TO DATAFRAME TESTS ====================

def test_load_csv_row_count(csv_exists):
    """Verify CSV loads expected number of rows."""
    data = load_csv_to_df(csv_exists)
    assert len(data) == 11


def test_load_csv_column_names(csv_exists):
    """Verify COVID columns loaded."""
    data = load_csv_to_df(csv_exists)
    key_cols = {"iso_code", "continent", "location", "date", "total_cases", "population"}
    for col in key_cols:
        assert col in data.columns
    assert len(data.columns) >= 60


def test_load_csv_file_not_found():
    """Test loading non-existent CSV raises FileNotFoundError."""
    bad_path = Path("data/sample/nonexistent.csv")
    
    with pytest.raises(FileNotFoundError, match="CSV file not found:"):
        load_csv_to_df(bad_path)


def test_load_csv_invalid_path():
    """Test invalid path handling."""
    invalid_path = "/invalid/path/does/not/exist.csv"
    
    with pytest.raises(FileNotFoundError, match="CSV file not found:"):
        load_csv_to_df(invalid_path)


def test_load_csv_empty_path():
    """Test empty string path."""
    with pytest.raises(FileNotFoundError, match="CSV path cannot be empty"):
        load_csv_to_df("")


# ==================== DATAFRAME TO CSV TESTS ====================

def test_load_df_to_csv_writes_file(tmp_path, sample_data):
    """Test writing DataFrame to CSV."""
    csv_path = tmp_path / "exports" / "df_export.csv"
    load_df_to_csv(sample_data, str(csv_path))
    
    assert csv_path.exists()
    
    reloaded = pd.read_csv(csv_path)
    pd.testing.assert_frame_equal(reloaded, sample_data)


def test_load_df_to_csv_raises_on_empty(tmp_path):
    """Test that empty DataFrame raises ValueError."""
    empty_df = pd.DataFrame()
    csv_path = tmp_path / "exports" / "empty.csv"
    
    with pytest.raises(ValueError, match="empty or None"):
        load_df_to_csv(empty_df, str(csv_path))


def test_load_df_to_csv_raises_on_none(tmp_path):
    """Test that None DataFrame raises ValueError."""
    csv_path = tmp_path / "exports" / "none.csv"
    
    with pytest.raises(ValueError, match="empty or None"):
        load_df_to_csv(None, str(csv_path))


def test_load_df_to_csv_creates_directory(tmp_path):
    """Test that missing directories are created."""
    csv_path = tmp_path / "nested" / "dirs" / "file.csv"
    df = pd.DataFrame({'a': [1, 2]})
    
    load_df_to_csv(df, str(csv_path))
    
    assert csv_path.exists()


# ==================== DATABASE TO DATAFRAME TESTS ====================

def test_load_db_to_df_returns_all_rows(engine):
    """Test loading all rows from database."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})
    insert_record(engine, ExampleTable, {"iso_code": "GBR", "country": "United Kingdom", "value": 200.0})

    df = load_db_to_df(engine, ExampleTable)

    assert df.shape[0] == 2
    assert set(df.columns) == {"iso_code", "country", "value"}


def test_load_db_to_df_with_column_subset(engine):
    """Test loading specific columns only."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    df = load_db_to_df(engine, ExampleTable, columns=["iso_code", "value"])

    assert set(df.columns) == {"iso_code", "value"}
    assert "country" not in df.columns


def test_load_db_to_df_empty_table_returns_empty_dataframe(engine):
    """Test loading from empty table."""
    df = load_db_to_df(engine, ExampleTable)
    assert df.empty


def test_load_db_to_df_excludes_id_by_default(engine):
    """Test that 'id' column is excluded by default."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "value": 100.0})
    
    df = load_db_to_df(engine, ExampleTable)
    
    assert 'id' not in df.columns


# ==================== DATAFRAME TO DATABASE TESTS ====================

def test_load_df_to_db_replaces_table_contents(engine, sample_data):
    """Test that load_df_to_db replaces existing data."""
    # Insert initial data
    insert_record(engine, ExampleTable, {"iso_code": "OLD", "value": 1.0})
    
    # Load new data
    load_df_to_db(engine, sample_data, ExampleTable)
    
    # Verify old data replaced
    records = get_all_records(engine, ExampleTable)
    assert len(records) == 3
    assert not any(r.iso_code == "OLD" for r in records)


def test_load_df_to_db_raises_on_empty_dataframe(engine):
    """Test that empty DataFrame raises ValueError."""
    empty_df = pd.DataFrame()
    
    with pytest.raises(ValueError, match="empty or None"):
        load_df_to_db(engine, empty_df, ExampleTable)


def test_load_df_to_db_raises_on_none(engine):
    """Test that None DataFrame raises ValueError."""
    with pytest.raises(ValueError, match="empty or None"):
        load_df_to_db(engine, None, ExampleTable)


def test_load_df_to_db_filters_to_model_columns(engine):
    """Test that extra DataFrame columns are handled."""
    df = pd.DataFrame({
        'iso_code': ['USA'],
        'value': [100.0],
        'country': ['United States'],
        'extra_column': ['ignored']  # Not in model
    })
    
    # Should succeed - extra columns ignored during bulk_replace_table
    load_df_to_db(engine, df, ExampleTable)
    
    records = get_all_records(engine, ExampleTable)
    assert len(records) == 1


# ==================== CSV TO DATABASE TESTS ====================

def test_load_csv_to_db_basic(engine, csv_exists):
    """Test loading CSV data into database."""
    result = load_csv_to_db(engine, csv_exists, CovidDataRaw, filter_columns=True)
    
    assert result["inserted"] > 0
    
    records = get_all_records(engine, CovidDataRaw)
    assert len(records) == result["inserted"]


def test_load_csv_to_db_empty_csv(engine, tmp_path):
    """Test loading empty CSV results in 0 inserts."""
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("iso_code,value,country\n")  # Header only

    result = load_csv_to_db(engine, empty_csv, ExampleTable, filter_columns=True)

    assert result["inserted"] == 0
    assert result["skipped"] == 0


def test_load_csv_to_db_missing_file(engine, tmp_path):
    """Test loading missing CSV raises FileNotFoundError."""
    missing = tmp_path / "does_not_exist.csv"

    with pytest.raises(FileNotFoundError):
        load_csv_to_db(engine, missing, ExampleTable)


def test_load_csv_to_db_duplicates_skipped(engine, tmp_path):
    """Test that duplicate rows are skipped."""
    csv_path = tmp_path / "dupe.csv"
    csv_path.write_text(
        "iso_code,value,country\n"
        "USA,100,United States\n"
        "USA,200,United States\n"  # Duplicate iso_code
    )

    result = load_csv_to_db(engine, csv_path, ExampleTable, filter_columns=True)

    assert result["inserted"] == 1
    assert result["skipped"] == 1


def test_load_csv_to_db_missing_csv_columns(engine, tmp_path):
    """Test handling of missing columns in CSV."""
    csv_path = tmp_path / "missing_cols.csv"
    csv_path.write_text(
        "iso_code,value\n"  # NO 'country' column
        "AFG,100\n"
    )

    result = load_csv_to_db(engine, csv_path, ExampleTable, filter_columns=True)

    records = get_all_records(engine, ExampleTable)
    assert result["inserted"] == 1
    assert records[0].iso_code == "AFG"
    assert records[0].value == 100
    assert records[0].country is None


def test_load_csv_to_db_extra_columns(engine, tmp_path):
    """Test handling of extra columns in CSV."""
    csv_path = tmp_path / "extra_cols.csv"
    csv_path.write_text(
        "iso_code,value,country,extra_col\n"
        "GBR,150,United Kingdom,something\n"
    )

    result = load_csv_to_db(engine, csv_path, ExampleTable, filter_columns=True)

    records = get_all_records(engine, ExampleTable)
    assert result["inserted"] == 1
    assert records[0].iso_code == "GBR"


# ==================== DATABASE TO CSV TESTS ====================

def test_load_db_to_csv_writes_expected_file(engine, tmp_path):
    """Test exporting database to CSV."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    csv_path = tmp_path / "exports" / "example.csv"
    load_db_to_csv(engine, ExampleTable, str(csv_path))

    assert csv_path.exists()

    df = pd.read_csv(csv_path)
    assert df.shape[0] == 1
    assert df.loc[0, "iso_code"] == "AFG"


def test_load_db_to_csv_with_column_subset(engine, tmp_path):
    """Test exporting specific columns only."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    csv_path = tmp_path / "exports" / "subset.csv"
    load_db_to_csv(engine, ExampleTable, str(csv_path), columns=["iso_code"])

    df = pd.read_csv(csv_path)
    assert list(df.columns) == ["iso_code"]


def test_load_db_to_csv_empty_table(engine, tmp_path):
    """Test exporting empty table."""
    csv_path = tmp_path / "exports" / "empty.csv"
    load_db_to_csv(engine, ExampleTable, str(csv_path))

    df = pd.read_csv(csv_path)
    assert df.empty


def test_load_db_to_csv_creates_directory(engine, tmp_path):
    """Test that export creates missing directories."""
    insert_record(engine, ExampleTable, {"iso_code": "USA", "value": 100.0})
    
    csv_path = tmp_path / "nested" / "dirs" / "export.csv"
    load_db_to_csv(engine, ExampleTable, str(csv_path))
    
    assert csv_path.exists()


# ==================== INTEGRATION TESTS ====================

def test_round_trip_csv_db_csv(engine, tmp_path, sample_data):
    """Test complete round trip: CSV → DB → CSV."""
    # Save original to CSV
    csv_original = tmp_path / "original.csv"
    sample_data.to_csv(csv_original, index=False)
    
    # Load to DB
    load_csv_to_db(engine, csv_original, ExampleTable, filter_columns=True)
    
    # Export back to CSV
    csv_export = tmp_path / "export.csv"
    load_db_to_csv(engine, ExampleTable, str(csv_export))
    
    # Compare
    df_original = pd.read_csv(csv_original)
    df_export = pd.read_csv(csv_export)
    
    pd.testing.assert_frame_equal(
        df_original.sort_values('iso_code').reset_index(drop=True),
        df_export.sort_values('iso_code').reset_index(drop=True)
    )


def test_load_multiple_layers(engine, sample_data):
    """Test loading data into multiple table layers."""
    # Load into raw table
    load_df_to_db(engine, sample_data, ExampleTable)
    
    # Verify
    df_from_db = load_db_to_df(engine, ExampleTable)
    assert len(df_from_db) == len(sample_data)


def test_filter_columns_true_removes_extra(engine, tmp_path):
    """Test that filter_columns=True removes non-model columns."""
    csv_path = tmp_path / "extra.csv"
    df = pd.DataFrame({
        'iso_code': ['USA'],
        'value': [100.0],
        'extra1': ['ignored'],
        'extra2': ['also_ignored']
    })
    df.to_csv(csv_path, index=False)
    
    result = load_csv_to_db(engine, csv_path, ExampleTable, filter_columns=True)
    
    assert result["inserted"] == 1
    records = get_all_records(engine, ExampleTable)
    assert len(records) == 1


def test_filter_columns_false_includes_all(engine, tmp_path):
    """Test that filter_columns=False attempts to use all columns."""
    csv_path = tmp_path / "all.csv"
    df = pd.DataFrame({
        'iso_code': ['USA'],
        'value': [100.0],
        'country': ['United States']
    })
    df.to_csv(csv_path, index=False)
    
    result = load_csv_to_db(engine, csv_path, ExampleTable, filter_columns=False)
    
    assert result["inserted"] == 1