import sys
import threading
import itertools
import time
import pandas as pd
from sqlalchemy.engine import Engine
from datetime import datetime

from src.pipeline_integration import execute_pipeline, reset_working_copy
from src.data_loader import load_db_to_csv
from src.data_analyzer import run_analysis
from src.logging_conf import log_activity, setup_logging
from src.data_visualization import (
    plot_grouped_summary,
    plot_time_trend,
    plot_correlation_heatmap
)
from src.db_engine import (
    get_engine,
    table_exists,
    get_table_row_count,
    insert_record,
    update_record,
    delete_record,
    filter_by_col_values,
)
from src.models import ( 
    CovidDataRaw as RawTable, 
    CovidDataClean as CleanTable, 
    CovidDataWorking as WorkingTable
)

# ---------------------- Loading ------------------------
def show_loading(message="Loading"):
    stop_event = threading.Event()
    
    def animate():
        for c in itertools.cycle([".", "..", "..."]):
            if stop_event.is_set():
                break
            sys.stdout.write(f"\r{message}{c}   ")
            sys.stdout.flush()
            time.sleep(0.5)
        # Clear the line when done
        sys.stdout.write(f"\r{' ' * (len(message) + 5)}\r")
        sys.stdout.flush()
    
    t = threading.Thread(target=animate, daemon=True)
    t.start()

    def stop():
        stop_event.set()
        t.join()

    return stop

# ----------------------- Helpers -----------------------
def choose_table():
    print("\nSelect table:")
    print("1. Raw")
    print("2. Cleaned")
    print("3. Working")
    choice = input("Enter choice (1-3): ").strip()
    mapping = {"1": RawTable, "2": CleanTable, "3": WorkingTable}
    if choice in mapping:
            return mapping[choice]
    print("Invalid choice. Try again.")


def input_dict(prompt: str) -> dict:
    """Parse key:value input safely with type conversion."""
    text = input(f"{prompt} (key1:value1,key2:value2): ").strip()
    if not text: 
        raise ValueError("record_data cannot be empty")
    
    record = {}
    for pair in [p.strip() for p in text.split(",") if p.strip()]:
        if ":" not in pair: raise ValueError(f"Invalid: {pair}")
        key, value = [x.strip() for x in pair.split(":", 1)]
        print(pair)
        if key == "date":
            record[key] = datetime.strptime(value, "%Y-%m-%d").date()
        elif value.isdigit():
            record[key] = int(value)
        elif value.replace(".", "", 1).isdigit():
            record[key] = float(value)
        else:
            record[key] = value
    print(record)
    return record

# ------------------------ Menu --------------------------
def menu():
    print("\n--- Public Health Data Insights CLI ---")
    print("1. View summary")
    print("2. Filter data and fetch")
    print("3. Export CSV")
    print("4. Generate plots")
    print("5. Reset working table")
    print("6. Insert one record")
    print("7. Update record")
    print("8. Delete record")
    print("9. Read records (limit)")
    print("10. Show row count")
    print("0. Exit")
    return


