import pandas as pd
import matplotlib.pyplot as plt
from src.data_visualization import (
    plot_grouped_summary,
    plot_time_trend,
    plot_summary_distribution,
    plot_correlation_heatmap,
    close_all_figures
)

# Sample test data
df = pd.DataFrame({
    "continent": ["Asia", "Asia", "Europe", "Europe"],
    "date": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-01-01", "2020-02-01"]),
    "new_cases": [100, 200, 150, 300],
    "new_deaths": [5, 10, 7, 15],
    "gdp_per_capita": [3000, 3000, 40000, 40000]
})

# ---- Grouped summary ----
grouped = (
    df.groupby("continent", as_index=False)["new_cases"]
      .mean()
      .rename(columns={"new_cases": "new_cases_mean"})
)

fig1 = plot_grouped_summary(
    grouped_df=grouped,
    group_col="continent",
    value_col="new_cases_mean"
)
# fig1.show()

# ---- Time trend ----
fig2 = plot_time_trend(
    trend_df=df,
    time_col="date",
    value_col="new_cases",
    group_col="continent"
)
# fig2.show()

# ---- Distribution ----
fig3 = plot_summary_distribution(
    df=df,
    columns=["new_cases", "new_deaths"]
)
# fig3.show()

# ---- Correlation heatmap ----
fig4 = plot_correlation_heatmap(df)
# fig4.show()

# close_all_figures()
plt.show() 