"""
Database ORM models for COVID-19 health data pipeline.

Architecture:
- RAW LAYER: Immutable ingestion tables (nullable fields)
- CLEAN LAYER: Validated reference tables (non-nullable fields)
- WORKING LAYER: Mutable operational tables (mirrors clean schema)
- TEST LAYER: Test fixtures and sample tables
"""

from sqlalchemy import Column, Integer, String, Float, Date
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# ==================== RAW LAYER (IMMUTABLE) ====================

class CovidDataRaw(Base):
    """
    Raw COVID-19 dataset ingested directly from CSV source.
    
    Characteristics:
    - All fields nullable (preserves original data as-is)
    - Never modified after initial ingestion
    - Serves as immutable audit trail
    - Full 67-field schema from Our World in Data
    """
    __tablename__ = "covid_data_raw"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Core identifiers
    iso_code = Column(String(10), nullable=True, index=True)
    continent = Column(String(50), nullable=True)
    location = Column(String(100), nullable=True, index=True)
    date = Column(Date, nullable=True, index=True)

    # Case metrics
    total_cases = Column(Float, nullable=True)
    new_cases = Column(Float, nullable=True)
    new_cases_smoothed = Column(Float, nullable=True)
    total_cases_per_million = Column(Float, nullable=True)
    new_cases_per_million = Column(Float, nullable=True)
    new_cases_smoothed_per_million = Column(Float, nullable=True)

    # Death metrics
    total_deaths = Column(Float, nullable=True)
    new_deaths = Column(Float, nullable=True)
    new_deaths_smoothed = Column(Float, nullable=True)
    total_deaths_per_million = Column(Float, nullable=True)
    new_deaths_per_million = Column(Float, nullable=True)
    new_deaths_smoothed_per_million = Column(Float, nullable=True)

    # Transmission
    reproduction_rate = Column(Float, nullable=True)

    # Hospital & ICU
    icu_patients = Column(Float, nullable=True)
    icu_patients_per_million = Column(Float, nullable=True)
    hosp_patients = Column(Float, nullable=True)
    hosp_patients_per_million = Column(Float, nullable=True)
    weekly_icu_admissions = Column(Float, nullable=True)
    weekly_icu_admissions_per_million = Column(Float, nullable=True)
    weekly_hosp_admissions = Column(Float, nullable=True)
    weekly_hosp_admissions_per_million = Column(Float, nullable=True)

    # Testing
    total_tests = Column(Float, nullable=True)
    new_tests = Column(Float, nullable=True)
    total_tests_per_thousand = Column(Float, nullable=True)
    new_tests_per_thousand = Column(Float, nullable=True)
    new_tests_smoothed = Column(Float, nullable=True)
    new_tests_smoothed_per_thousand = Column(Float, nullable=True)
    positive_rate = Column(Float, nullable=True)
    tests_per_case = Column(Float, nullable=True)
    tests_units = Column(String(50), nullable=True)

    # Vaccination
    total_vaccinations = Column(Float, nullable=True)
    people_vaccinated = Column(Float, nullable=True)
    people_fully_vaccinated = Column(Float, nullable=True)
    total_boosters = Column(Float, nullable=True)
    new_vaccinations = Column(Float, nullable=True)
    new_vaccinations_smoothed = Column(Float, nullable=True)
    total_vaccinations_per_hundred = Column(Float, nullable=True)
    people_vaccinated_per_hundred = Column(Float, nullable=True)
    people_fully_vaccinated_per_hundred = Column(Float, nullable=True)
    total_boosters_per_hundred = Column(Float, nullable=True)
    new_vaccinations_smoothed_per_million = Column(Float, nullable=True)
    new_people_vaccinated_smoothed = Column(Float, nullable=True)
    new_people_vaccinated_smoothed_per_hundred = Column(Float, nullable=True)

    # Policy
    stringency_index = Column(Float, nullable=True)

    # Demographics
    population_density = Column(Float, nullable=True)
    median_age = Column(Float, nullable=True)
    aged_65_older = Column(Float, nullable=True)
    aged_70_older = Column(Float, nullable=True)

    # Economics
    gdp_per_capita = Column(Float, nullable=True)
    extreme_poverty = Column(Float, nullable=True)

    # Health indicators
    cardiovasc_death_rate = Column(Float, nullable=True)
    diabetes_prevalence = Column(Float, nullable=True)
    female_smokers = Column(Float, nullable=True)
    male_smokers = Column(Float, nullable=True)
    handwashing_facilities = Column(Float, nullable=True)
    hospital_beds_per_thousand = Column(Float, nullable=True)
    life_expectancy = Column(Float, nullable=True)
    human_development_index = Column(Float, nullable=True)

    # Population
    population = Column(Float, nullable=True)

    # Excess mortality
    excess_mortality_cumulative_absolute = Column(Float, nullable=True)
    excess_mortality_cumulative = Column(Float, nullable=True)
    excess_mortality = Column(Float, nullable=True)
    excess_mortality_cumulative_per_million = Column(Float, nullable=True)

    def __repr__(self):
        return f"<CovidDataRaw(id={self.id}, location={self.location}, date={self.date})>"


# ==================== CLEAN LAYER (IMMUTABLE REFERENCE) ====================

