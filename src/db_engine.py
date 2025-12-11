from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

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
    name = Column(String(100), nullable=False)
    value = Column(Float, nullable=True)


# SQLAlchemy session factory (will be useful later)
def get_session(engine):
    """
    Create a new SQLAlchemy session bound to the given engine.
    """
    Session = sessionmaker(bind=engine)
    return Session()