# ----------------------- CLI Loop -----------------------
@log_activity("User has entered the CLI.")
def run_cli():
    engine: Engine = get_engine()  # Create DB engine
    
    stop_loader = show_loading("Executing pipeline")
    execute_pipeline(engine)       # Ensure pipeline stages executed
    stop_loader()

    menu()

    while True:
        choice = input("\n\nEnter choice (to see the menu again, enter 11): ").strip()
        
        if choice == "0":
            print("Exiting CLI. Goodbye!")
            break
        
        elif choice == "1":
            model = choose_table()
            if model:
                exists = table_exists(engine, model.__tablename__)
                rows = get_table_row_count(engine, model) if exists else 0
                print(f"Table: {model.__tablename__}, Exists: {exists}, Rows: {rows}")
                if exists:
                    df = pd.read_sql_table(model.__tablename__, engine)
                    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                    print("The basic summary of the table:")
                    print(df[numeric_cols].describe())
                    print("\nBasic information about columns:")
                    print(df.info(memory_usage='deep'))

        elif choice == "2":
            model = choose_table()
            if model:
                try:
                    filters = input_dict("Enter filters")
                    results = filter_by_col_values(engine, model, filters)
                    print(pd.DataFrame(results).head())
                except Exception as e:
                    print(f"Error filtering records: {e}")
        
        elif choice == "3":
            model = choose_table()
            if model:
                path = input("Enter CSV file path: ").strip()
                cols = input("Enter columns to export (comma-separated, optional): ").strip()
                cols_list = [c.strip() for c in cols.split(",")] if cols else None
                load_db_to_csv(engine, model, path, cols_list)
                print(f"CSV exported to {path}")
        
        elif choice == "4":
            model = choose_table()
            if model:
                df = pd.read_sql_table(model.__tablename__, engine)
                print("\n\nSelect plot type:")
                print("1. Grouped summary (bar chart by category)")
                print("2. Time trend (line chart over time)")
                print("3. Correlation heatmap (numeric variables)")
                print("4. All plots")
                plot_choice = input("Choice: ").strip()
                print(f'--' * 30)
        
                print(df)
                # Example defaults for non-interactive plotting
                group_col = "continent"       # category
                time_col = "date"
                value_col = "new_cases"       # numeric
                analysis = run_analysis(
                    df,
                    group_by=[group_col],
                    time_column=time_col,
                    value_column=value_col,
                )

                if plot_choice in ["1","4"]:
                    grouped = analysis["grouped_summary"]
                    fig = plot_grouped_summary(grouped, group_col, f"{value_col}_mean")
                    fig.suptitle(f"Grouped Summary: {value_col.replace('_',' ').title()} by {group_col.title()}",
                                fontsize=16, fontweight='bold', y=1.02)
                    fig.show()

                if plot_choice in ["2","4"]:
                    trend = analysis["trend"]
                    fig = plot_time_trend(trend, time_col, value_col)
                    fig.suptitle(f"Time Trend of {value_col.replace('_',' ').title()} over Time",
                                fontsize=16, fontweight='bold', y=1.02)
                    fig.show()
                
                if plot_choice in ["3","4"]:
                    numeric_cols = ["total_cases", "new_cases", "total_deaths", "new_deaths",
                                    "gdp_per_capita", "population"]
                    fig = plot_correlation_heatmap(df[numeric_cols])
                    fig.suptitle("Correlation Heatmap of Core COVID Metrics",
                                fontsize=16, fontweight='bold', y=1.02)
                    fig.show()

        
        elif choice == "5":
            reset_working_copy(engine)
            print("Working table reset from clean reference.")
        
        elif choice == "6":
            model = WorkingTable
            record = input_dict("Enter new record data")
            try:
                insert_record(engine, model, record)
                print("Record inserted successfully.")
            except Exception as e:
                print(f"Error inserting record: {e}")
        
        elif choice == "7":
            model = WorkingTable
            filters = input_dict("Enter filter conditions")
            updates = input_dict("Enter updates")
            try:
                updated_count = update_record(engine, model, filters, updates)
                print(f"{updated_count} record(s) updated.")
            except Exception as e:
                print(f"Error updating record: {e}")
        
        elif choice == "8":
            model = WorkingTable
            filters = input_dict("Enter filter conditions")
            try:
                deleted_count = delete_record(engine, model, filters)
                print(f"{deleted_count} record(s) deleted.")
            except Exception as e:
                print(f"Error deleting record: {e}")
        
        elif choice == "9":
            model = choose_table()
            if model:
                try:
                    limit = int(input("Enter number of records to display: ").strip())
                    df = pd.read_sql_table(model.__tablename__, engine)
                    print(df.head(limit))
                except Exception as e:
                    print(f"Error reading records: {e}")
        
        elif choice == "10":
            model = choose_table()
            if model:
                count = get_table_row_count(engine, model)
                print(f"Table {model.__tablename__} has {count} rows.")
        
        elif choice == "11":
            menu()

        else:
            print("Invalid choice. Try again.")
            menu()

if __name__ == "__main__":
    setup_logging()
    run_cli()
