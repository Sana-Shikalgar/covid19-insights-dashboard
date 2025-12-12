import pytest
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine
from src.data_loader import load_csv_to_df, load_csv_to_db, load_db_to_df, load_df_to_db, load_db_to_csv, load_df_to_csv
from src.db_engine import Base, ExampleTable, get_all_records, insert_record


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
    data = load_csv_to_df(csv_exists)
    assert len(data) == 11


def test_load_csv_column_names(csv_exists):
    """Verify 60+ COVID columns loaded."""
    data = load_csv_to_df(csv_exists)
    key_cols = {"iso_code", "continent", "location", "date", "total_cases", "population"}
    for col in key_cols:
        assert col in data.columns
    assert len(data.columns) >= 60


def test_load_csv_file_not_found():
    """Test loading non-existent CSV raises FileNotFoundError."""
    bad_path = Path("data/sample/nonexistent.csv")
    
    with pytest.raises(FileNotFoundError, match="CSV not found"):
        load_csv_to_df(bad_path)


def test_load_csv_invalid_path():
    """Test invalid path handling."""
    invalid_path = "/invalid/path/does/not/exist.csv"
    
    with pytest.raises(FileNotFoundError, match="CSV not found"):
        load_csv_to_df(invalid_path)


def test_load_csv_empty_path():
    """Test empty string path."""
    with pytest.raises(FileNotFoundError, match="CSV not found"):
        load_csv_to_df("")


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


# ---------- load_db_to_df tests ----------

def test_load_db_to_df_returns_all_rows_and_columns(engine, tmp_path):
    """load_db_to_df should return all rows and all columns by default."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})
    insert_record(engine, ExampleTable, {"iso_code": "GBR", "country": "United Kingdom", "value": 200.0})

    df = load_db_to_df(engine, ExampleTable.__table__)

    assert df.shape == (2, 3)
    assert set(df.columns) == {"iso_code", "country", "value"}


def test_load_db_to_df_with_column_subset(engine):
    """load_db_to_df should support selecting only a subset of columns."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    df = load_db_to_df(engine, ExampleTable, columns=["iso_code", "value"])

    assert set(df.columns) == {"iso_code", "value"}
    assert df.loc[0, "iso_code"] == "AFG"
    assert df.loc[0, "value"] == 100.0


def test_load_db_to_df_empty_table_returns_empty_dataframe(engine):
    """When the table is empty, load_db_to_df should return an empty DataFrame."""
    df = load_db_to_df(engine, ExampleTable.__table__)
    assert df.empty


def test_load_db_to_df_raises_on_error(monkeypatch, engine, caplog):
    def bad_query(*args, **kwargs):
        raise RuntimeError("boom")

    # Patch the helper function you use to get a Session or query;
    # if you don't have one, patch Session.query on the module you use.
    monkeypatch.setattr("src.data_loader.Session.query", bad_query, raising=False)

    with pytest.raises(RuntimeError):
        load_db_to_df(engine, ExampleTable.__table__)

    assert any("load_db_to_df failed" in r.message for r in caplog.records)


# ---------- load_df_to_db tests ----------

def test_load_df_to_db_creates_table_when_not_exists(engine):
    """When table does not exist, load_df_to_db should create it and bulk insert."""
    df = pd.DataFrame([
        {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0},
        {"iso_code": "GBR", "country": "United Kingdom", "value": 200.0},
    ])

    # Use a fresh table name; model_class=None to force dynamic table creation
    TargetTable = load_df_to_db(engine, df, table_name="dynamic_example", model_class=None)

    records = get_all_records(engine, TargetTable)
    assert len(records) == 2
    assert {r.iso_code for r in records} == {"AFG", "GBR"}


def test_load_df_to_db_bulk_replaces_when_table_exists(engine):
    """When model_class table exists, load_df_to_db should bulk replace its contents."""
    # Seed ExampleTable with one row
    insert_record(engine, ExampleTable, {"iso_code": "OLD", "country": "Oldland", "value": 1.0})

    # New data to replace existing rows
    df = pd.DataFrame([
        {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0},
    ])

    TargetTable = load_df_to_db(engine, df, table_name="example_table", model_class=ExampleTable)
    assert TargetTable is ExampleTable

    records = get_all_records(engine, ExampleTable)
    assert len(records) == 1
    assert records[0].iso_code == "AFG"
    assert records[0].value == 100.0


