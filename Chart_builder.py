"""
chart_builder.py
------------------
Visualization module for Auto-Dashboard-Generator.

Takes the prioritized chart recommendation list from rule_engine.py
and the cleaned DataFrame from profiler.py, and generates actual
Plotly figure objects ready to render in Streamlit.

Each recommendation dict looks like:
    {"chart_type": "line", "columns": ["OrderDate", "Sales"], "reason": "...", "priority": 95}

build_all_charts() returns a list of:
    {"figure": <plotly Figure>, "title": str, "reason": str, "chart_type": str}
"""

import pandas as pd
import plotly.express as px


# ---------------------------------------------------------------------
# INDIVIDUAL CHART BUILDERS
# ---------------------------------------------------------------------
def build_histogram(df: pd.DataFrame, col: str):
    fig = px.histogram(df, x=col, title=f"Distribution of {col}")
    fig.update_layout(bargap=0.1)
    return fig


def build_bar_counts(df: pd.DataFrame, col: str):
    """Bar chart of value counts for a single categorical column."""
    counts = df[col].value_counts().reset_index()
    counts.columns = [col, "count"]
    fig = px.bar(counts, x=col, y="count", title=f"Count of records by {col}")
    return fig


def build_bar_grouped(df: pd.DataFrame, cat_col: str, num_col: str):
    """Bar chart of a numeric column aggregated (sum) by a categorical column."""
    grouped = df.groupby(cat_col, as_index=False)[num_col].sum()
    grouped = grouped.sort_values(by=num_col, ascending=False)
    fig = px.bar(grouped, x=cat_col, y=num_col, title=f"Total {num_col} by {cat_col}")
    return fig


def build_line_trend(df: pd.DataFrame, date_col: str, num_col: str):
    """Line chart of a numeric column's trend over a date column (aggregated per date)."""
    trend_df = df[[date_col, num_col]].dropna()
    trend_df = trend_df.groupby(date_col, as_index=False)[num_col].sum()
    trend_df = trend_df.sort_values(by=date_col)
    fig = px.line(trend_df, x=date_col, y=num_col, title=f"Trend of {num_col} over {date_col}", markers=True)
    return fig


def build_scatter(df: pd.DataFrame, col_a: str, col_b: str):
    fig = px.scatter(df, x=col_a, y=col_b, title=f"{col_a} vs {col_b}", trendline=None)
    return fig


# ---------------------------------------------------------------------
# DISPATCH: MAP CHART TYPE -> BUILDER FUNCTION
# ---------------------------------------------------------------------
def build_chart(df: pd.DataFrame, recommendation: dict):
    """
    Takes one recommendation dict and routes it to the correct builder.
    Returns None if the chart can't be built (e.g. missing columns),
    so the caller can skip it instead of crashing the whole dashboard.
    """
    chart_type = recommendation["chart_type"]
    columns = recommendation["columns"]

    # Safety check: make sure all referenced columns still exist in df
    for col in columns:
        if col not in df.columns:
            return None

    try:
        if chart_type == "histogram":
            fig = build_histogram(df, columns[0])
        elif chart_type == "bar":
            fig = build_bar_counts(df, columns[0])
        elif chart_type == "bar_grouped":
            fig = build_bar_grouped(df, columns[0], columns[1])
        elif chart_type == "line":
            fig = build_line_trend(df, columns[0], columns[1])
        elif chart_type == "scatter":
            fig = build_scatter(df, columns[0], columns[1])
        else:
            return None  # unknown chart type, skip safely
    except Exception as e:
        print(f"Warning: failed to build {chart_type} for {columns}: {e}")
        return None

    return {
        "figure": fig,
        "title": fig.layout.title.text,
        "reason": recommendation["reason"],
        "chart_type": chart_type,
        "priority": recommendation["priority"],
    }


# ---------------------------------------------------------------------
# MASTER FUNCTION: BUILD ALL CHARTS FROM RECOMMENDATION LIST
# ---------------------------------------------------------------------
def build_all_charts(df: pd.DataFrame, recommendations: list) -> list:
    """
    Loops through every recommendation, builds the chart, and skips
    (rather than crashes on) any that fail. Order is preserved,
    so charts stay in priority order.
    """
    charts = []
    for rec in recommendations:
        built = build_chart(df, rec)
        if built is not None:
            charts.append(built)
    return charts


# ---------------------------------------------------------------------
# STANDALONE TEST BLOCK
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from profiler import profile_and_clean
    from Rule_engine import generate_chart_recommendations

    for test_file in ["HR Analytics Data.csv"]:
        print(f"\n===== {test_file} =====")
        report = profile_and_clean(test_file)
        df_cleaned = report["cleaned_dataframe"]
        column_types = report["column_types"]

        recommendations = generate_chart_recommendations(df_cleaned, column_types)
        charts = build_all_charts(df_cleaned, recommendations)

        print(f"Recommendations: {len(recommendations)} | Charts successfully built: {len(charts)}")
        for c in charts:
            print(f"  - [{c['chart_type']}] {c['title']}  (priority={c['priority']})")