class CovidDataClean(Base):
    """
    Cleaned and validated COVID-19 reference dataset.
    
    Characteristics:
    - All fields NON-NULLABLE (validated, complete data)
    - Never modified after creation
    - Serves as authoritative source of truth
    - Core 10-field schema for essential metrics
    """
    __tablename__ = "covid_data_clean"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Core identifiers (NON-NULL)
    iso_code = Column(String(10), nullable=False, index=True)
    location = Column(String(100), nullable=False, index=True)
    continent = Column(String(50), nullable=False, index=True)
    
    # Date (NON-NULL)
    date = Column(Date, nullable=False, index=True)
    
    # Core COVID metrics (NON-NULL - validated during cleaning)
    total_cases = Column(Float, nullable=False)
    new_cases = Column(Float, nullable=False)
    total_deaths = Column(Float, nullable=False)
    new_deaths = Column(Float, nullable=False)
    
    # Demographic data (NON-NULL - imputed during cleaning)
    gdp_per_capita = Column(Float, nullable=False)
    population = Column(Float, nullable=False)
    
    def __repr__(self):
        return f"<CovidDataClean(id={self.id}, location={self.location}, date={self.date})>"
    
    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            'id': self.id,
            'iso_code': self.iso_code,
            'location': self.location,
            'continent': self.continent,
            'date': self.date.isoformat() if self.date else None,
            'total_cases': self.total_cases,
            'new_cases': self.new_cases,
            'total_deaths': self.total_deaths,
            'new_deaths': self.new_deaths,
            'gdp_per_capita': self.gdp_per_capita,
            'population': self.population
        }


# ==================== WORKING LAYER (MUTABLE OPERATIONAL) ====================

class CovidDataWorking(Base):
    """
    Working copy of COVID-19 data for CRUD operations.
    
    Characteristics:
    - Identical schema to CovidDataClean
    - All fields NON-NULLABLE (preserves data integrity)
    - ONLY table where user modifications are permitted
    - Can be reset from CovidDataClean at any time
    """
    __tablename__ = "covid_data_working"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Core identifiers (NON-NULL)
    iso_code = Column(String(10), nullable=False, index=True)
    location = Column(String(100), nullable=False, index=True)
    continent = Column(String(50), nullable=False, index=True)
    
    # Date (NON-NULL)
    date = Column(Date, nullable=False, index=True)
    
    # Core COVID metrics (NON-NULL)
    total_cases = Column(Float, nullable=False)
    new_cases = Column(Float, nullable=False)
    total_deaths = Column(Float, nullable=False)
    new_deaths = Column(Float, nullable=False)
    
    # Demographic data (NON-NULL)
    gdp_per_capita = Column(Float, nullable=False)
    population = Column(Float, nullable=False)
    
    def __repr__(self):
        return f"<CovidDataWorking(id={self.id}, location={self.location}, date={self.date})>"
    
    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            'id': self.id,
            'iso_code': self.iso_code,
            'location': self.location,
            'continent': self.continent,
            'date': self.date.isoformat() if self.date else None,
            'total_cases': self.total_cases,
            'new_cases': self.new_cases,
            'total_deaths': self.total_deaths,
            'new_deaths': self.new_deaths,
            'gdp_per_capita': self.gdp_per_capita,
            'population': self.population
        }


# ==================== TEST LAYER ====================

class ExampleTable(Base):
    """
    Example table for CRUD testing and validation.
    Simple 4-field structure for unit tests.
    """
    __tablename__ = "example_table"

    id = Column(Integer, primary_key=True, autoincrement=True)
    iso_code = Column(String(100), nullable=False, unique=True)
    value = Column(Float, nullable=True)
    country = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<ExampleTable(id={self.id}, iso_code={self.iso_code})>"


class SampleTable(Base):
    """
    Sample schema for integration testing.
    Mirrors core COVID structure for test scenarios.
    """
    __tablename__ = "sample_table"

    id = Column(Integer, primary_key=True, autoincrement=True)
    iso_code = Column(String(10), nullable=False)
    location = Column(String(100), nullable=True)
    continent = Column(String(50), nullable=True)
    date = Column(Date, nullable=True)
    total_cases = Column(Float, nullable=True)
    new_cases = Column(Float, nullable=True)
    total_deaths = Column(Float, nullable=True)
    new_deaths = Column(Float, nullable=True)
    gdp_per_capita = Column(Float, nullable=True)
    population = Column(Float, nullable=True)

    def __repr__(self):
        return f"<SampleTable(id={self.id}, iso_code={self.iso_code})>"
    

# ==================== HELPER FUNCTIONS ====================

def get_model_by_layer(layer: str):
    """
    Get model class by layer name.
    
    Args:
        layer: 'raw', 'clean', or 'working'
    
    Returns:
        Corresponding model class
    
    Raises:
        ValueError: If invalid layer name
    """
    layers = {
        'raw': CovidDataRaw,
        'clean': CovidDataClean,
        'working': CovidDataWorking
    }
    
    if layer not in layers:
        raise ValueError(f"Invalid layer '{layer}'. Must be one of: {list(layers.keys())}")
    
    return layers[layer]


def get_core_columns():
    """
    Get list of core column names present in clean/working tables.
    
    Returns:
        List of column names (excluding 'id')
    """
    return [
        'iso_code', 'location', 'continent', 'date',
        'total_cases', 'new_cases', 'total_deaths', 'new_deaths',
        'gdp_per_capita', 'population'
    ]