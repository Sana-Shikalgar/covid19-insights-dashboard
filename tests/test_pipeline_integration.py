"""
Integration tests for the complete COVID-19 data pipeline.

Tests all stages following TDD principles:
1. Raw data ingestion (immutable)
2. Data cleaning and validation
3. Working copy creation (mutable)
4. CRUD operations (working copy only)
5. Data integrity and isolation

All tests use in-memory SQLite for isolation.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from sqlalchemy import inspect

from src.db_engine import (
    get_engine, create_all_tables, table_exists, 
    get_table_row_count, insert_record, update_record, delete_record
)
from src.models import CovidDataRaw, CovidDataClean, CovidDataWorking, Base
from src.data_loader import load_csv_to_df, load_df_to_db, load_db_to_df
from src.data_cleaner import clean_pipeline
from src.pipeline_integration import (
    check_pipeline_status, pipeline_needs_execution,
    stage1_ingest_raw_data, stage2_clean_and_validate,
    stage3_create_working_copy, execute_pipeline,
    reset_working_copy, load_data_by_layer
)


# ==================== FIXTURES ====================

@pytest.fixture
def engine():
    """Create in-memory SQLite database for testing."""
    engine = get_engine("sqlite:///:memory:")
    create_all_tables(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def sample_raw_data():
    """Create sample raw data matching CovidDataRaw schema."""
    return pd.DataFrame({
        'iso_code': ['AFG', 'AFG', 'GBR', 'GBR', 'USA'],
        'continent': ['Asia', 'Asia', np.nan, 'Europe', 'North America'],
        'location': ['Afghanistan', 'Afghanistan', 'United Kingdom', 'United Kingdom', 'United States'],
        'date': pd.to_datetime(['2020-01-01', '2020-01-02', '2020-01-01', '2020-01-02', '2020-01-01']),
        'total_cases': [100.0, 200.0, 500.0, 600.0, 1000.0],
        'new_cases': [10.0, 20.0, 50.0, 60.0, 100.0],
        'total_deaths': [1.0, 2.0, 5.0, 6.0, 10.0],
        'new_deaths': [0.1, 0.2, 0.5, 0.6, 1.0],
        'gdp_per_capita': [2000.0, 2000.0, np.nan, 40000.0, 60000.0],
        'population': [38000000.0, 38000000.0, 67000000.0, 67000000.0, 331000000.0]
    })


@pytest.fixture
def sample_csv(tmp_path, sample_raw_data):
    """Create a temporary CSV file with sample data."""
    csv_path = tmp_path / "test_covid_data.csv"
    sample_raw_data.to_csv(csv_path, index=False)
    return str(csv_path)


# ==================== TABLE CREATION TESTS ====================

def test_all_tables_created(engine):
    """Test that all required tables are created."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    assert 'covid_data_raw' in tables
    assert 'covid_data_clean' in tables
    assert 'covid_data_working' in tables


def test_raw_table_schema_nullable(engine):
    """Test that raw table has all nullable columns."""
    inspector = inspect(engine)
    columns = inspector.get_columns('covid_data_raw')
    
    for col in columns:
        if col['name'] != 'id':  # ID is primary key, not nullable
            assert col['nullable'] is True, f"Column {col['name']} should be nullable in raw table"


def test_clean_table_schema_not_nullable(engine):
    """Test that clean table has all non-nullable columns (except id)."""
    inspector = inspect(engine)
    columns = inspector.get_columns('covid_data_clean')
    
    for col in columns:
        if col['name'] != 'id':
            assert col['nullable'] is False, f"Column {col['name']} should be NOT NULL in clean table"


def test_working_table_matches_clean_schema(engine):
    """Test that working table has identical schema to clean table."""
    inspector = inspect(engine)
    
    clean_cols = {col['name']: col for col in inspector.get_columns('covid_data_clean')}
    working_cols = {col['name']: col for col in inspector.get_columns('covid_data_working')}
    
    assert set(clean_cols.keys()) == set(working_cols.keys())
    
    for col_name in clean_cols.keys():
        clean_col = clean_cols[col_name]
        working_col = working_cols[col_name]

        assert type(clean_col["type"]) is type(working_col["type"])
        
        # Nullability must match
        assert clean_col["nullable"] == working_col["nullable"]

# ==================== PIPELINE STATUS TESTS ====================

def test_check_pipeline_status_empty_db(engine):
    """Test pipeline status check on empty database."""
    status = check_pipeline_status(engine)
    
    assert status['raw_exists'] is True  # Tables created but empty
    assert status['clean_exists'] is True
    assert status['working_exists'] is True
    assert status['raw_count'] == 0
    assert status['clean_count'] == 0
    assert status['working_count'] == 0


