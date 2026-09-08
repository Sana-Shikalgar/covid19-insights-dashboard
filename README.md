# COVID19 Insights Dashboard

A CLI tool for loading, cleaning, analyzing, and visualizing public health COVID-19
data from [Our World in Data](https://github.com/owid/covid-19-data). It runs the raw
dataset through an ETL pipeline into a local SQLite database (raw → cleaned → working
copies), then lets you explore it interactively: view summaries, filter and export
records, edit rows, and generate grouped-summary, time-trend, and correlation plots.

## What it does

- **Loads** a CSV of COVID-19 records into SQLite (`src/data_loader.py`, `src/db_engine.py`)
- **Cleans** it — normalizes dates, imputes missing continent/GDP values, drops unusable
  rows (`src/data_cleaner.py`, `src/helper_data_cleaning.py`)
- **Analyzes** it — grouped summaries and time trends (`src/data_analyzer.py`)
- **Visualizes** it — bar charts, time-series lines, and a correlation heatmap, saved to
  `plots/` (`src/data_visualization.py`)
- **Serves** all of the above through an interactive menu-driven CLI (`cli_dashboard.py`)

## Getting Started

1. Clone the repository and `cd` into it:

   ```bash
   git clone <repository-url>
   cd covid19-insights-dashboard
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run it:

   ```bash
   python cli_dashboard.py
   ```

   On first run this loads the bundled dataset, cleans it, and populates the local
   SQLite database (`database/health_data.db`) before dropping you into the menu:

   ```
   --- Public Health Data Insights CLI ---
   1. View summary
   2. Filter data and fetch
   3. Export CSV
   4. Generate plots
   5. Reset working table
   6. Insert one record
   7. Update record
   8. Delete record
   9. Read records (limit)
   10. Show row count
   0. Exit
   ```

### Dataset

Only a 15K-row subset of `data/raw/owid-covid-data.csv` ships in the repo (Git LFS size
limits). To use the full dataset, download the CSV from
[OWID's repository](https://github.com/owid/covid-19-data/blob/master/public/data/owid-covid-data.csv)
and replace `data/raw/owid-covid-data.csv` with it — that's the path
`PipelineConfig.RAW_CSV_PATH` (`src/pipeline_integration.py`) reads by default.

`data_inspection/` holds the exploratory analysis behind the pipeline's design: the
notebooks and spreadsheet used to profile the source columns for data quality and decide
which fields the cleaning pipeline keeps. It documents *why* the pipeline works with the
columns it does — it isn't imported or executed by the application itself.

## Running Tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=src --cov-report=html
```

`pytest.ini` runs the suite with a `logs/app.log` capture by default.

## Database

SQLite, with three tables defined in `src/models.py`:

- **CovidDataRaw**: data as loaded from the CSV
- **CovidDataClean**: cleaned and validated data
- **CovidDataWorking**: a working copy for analysis, edits, and resets

## Logging

Application logs are configured in `src/logging_conf.py` and written to `logs/`.
