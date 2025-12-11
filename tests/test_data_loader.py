import pytest
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.data_loader import load_csv_data, load_csv_to_db
from src.db_engine import Base, ExampleTable, get_all_records


@pytest.fixture
def sample_covid_path():
    """Path to your test CSV."""
    return Path("data/sample/test_data.csv")


@pytest.fixture
def csv_exists(sample_covid_path):
    """Skip tests if CSV missing."""
    if not sample_covid_path.exists():
        pytest.skip("Sample CSV not found - create data/sample/test_data.csv")
    return sample_covid_path


@pytest.fixture
def engine():
    # In-memory SQLite DB for each test
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    

def test_load_csv_row_count(csv_exists):
    """Verify CSV loads 10 rows."""
    data = load_csv_data(csv_exists)
    assert len(data) == 11


def test_load_csv_column_names(csv_exists):
    """Verify 60+ COVID columns loaded."""
    data = load_csv_data(csv_exists)
    key_cols = {"iso_code", "continent", "location", "date", "total_cases", "population"}
    for col in key_cols:
        assert col in data.columns
    assert len(data.columns) >= 60


def test_load_csv_file_not_found():
    """Test loading non-existent CSV raises FileNotFoundError."""
    bad_path = Path("data/sample/nonexistent.csv")
    
    with pytest.raises(FileNotFoundError, match="CSV not found"):
        load_csv_data(bad_path)


def test_load_csv_invalid_path():
    """Test invalid path handling."""
    invalid_path = "/invalid/path/does/not/exist.csv"
    
    with pytest.raises(FileNotFoundError, match="CSV not found"):
        load_csv_data(invalid_path)


def test_load_csv_empty_path():
    """Test empty string path."""
    with pytest.raises(FileNotFoundError, match="CSV not found"):
        load_csv_data("")


def test_load_csv_to_db(engine, csv_exists):
    """Test loading CSV data into the database."""
    # Load CSV to DB
    result = load_csv_to_db(engine, csv_exists, ExampleTable)
    
    # Verify insertion worked
    records = get_all_records(engine, ExampleTable)
    assert result["inserted"] > 0
    assert len(records) == result["inserted"]
    
    # Verify sample data (AFG from your CSV)
    afg_records = [r for r in records if r.iso_code == "AFG"]
    assert len(afg_records) > 0
    print(f"{result['inserted']} rows inserted! Found {len(afg_records)} AFG records")


def test_load_csv_to_db_empty_csv(engine, tmp_path):
    """Test loading from an empty CSV file results in 0 inserts."""
    empty_csv = tmp_path / "empty.csv"
    # Header matches ExampleTable columns you care about
    empty_csv.write_text("iso_code,value,country\n")

    result = load_csv_to_db(engine, empty_csv, ExampleTable)

    records = get_all_records(engine, ExampleTable)
    assert result["inserted"] == 0
    assert result["skipped"] == 0
    assert len(records) == 0


def test_load_csv_to_db_missing_file(engine, tmp_path):
    """Test loading from a missing CSV file raises FileNotFoundError."""
    missing = tmp_path / "does_not_exist.csv"

    with pytest.raises(FileNotFoundError):
        load_csv_to_db(engine, missing, ExampleTable)


def test_load_csv_to_db_duplicates_skipped(engine, tmp_path):
    """Test that duplicate rows in CSV are skipped during bulk_insert."""
    csv_path = tmp_path / "dupe.csv"
    csv_path.write_text(
        "iso_code,value,country\n"
        "USA,100,United States\n"
        "USA,200,United States\n"  # duplicate iso_code
    )

    result = load_csv_to_db(engine, csv_path, ExampleTable)

    records = get_all_records(engine, ExampleTable)
    # One inserted, one skipped due to UNIQUE(iso_code)
    assert result["inserted"] == 1
    assert result["skipped"] == 1
    assert len(records) == 1
    assert records[0].iso_code == "USA"


def test_load_csv_to_db_missing_csv_columns(engine, tmp_path):
    """Test handling of missing columns in CSV during load."""
    csv_path = tmp_path / "missing_cols.csv"
    csv_path.write_text(
        "iso_code,value\n"           # NO 'country' column!
        "AFG,100\n"
    )

    result = load_csv_to_db(engine, csv_path, ExampleTable)

    records = get_all_records(engine, ExampleTable)
    assert result["inserted"] == 1
    assert len(records) == 1
    assert records[0].iso_code == "AFG"
    assert records[0].value == 100
    assert records[0].country is None  # ✅ Missing CSV col → NULL in DB


def test_load_csv_to_db_extra_columns(engine, tmp_path):
    """Test handling of extra columns in CSV during load. Ignore extra columsn gracefully"""
    csv_path = tmp_path / "extra_cols.csv"
    csv_path.write_text(
        "iso_code,value,country,extra_col\n"
        "GBR,150,United Kingdom,something\n"
    )

    result = load_csv_to_db(engine, csv_path, ExampleTable)

    records = get_all_records(engine, ExampleTable)
    assert result["inserted"] == 1
    assert len(records) == 1
    assert records[0].iso_code == "GBR"
    assert records[0].value == 150
    assert records[0].country == "United Kingdom"