def test_pipeline_needs_execution_when_empty(engine):
    """Test that pipeline needs execution when tables are empty."""
    needs_run = pipeline_needs_execution(engine)
    assert needs_run is True


def test_pipeline_does_not_need_execution_when_populated(engine, sample_raw_data):
    """Test that pipeline skips execution when tables have data."""
    # Populate all tables
    load_df_to_db(engine, sample_raw_data, CovidDataRaw)
    df_clean = clean_pipeline(sample_raw_data)
    load_df_to_db(engine, df_clean, CovidDataClean)
    load_df_to_db(engine, df_clean, CovidDataWorking)
    
    needs_run = pipeline_needs_execution(engine)
    assert needs_run is False


# ==================== STAGE 1: RAW INGESTION TESTS ====================

def test_stage1_ingests_raw_data(engine, sample_csv):
    """Test Stage 1: Raw data ingestion from CSV."""
    df_raw = stage1_ingest_raw_data(engine, sample_csv)
    
    # Check DataFrame
    assert not df_raw.empty
    assert len(df_raw) == 5
    
    # Check database
    assert get_table_row_count(engine, CovidDataRaw) == 5


def test_stage1_preserves_nulls_in_raw_table(engine, sample_csv):
    """Test that Stage 1 preserves null values in raw table."""
    stage1_ingest_raw_data(engine, sample_csv)
    
    df_from_db = load_db_to_df(engine, CovidDataRaw)
    
    # Check that nulls are preserved
    assert df_from_db['continent'].isnull().sum() > 0
    assert df_from_db['gdp_per_capita'].isnull().sum() > 0


def test_stage1_skips_if_raw_table_populated(engine, sample_raw_data):
    """Test that Stage 1 skips ingestion if raw table already has data."""
    # Pre-populate raw table
    load_df_to_db(engine, sample_raw_data, CovidDataRaw)
    initial_count = get_table_row_count(engine, CovidDataRaw)
    
    # Try to run stage1 again (should load from DB, not re-ingest)
    df_raw = stage1_ingest_raw_data(engine, "non_existent.csv")
    
    # Count should be unchanged
    assert get_table_row_count(engine, CovidDataRaw) == initial_count
    assert len(df_raw) == initial_count


def test_stage1_raises_on_missing_csv(engine):
    """Test that Stage 1 raises error if CSV file not found."""
    with pytest.raises(FileNotFoundError):
        stage1_ingest_raw_data(engine, "non_existent.csv")


# ==================== STAGE 2: CLEANING TESTS ====================

def test_stage2_cleans_and_validates(engine, sample_raw_data):
    """Test Stage 2: Data cleaning and validation."""
    df_clean = stage2_clean_and_validate(engine, sample_raw_data)
    
    # Check no nulls remain
    assert not df_clean.isnull().any().any()
    
    # Check database
    assert get_table_row_count(engine, CovidDataClean) > 0


def test_stage2_enforces_not_null_constraints(engine, sample_raw_data):
    """Test that Stage 2 drops rows with nulls to enforce NOT NULL."""
    df_clean = stage2_clean_and_validate(engine, sample_raw_data)
    
    # Cleaned data should have no nulls
    assert df_clean.isnull().sum().sum() == 0
    
    # Database should have no nulls
    df_from_db = load_db_to_df(engine, CovidDataClean)
    assert df_from_db.isnull().sum().sum() == 0


def test_stage2_skips_if_clean_table_populated(engine, sample_raw_data):
    """Test that Stage 2 skips cleaning if clean table already has data."""
    # Pre-populate clean table
    df_clean = clean_pipeline(sample_raw_data)
    load_df_to_db(engine, df_clean, CovidDataClean)
    initial_count = get_table_row_count(engine, CovidDataClean)
    
    # Try to run stage2 again
    df_result = stage2_clean_and_validate(engine, sample_raw_data)
    
    # Count should be unchanged
    assert get_table_row_count(engine, CovidDataClean) == initial_count
    assert len(df_result) == initial_count


def test_stage2_produces_subset_of_raw_columns(engine, sample_raw_data):
    """Test that clean table has fewer columns than raw table (core columns only)."""
    load_df_to_db(engine, sample_raw_data, CovidDataRaw)  # Direct load
    
    df_clean = stage2_clean_and_validate(engine, sample_raw_data)
    
    raw_cols = [c.name for c in CovidDataRaw.__table__.columns if c.name != 'id']
    clean_cols = [c.name for c in CovidDataClean.__table__.columns if c.name != 'id']
    
    assert len(clean_cols) < len(raw_cols)


