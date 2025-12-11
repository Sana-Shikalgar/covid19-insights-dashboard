import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError
from src.db_engine import get_engine, Base, ExampleTable

@pytest.fixture(scope="module")
def engine():
    """Fixture to create and yield a test database engine."""
    engine = get_engine("sqlite:///:memory")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


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
    assert len(columns) == 3, "Unexpected schema structure"
