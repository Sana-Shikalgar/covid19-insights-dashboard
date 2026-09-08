"""
Data visualization module for COVID-19 health dashboard.
Creates matplotlib figures for the CLI dashboard.
"""

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from typing import Optional, List
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Configure matplotlib style
plt.style.use('default')
sns.set_palette("husl")


# ==================== GROUPED SUMMARY VISUALIZATION ====================

def plot_grouped_summary(
    grouped_df: pd.DataFrame,
    group_col: str,
    value_col: str,
    top_n: int = 10
) -> plt.Figure:
    """
    Create grouped bar chart from grouped summary data.
    
    Displays top N groups by mean value with statistics overlay.
    
    Args:
        grouped_df: Output from generate_grouped_summary()
        group_col: Column used for grouping (e.g., 'iso_code', 'continent')
        value_col: Numeric column for Y-axis (e.g., 'gdp_per_capita_mean')
        top_n: Number of top groups to display
    
    Returns:
        Matplotlib Figure object for rendering
    """
    # Handle empty data
    if grouped_df.empty:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'No data available for grouping',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=14, color='gray')
        ax.set_title(f"No Data: {group_col} vs {value_col}")
        ax.axis('off')
        plt.tight_layout()
        logger.warning("Empty DataFrame provided to plot_grouped_summary")
        return fig
    
    # Select top N groups by value
    top_groups = grouped_df.nlargest(top_n, value_col)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Create bars
    x_pos = np.arange(len(top_groups))
    bars = ax.bar(x_pos, top_groups[value_col].values,
                  color='steelblue', alpha=0.8, edgecolor='navy', linewidth=1.5)
    
    # Add value labels on bars
    for i, (bar, val) in enumerate(zip(bars, top_groups[value_col])):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                f'{val:.1f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # Customize axes
    ax.set_xlabel(group_col.replace('_', ' ').title(), fontsize=12, fontweight='bold')
    ax.set_ylabel(value_col.replace('_', ' ').title(), fontsize=12, fontweight='bold')
    ax.set_title(f'Top {top_n} {value_col.replace("_", " ").title()} by {group_col.replace("_", " ").title()}',
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(top_groups[group_col], rotation=45, ha='right')
    
    # Add mean line
    mean_val = top_groups[value_col].mean()
    ax.axhline(y=mean_val, color='red', linestyle='--', alpha=0.7,
               linewidth=2, label=f'Mean: {mean_val:.2f}')
    
    # Add grid and legend
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.legend(loc='upper right', framealpha=0.9)
    
    plt.tight_layout()
    logger.info(f"Generated grouped summary plot: {group_col} vs {value_col}")
    return fig


# ==================== TIME TREND VISUALIZATION ====================

def plot_time_trend(
    trend_df: pd.DataFrame,
    time_col: str,
    value_col: str,
    group_col: Optional[str] = None
) -> plt.Figure:
    """
    Create time series line plot from time trend data.
    
    Supports both single-line and multi-line (grouped) trends.
    
    Args:
        trend_df: Output from generate_time_trend()
        time_col: Date/time column name
        value_col: Numeric value column name
        group_col: Optional grouping column for multiple lines
    
    Returns:
        Matplotlib Figure object for rendering
    """
    # Handle empty data
    if trend_df.empty:
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.text(0.5, 0.5, 'No time trend data available',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=14, color='gray')
        ax.set_title(f"No Time Data: {value_col} over {time_col}")
        ax.axis('off')
        plt.tight_layout()
        logger.warning("Empty DataFrame provided to plot_time_trend")
        return fig
    
    # Create figure
    fig, ax = plt.subplots(figsize=(14, 7))
    
    # Plot multiple lines if grouped
    if group_col and group_col in trend_df.columns:
        for name, group_data in trend_df.groupby(group_col):
            ax.plot(group_data[time_col], group_data[value_col],
                   marker='o', linewidth=2.5, label=str(name),
                   markersize=4, alpha=0.8)
        ax.legend(title=group_col.replace('_', ' ').title(),
                 bbox_to_anchor=(1.05, 1), loc='upper left',
                 framealpha=0.9)
    
    # Plot single line
    else:
        ax.plot(trend_df[time_col], trend_df[value_col],
               linewidth=3, color='darkblue', marker='o',
               markersize=5, alpha=0.8, label=value_col.replace('_', ' ').title())
    
    # Customize axes
    ax.set_xlabel(time_col.replace('_', ' ').title(), fontsize=12, fontweight='bold')
    ax.set_ylabel(value_col.replace('_', ' ').title(), fontsize=12, fontweight='bold')
    ax.set_title(f'{value_col.replace("_", " ").title()} Trend over {time_col.replace("_", " ").title()}',
                 fontsize=14, fontweight='bold', pad=20)
    
    # Format date axis if applicable
    if pd.api.types.is_datetime64_any_dtype(trend_df[time_col]):
        ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Add summary statistics
    mean_val = trend_df[value_col].mean()
    min_val = trend_df[value_col].min()
    max_val = trend_df[value_col].max()
    
    ax.axhline(y=mean_val, color='green', linestyle='--', alpha=0.7,
               linewidth=2, label=f'Mean: {mean_val:.2f}')
    
    # Add stats box
    stats_text = f'Min: {min_val:.2f} | Max: {max_val:.2f} | Range: {max_val - min_val:.2f}'
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            va='top', ha='left', fontsize=10,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    # Add grid
    ax.grid(True, alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    logger.info(f"Generated time trend plot: {value_col} over {time_col}")
    return fig


# ==================== SUMMARY DISTRIBUTION VISUALIZATION ====================

def plot_summary_distribution(
    df: pd.DataFrame,
    columns: List[str],
    bins: int = 30
) -> plt.Figure:
    """
    Create distribution histograms for multiple numeric columns.
    
    Displays side-by-side histograms with mean indicators.
    
    Args:
        df: Input DataFrame
        columns: List of numeric column names to plot
        bins: Number of histogram bins (default: 30)
    
    Returns:
        Matplotlib Figure object for rendering
    """
    # Handle empty data or no columns
    if df.empty or not columns:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'No summary data available',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=14, color='gray')
        ax.set_title("No Data Available for Distribution")
        ax.axis('off')
        plt.tight_layout()
        logger.warning("Empty DataFrame or no columns provided to plot_summary_distribution")
        return fig
    
    # Determine subplot layout
    n_cols = len(columns)
    fig, axes = plt.subplots(1, n_cols, figsize=(5*n_cols, 6))
    
    # Handle single column case
    if n_cols == 1:
        axes = [axes]
    
    # Create histogram for each column
    for i, col in enumerate(columns):
        ax = axes[i]
        
        # Get non-null data
        data = df[col].dropna()
        
        if len(data) == 0:
            ax.text(0.5, 0.5, f'No data for {col}',
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=12, color='gray')
            ax.set_title(col.replace('_', ' ').title())
            continue
        
        # Create histogram
        n, bins_edges, patches = ax.hist(data, bins=bins, alpha=0.7,
                                         color='skyblue', edgecolor='black',
                                         linewidth=1.2)
        
        # Calculate statistics
        mean_val = data.mean()
        median_val = data.median()
        std_val = data.std()
        
        # Add mean line
        ax.axvline(mean_val, color='red', linestyle='--',
                  linewidth=2, label=f'Mean: {mean_val:.2f}')
        
        # Add median line
        ax.axvline(median_val, color='green', linestyle='-.',
                  linewidth=2, label=f'Median: {median_val:.2f}')
        
        # Customize axes
        ax.set_title(col.replace('_', ' ').title(), fontsize=12, fontweight='bold')
        ax.set_xlabel(col.replace('_', ' ').title(), fontsize=10)
        ax.set_ylabel('Frequency', fontsize=10)
        
        # Add statistics box
        stats_text = f'Std: {std_val:.2f}\nCount: {len(data)}'
        ax.text(0.98, 0.98, stats_text, transform=ax.transAxes,
                va='top', ha='right', fontsize=9,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Add legend and grid
        ax.legend(loc='upper right', fontsize=9, framealpha=0.9)
        ax.grid(True, alpha=0.3, linestyle='--')
    
    plt.suptitle('Distribution Analysis', fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    
    logger.info(f"Generated distribution plots for: {', '.join(columns)}")
    return fig


# ==================== CORRELATION HEATMAP (BONUS) ====================

def plot_correlation_heatmap(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    figsize: tuple = (10, 8)
) -> plt.Figure:
    """
    Create correlation heatmap for numeric columns.
    
    NOTE: This is a bonus visualization not required by original spec.
    Useful for exploratory data analysis.
    
    Args:
        df: Input DataFrame
        columns: Columns to include (default: all numeric)
        figsize: Figure size tuple
    
    Returns:
        Matplotlib Figure object for rendering
    """
    # Select numeric columns
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Handle empty data
    if df.empty or not columns:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, 'No data for correlation analysis',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=14, color='gray')
        ax.axis('off')
        plt.tight_layout()
        logger.warning("No data for correlation heatmap")
        return fig
    
    # Calculate correlation matrix
    corr_matrix = df[columns].corr()
    
    # Create heatmap
    fig, ax = plt.subplots(figsize=figsize)
    
    sns.heatmap(corr_matrix, annot=True, fmt='.2f', cmap='coolwarm',
                center=0, square=True, linewidths=1, cbar_kws={"shrink": 0.8},
                ax=ax)
    
    ax.set_title('Correlation Heatmap', fontsize=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    logger.info(f"Generated correlation heatmap for {len(columns)} columns")
    return fig


# ==================== UTILITY FUNCTION ====================

def close_all_figures() -> None:
    """
    Close all matplotlib figures to free memory.
    
    Call this after saving/displaying figures to prevent memory leaks.
    """
    plt.close('all')
    logger.debug("Closed all matplotlib figures")