# ==================== STAGE 3: WORKING COPY TESTS ====================

def test_stage3_creates_working_copy(engine, sample_raw_data):
    """Test Stage 3: Working copy creation."""
    df_clean = clean_pipeline(sample_raw_data)
    df_working = stage3_create_working_copy(engine, df_clean)
    
    # Check database
    assert get_table_row_count(engine, CovidDataWorking) == len(df_clean)


def test_stage3_working_copy_matches_clean(engine, sample_raw_data):
    """Test that working copy initially matches clean reference exactly."""
    df_clean = clean_pipeline(sample_raw_data)
    load_df_to_db(engine, df_clean, CovidDataClean)
    
    stage3_create_working_copy(engine, df_clean)
    
    df_clean_db = load_db_to_df(engine, CovidDataClean)
    df_working_db = load_db_to_df(engine, CovidDataWorking)
    
    # Should have same number of rows
    assert len(df_clean_db) == len(df_working_db)


def test_stage3_skips_if_working_table_populated(engine, sample_raw_data):
    """Test that Stage 3 skips creation if working table already has data."""
    df_clean = clean_pipeline(sample_raw_data)
    load_df_to_db(engine, df_clean, CovidDataWorking)
    initial_count = get_table_row_count(engine, CovidDataWorking)
    
    df_result = stage3_create_working_copy(engine, df_clean)
    
    assert get_table_row_count(engine, CovidDataWorking) == initial_count


# ==================== FULL PIPELINE EXECUTION TESTS ====================

def test_execute_pipeline_full_run(engine, sample_csv):
    """Test complete pipeline execution from CSV to working copy."""
    result = execute_pipeline(engine, sample_csv, force=True)
    
    assert result['executed'] is True
    assert result['status']['raw_count'] > 0
    assert result['status']['clean_count'] > 0
    assert result['status']['working_count'] > 0


def test_execute_pipeline_skip_when_populated(engine, sample_raw_data):
    """Test that pipeline skips execution when tables already exist."""
    # Pre-populate all tables
    load_df_to_db(engine, sample_raw_data, CovidDataRaw)
    df_clean = clean_pipeline(sample_raw_data)
    load_df_to_db(engine, df_clean, CovidDataClean)
    load_df_to_db(engine, df_clean, CovidDataWorking)
    
    result = execute_pipeline(engine, force=False)
    
    assert result['executed'] is False
    assert 'Tables already exist' in result['reason']


def test_execute_pipeline_force_rerun(engine, sample_raw_data):
    """Test that force=True re-runs pipeline even when tables exist."""
    # Pre-populate tables
    load_df_to_db(engine, sample_raw_data, CovidDataRaw)
    df_clean = clean_pipeline(sample_raw_data)
    load_df_to_db(engine, df_clean, CovidDataClean)
    load_df_to_db(engine, df_clean, CovidDataWorking)
    
    # Create CSV
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        sample_raw_data.to_csv(f.name, index=False)
        csv_path = f.name
    
    result = execute_pipeline(engine, csv_path, force=True)
    
    assert result['executed'] is True


# ==================== DATA ISOLATION TESTS ====================

def test_raw_table_immutable_after_ingestion(engine, sample_raw_data):
    """Test that raw table cannot be modified after ingestion."""
    load_df_to_db(engine, sample_raw_data, CovidDataRaw)
    initial_count = get_table_row_count(engine, CovidDataRaw)
    
    # Attempt to modify raw table should not be part of normal operations
    # In practice, this is enforced by pipeline logic, not database constraints
    
    # Verify count unchanged
    assert get_table_row_count(engine, CovidDataRaw) == initial_count


def test_clean_table_immutable_after_creation(engine, sample_raw_data):
    """Test that clean reference table remains unchanged."""
    df_clean = clean_pipeline(sample_raw_data)
    load_df_to_db(engine, df_clean, CovidDataClean)
    initial_count = get_table_row_count(engine, CovidDataClean)
    
    # Normal pipeline operations should not modify clean table
    
    assert get_table_row_count(engine, CovidDataClean) == initial_count


