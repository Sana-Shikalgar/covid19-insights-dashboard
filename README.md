# WM9QF-Task1-DataInsightsDashboard

A comprehensive Python-based Data Insights Dashboard for analyzing and visualizing public health COVID-19 data. This project provides data loading, cleaning, analysis, and visualization capabilities with a CLI interface.

## Features

- **Data Loading**: Import CSV files and manage data in SQLite databases
- **Data Cleaning**: Normalize dates, handle missing values, and validate data quality
- **Data Analysis**: Aggregate, filter, and analyze COVID-19 health metrics
- **Data Visualization**: Generate plots including time trends, correlations, and grouped summaries
- **CLI Dashboard**: Interactive command-line interface for data exploration
- **Database Management**: SQLAlchemy-based ORM with support for raw, cleaned, and working data tables
- **Testing**: Comprehensive test suite with pytest and coverage reporting

## Project Structure

```
src/
├── data_loader.py          # CSV and database import/export operations
├── data_cleaner.py         # Data cleaning and validation
├── data_analyzer.py        # Data analysis and aggregation
├── data_visualization.py   # Matplotlib-based plotting functions
├── db_engine.py            # SQLAlchemy database operations
├── models.py               # SQLAlchemy ORM models
├── pipeline_integration.py # ETL pipeline orchestration
├── helper_data_cleaning.py # Data cleaning utilities
└── logging_conf.py         # Logging configuration

tests/
├── test_data_loader.py
├── test_data_cleaner.py
├── test_data_analyzer.py
├── test_data_visualization.py
├── test_db_engine.py
├── test_pipeline_integration.py
└── test_helper_data_cleaning.py

data/
├── raw/                    # Raw data files
├── cleaned/                # Processed clean data
└── sample/                 # Test data
```

## Requirements

See `requirements.txt` for all dependencies. Main packages include:

- **pandas**: Data manipulation and analysis
- **sqlalchemy**: Database ORM
- **matplotlib & seaborn**: Data visualization
- **pytest**: Unit testing

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd WM9QF-Task1-DataInsightsDashboard
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Run the CLI Dashboard

```bash
python cli_dashboard.py
```

### Run Tests

```bash
pytest
```

Generate coverage report:

```bash
pytest --cov=src --cov-report=html
```

## Database

The project uses SQLite database with three main tables:

- **CovidDataRaw**: Raw imported data
- **CovidDataClean**: Cleaned and validated data
- **CovidDataWorking**: Working copy for analysis and manipulation

All table structures are statically defined in `src/models.py`.

## Logging

Application logs are configured in `src/logging_conf.py`. Logs are written to the `logs/` directory with configurable levels.

## Author

5749407