def test_load_df_to_db_raises_on_empty_dataframe(engine):
    """load_df_to_db should refuse to run when given an empty or None DataFrame."""
    empty_df = pd.DataFrame()

    with pytest.raises(ValueError):
        load_df_to_db(engine, empty_df, table_name="example_table", model_class=ExampleTable)


def test_load_df_to_db_raises_on_error(monkeypatch, engine, caplog):
    df = pd.DataFrame([{"iso_code": "AFG", "country": "Afghanistan", "value": 100.0}])

    def bad_create(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.data_loader.create_dynamic_table", bad_create)

    with pytest.raises(RuntimeError):
        load_df_to_db(engine, df, table_name="dynamic_example", model_class=None)

    assert any("load_df_to_db failed" in r.message for r in caplog.records)


# ---------- load_db_to_csv tests ----------

def test_load_db_to_csv_writes_expected_file(engine, tmp_path):
    """load_db_to_csv should create a CSV file with the table contents."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    csv_path = tmp_path / "exports" / "example.csv"
    load_db_to_csv(engine, ExampleTable.__table__, str(csv_path))

    assert csv_path.exists()

    df = pd.read_csv(csv_path)
    assert df.shape == (1, 3)
    assert df.loc[0, "iso_code"] == "AFG"
    assert df.loc[0, "country"] == "Afghanistan"
    assert df.loc[0, "value"] == 100.0


def test_load_db_to_csv_with_column_subset(engine, tmp_path):
    """load_db_to_csv should support exporting only selected columns."""
    insert_record(engine, ExampleTable, {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0})

    csv_path = tmp_path / "exports" / "example_subset.csv"
    load_db_to_csv(engine, ExampleTable, str(csv_path), columns=["iso_code"])

    df = pd.read_csv(csv_path)
    assert list(df.columns) == ["iso_code"]
    assert df.loc[0, "iso_code"] == "AFG"


def test_load_db_to_csv_raises_on_inner_error(monkeypatch, engine, tmp_path, caplog):
    def bad_loader(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.data_loader.load_db_to_df", bad_loader)

    csv_path = tmp_path / "exports" / "example.csv"
    with pytest.raises(RuntimeError):
        load_db_to_csv(engine, ExampleTable, str(csv_path))

    assert any("load_db_to_csv failed" in r.message for r in caplog.records)


# ---------- load_df_to_csv tests ----------

def test_load_df_to_csv_writes_file(tmp_path):
    """load_df_to_csv should write DataFrame contents to the given CSV path."""
    df = pd.DataFrame([
        {"iso_code": "AFG", "country": "Afghanistan", "value": 100.0},
    ])

    csv_path = tmp_path / "exports" / "df_export.csv"
    load_df_to_csv(df, str(csv_path))

    assert csv_path.exists()

    reloaded = pd.read_csv(csv_path)
    pd.testing.assert_frame_equal(reloaded, df)


def test_load_df_to_csv_raises_on_empty_or_none(tmp_path):
    """load_df_to_csv should raise ValueError when df is empty or None."""
    empty_df = pd.DataFrame()
    csv_path = tmp_path / "exports" / "empty.csv"

    with pytest.raises(ValueError):
        load_df_to_csv(empty_df, str(csv_path))

    with pytest.raises(ValueError):
        load_df_to_csv(None, str(csv_path))  # type: ignore[arg-type]


def test_load_df_to_csv_raises_on_to_csv_error(monkeypatch, tmp_path, caplog):
    df = pd.DataFrame([{"a": 1}])

    def bad_to_csv(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr("pandas.DataFrame.to_csv", bad_to_csv)

    csv_path = tmp_path / "exports" / "data.csv"
    with pytest.raises(OSError):
        load_df_to_csv(df, str(csv_path))

    assert any("load_df_to_csv failed" in r.message for r in caplog.records)