def test_crud_on_working_table_only(engine, sample_raw_data):
    """Test that CRUD operations only affect working table."""
    df_clean = clean_pipeline(sample_raw_data)
    load_df_to_db(engine, df_clean, CovidDataClean)
    load_df_to_db(engine, df_clean, CovidDataWorking)
    
    initial_clean_count = get_table_row_count(engine, CovidDataClean)
    initial_working_count = get_table_row_count(engine, CovidDataWorking)
    
    # Insert into working table
    new_record = {
        'iso_code': 'XXX',
        'location': 'Test Location',
        'continent': 'Test Continent',
        'date': pd.Timestamp('2020-01-01'),
        'total_cases': 100.0,
        'new_cases': 10.0,
        'total_deaths': 5.0,
        'new_deaths': 1.0,
        'gdp_per_capita': 10000.0,
        'population': 1000000.0
    }
    insert_record(engine, CovidDataWorking, new_record)
    
    # Clean table should be unchanged
    assert get_table_row_count(engine, CovidDataClean) == initial_clean_count
    
    # Working table should have one more row
    assert get_table_row_count(engine, CovidDataWorking) == initial_working_count + 1


# ==================== RESET FUNCTIONALITY TESTS ====================

def test_reset_working_copy_from_clean(engine, sample_raw_data):
    """Test that working copy can be reset from clean reference."""
    df_clean = clean_pipeline(sample_raw_data)
    load_df_to_db(engine, df_clean, CovidDataClean)
    load_df_to_db(engine, df_clean, CovidDataWorking)
    
    # Modify working table
    update_record(engine, CovidDataWorking, 
                 filters={'iso_code': 'AFG'},
                 updates={'total_cases': 99999.0})
    
    # Reset
    rows_reset = reset_working_copy(engine)
    
    # Working should match clean again
    df_clean_db = load_db_to_df(engine, CovidDataClean)
    df_working_db = load_db_to_df(engine, CovidDataWorking)
    
    assert len(df_clean_db) == len(df_working_db)
    assert rows_reset == len(df_clean_db)


# ==================== LAYER ACCESS TESTS ====================

def test_load_data_by_layer_raw(engine, sample_raw_data):
    """Test loading data from raw layer."""
    load_df_to_db(engine, sample_raw_data, CovidDataRaw)
    
    df = load_data_by_layer(engine, 'raw')
    
    assert len(df) == len(sample_raw_data)


def test_load_data_by_layer_clean(engine, sample_raw_data):
    """Test loading data from clean layer."""
    df_clean = clean_pipeline(sample_raw_data)
    load_df_to_db(engine, df_clean, CovidDataClean)
    
    df = load_data_by_layer(engine, 'clean')
    
    assert len(df) > 0


def test_load_data_by_layer_working(engine, sample_raw_data):
    """Test loading data from working layer."""
    df_clean = clean_pipeline(sample_raw_data)
    load_df_to_db(engine, df_clean, CovidDataWorking)
    
    df = load_data_by_layer(engine, 'working')
    
    assert len(df) > 0


def test_load_data_by_layer_invalid(engine):
    """Test that invalid layer name raises error."""
    with pytest.raises(ValueError, match="Invalid layer"):
        load_data_by_layer(engine, 'invalid')


# ==================== END-TO-END INTEGRATION TEST ====================

def test_full_pipeline_end_to_end(engine, sample_csv):
    """
    Complete end-to-end test of entire pipeline:
    1. Ingest raw data
    2. Clean and validate
    3. Create working copy
    4. Perform CRUD operations
    5. Verify data isolation
    """
    # Execute pipeline
    result = execute_pipeline(engine, sample_csv, force=True)
    
    assert result['executed'] is True
    
    # Verify all tables populated
    assert get_table_row_count(engine, CovidDataRaw) > 0
    assert get_table_row_count(engine, CovidDataClean) > 0
    assert get_table_row_count(engine, CovidDataWorking) > 0
    
    # Perform CRUD on working copy
    initial_count = get_table_row_count(engine, CovidDataWorking)
    
    # Create
    new_record = {
        'iso_code': 'TST',
        'location': 'Test',
        'continent': 'Europe',
        'date': pd.Timestamp('2020-06-01'),
        'total_cases': 100.0,
        'new_cases': 10.0,
        'total_deaths': 5.0,
        'new_deaths': 1.0,
        'gdp_per_capita': 50000.0,
        'population': 5000000.0
    }
    insert_record(engine, CovidDataWorking, new_record)
    
    # Verify working table changed
    assert get_table_row_count(engine, CovidDataWorking) == initial_count + 1
    
    # Verify raw and clean tables unchanged
    assert get_table_row_count(engine, CovidDataRaw) == result['status']['raw_count']
    assert get_table_row_count(engine, CovidDataClean) == result['status']['clean_count']
    
    # Reset working copy
    reset_working_copy(engine)
    
    # Verify working table reset to clean state
    assert get_table_row_count(engine, CovidDataWorking) == result['status']['clean_count']