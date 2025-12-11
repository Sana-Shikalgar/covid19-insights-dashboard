import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, IntegrityError
from src.db_engine import (
    get_engine,
    Base,
    ExampleTable,
    insert_record,
    get_session,
    get_record_by_id
)


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
    record_id = insert_record(session.bind, iso_code="Test Patient", value=98.6)
    
    # Assert: Verify using helper function
    saved_record = get_record_by_id(session.bind, record_id)
    assert saved_record is not None
    assert saved_record.iso_code == "Test Patient"
    assert saved_record.value == 98.6
    assert saved_record.id == record_id


def test_create_single_record_id_autoincrement(session):
    """Test that the primary key auto-increments correctly."""
    # Arrange & Act: Insert first record
    record_id1 = insert_record(session.bind, iso_code="Patient 1", value=98.6)
    
    # Act: Insert second record
    record_id2 = insert_record(session.bind, iso_code="Patient 2", value=98.0)
    
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
        database.insert_record(engine, iso_code="Test", value=98.6)



def test_insert_record_duplicate_name_raises_integrity_error(engine):
    """Test duplicate name violation (assumes unique constraint on name)."""
    # First insert succeeds
    insert_record(engine, iso_code="DuplicateTest", value=1.0)
    
    # Second insert should fail (if you add unique=True to name column)
    with pytest.raises(IntegrityError):
        insert_record(engine, iso_code="DuplicateTest", value=2.0)



def test_get_record_by_id_session_failure(engine, monkeypatch):
    """Test that session/query failures are properly handled and re-raised."""
    import src.db_engine as database
    
    class FailingSession:
        def query(self, *args):
            raise RuntimeError("Database query failure")
        def rollback(self): pass
        def close(self): pass
    
    def fake_get_session(engine):
        return lambda: FailingSession()
    
    monkeypatch.setattr(database, "get_session", fake_get_session)
    
    with pytest.raises(RuntimeError, match="Database query failure"):
        database.get_record_by_id(engine, record_id=1)
