# """
# app.py
# -------
# Streamlit UI for Auto-Dashboard-Generator.

# Full pipeline:
#     Upload -> profiler.py (profile + clean) -> rule_engine.py (pick charts)
#     -> chart_builder.py (build Plotly figures) -> insight_generator.py (AI insights)
#     -> rendered dashboard

# Run with:
#     streamlit run app.py
# """

# import os
# import tempfile
# import streamlit as st

# from profiler import profile_and_clean
# from Rule_engine import generate_chart_recommendations
# from Chart_builder import build_all_charts
# from Insight_generator import generate_insights_for_charts


# # ---------------------------------------------------------------------
# # PAGE CONFIG
# # ---------------------------------------------------------------------
# st.set_page_config(
#     page_title="Auto-Dashboard Generator",
#     page_icon="📊",
#     layout="wide",
# )

# st.title("📊 Auto-Dashboard Generator")
# st.caption("Upload any CSV or Excel file. The system profiles, cleans, and builds a dashboard "
#            "with AI-written insights automatically — no manual chart building required.")


# # ---------------------------------------------------------------------
# # FILE UPLOAD
# # ---------------------------------------------------------------------
# uploaded_file = st.file_uploader("Upload your CSV or Excel file", type=["csv", "xlsx", "xls"])

# if uploaded_file is None:
#     st.info("Upload a file above to generate your dashboard.")
#     st.stop()


# # ---------------------------------------------------------------------
# # SAVE UPLOADED FILE TEMPORARILY (profiler.py expects a file path)
# # ---------------------------------------------------------------------
# file_ext = os.path.splitext(uploaded_file.name)[1]
# with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
#     tmp_file.write(uploaded_file.getvalue())
#     tmp_path = tmp_file.name


# # ---------------------------------------------------------------------
# # RUN THE PIPELINE (cached so re-renders don't re-run everything)
# # ---------------------------------------------------------------------
# @st.cache_data(show_spinner=False)
# def run_pipeline(file_path: str, file_name: str):
#     """
#     file_name is passed only so Streamlit's cache key changes when a
#     different file is uploaded (file_path alone, being a temp path,
#     isn't a reliable cache key across uploads).
#     """
#     report = profile_and_clean(file_path)
#     df_cleaned = report["cleaned_dataframe"]
#     column_types = report["column_types"]

#     recommendations = generate_chart_recommendations(df_cleaned, column_types)
#     charts = build_all_charts(df_cleaned, recommendations)
#     charts = generate_insights_for_charts(df_cleaned, charts)

#     return report, charts


# try:
#     with st.spinner("Profiling, cleaning, and analyzing your data..."):
#         report, charts = run_pipeline(tmp_path, uploaded_file.name)
# except Exception as e:
#     st.error(f"Something went wrong while processing your file: {e}")
#     st.stop()
# finally:
#     os.remove(tmp_path)


# # ---------------------------------------------------------------------
# # SECTION 1: DATA OVERVIEW + CLEANING SUMMARY
# # ---------------------------------------------------------------------
# st.header("1. Data Overview")

# col1, col2, col3 = st.columns(3)
# col1.metric("Rows (original)", report["row_count_original"])
# col2.metric("Rows (after cleaning)", report["row_count_cleaned"])
# col3.metric("Columns", len(report["column_types"]))

# with st.expander("🧹 Cleaning summary (what changed)", expanded=True):
#     cleaning = report["cleaning_summary"]

#     if cleaning["duplicates_removed"] > 0:
#         st.write(f"- Removed **{cleaning['duplicates_removed']}** duplicate rows")

#     if cleaning["columns_dropped_high_missing"]:
#         st.write(f"- Dropped columns with too much missing data: "
#                  f"**{', '.join(cleaning['columns_dropped_high_missing'])}**")

#     if cleaning["missing_values_filled"]:
#         st.write("- Filled missing values:")
#         for col, method in cleaning["missing_values_filled"].items():
#             st.write(f"   - `{col}` → {method}")

#     if cleaning["date_columns_converted"]:
#         st.write(f"- Converted to proper date format: **{', '.join(cleaning['date_columns_converted'])}**")

#     if not any([cleaning["duplicates_removed"], cleaning["columns_dropped_high_missing"],
#                 cleaning["missing_values_filled"], cleaning["date_columns_converted"]]):
#         st.write("No cleaning was needed — your data was already in good shape.")

# with st.expander("🔍 Detected column types"):
#     for col, ctype in report["column_types"].items():
#         st.write(f"- `{col}` → **{ctype}**")


# # ---------------------------------------------------------------------
# # SECTION 2: DASHBOARD (CHARTS + AI INSIGHTS)
# # ---------------------------------------------------------------------
# st.header("2. Dashboard")

# if not charts:
#     st.warning("No charts could be generated from this dataset. "
#                "Try a file with at least one numeric or date column.")
# else:
#     # Render 2 charts per row for a cleaner layout
#     for i in range(0, len(charts), 2):
#         row_charts = charts[i:i + 2]
#         cols = st.columns(len(row_charts))

#         for col, chart in zip(cols, row_charts):
#             with col:
#                 st.plotly_chart(chart["figure"], use_container_width=True)
#                 st.info(f"💡 {chart['insight']}")


# # ---------------------------------------------------------------------
# # SECTION 3: EXPORT (placeholder for Step 8)
# # ---------------------------------------------------------------------
# st.header("3. Export")
# st.caption("PDF/PPT export coming in the next step.")




"""
app.py
-------
Streamlit UI for Auto-Dashboard-Generator.

Full pipeline:
    Upload -> profiler.py (profile + clean) -> rule_engine.py (pick charts)
    -> chart_builder.py (build Plotly figures) -> insight_generator.py (AI insights)
    -> rendered dashboard (with KPI cards + sidebar filters)

Run with:
    streamlit run app.py
"""

import os
import tempfile
import pandas as pd
import streamlit as st

from profiler import profile_and_clean
from Rule_engine import (
    generate_chart_recommendations,
    identify_excluded_columns,
    score_numeric_column,
)
from Chart_builder import build_all_charts
from Insight_generator import generate_insights_for_charts


# =======================================================================
# PAGE CONFIG + THEME (dark navy / teal, matches portfolio branding)
# =======================================================================
st.set_page_config(
    page_title="Auto-Dashboard Generator",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
    .stApp { background-color: #0b1220; }

    h1, h2, h3 { color: #e6edf3; }
    p, span, label { color: #b8c2cc; }

    /* KPI card */
    .kpi-card {
        background: linear-gradient(155deg, #101a2c 0%, #0d1626 100%);
        border: 1px solid #1f2f47;
        border-radius: 14px;
        padding: 18px 20px;
        text-align: left;
    }
    .kpi-label {
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #6b7f94;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 26px;
        font-weight: 700;
        color: #2dd4bf;
    }

    /* Section headers */
    .section-title {
        font-size: 20px;
        font-weight: 700;
        color: #e6edf3;
        margin-top: 6px;
        margin-bottom: 14px;
        border-left: 4px solid #2dd4bf;
        padding-left: 10px;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #0f1a2c;
        border: 1px solid #1f2f47 !important;
        border-radius: 14px;
    }

    section[data-testid="stSidebar"] {
        background-color: #0d1626;
        border-right: 1px solid #1f2f47;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Auto-Dashboard Generator")
st.caption("Upload any CSV or Excel file. The system profiles, cleans, and builds a full "
           "BI-style dashboard with KPIs, filters, and AI-written insights — automatically.")


# =======================================================================
# FILE UPLOAD
# =======================================================================
uploaded_file = st.file_uploader("Upload your CSV or Excel file", type=["csv", "xlsx", "xls"])

if uploaded_file is None:
    st.info("Upload a file above to generate your dashboard.")
    st.stop()

file_ext = os.path.splitext(uploaded_file.name)[1]
with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
    tmp_file.write(uploaded_file.getvalue())
    tmp_path = tmp_file.name


# =======================================================================
# RUN THE HEAVY PIPELINE ONCE (cached) - cleaning + AI insights are
# expensive/API-based, so they run on the FULL cleaned dataset only once.
# Filters below only affect what's plotted, not what's sent to the LLM -
# this keeps the app fast and avoids re-calling the Groq API on every
# filter click (Streamlit reruns the whole script on every widget change).
# =======================================================================
@st.cache_data(show_spinner=False)
def run_pipeline(file_path: str, file_name: str):
    report = profile_and_clean(file_path)
    df_cleaned = report["cleaned_dataframe"]
    column_types = report["column_types"]

    recommendations = generate_chart_recommendations(df_cleaned, column_types)
    charts = build_all_charts(df_cleaned, recommendations)
    charts = generate_insights_for_charts(df_cleaned, charts)

    return report, charts


try:
    with st.spinner("Profiling, cleaning, and analyzing your data..."):
        report, base_charts = run_pipeline(tmp_path, uploaded_file.name)
except Exception as e:
    st.error(f"Something went wrong while processing your file: {e}")
    st.stop()
finally:
    os.remove(tmp_path)

df_cleaned = report["cleaned_dataframe"]
column_types = report["column_types"]
excluded_cols = identify_excluded_columns(df_cleaned, column_types)


# =======================================================================
# SIDEBAR: SLICERS / FILTERS
# =======================================================================
st.sidebar.header("🔍 Filters")

date_cols = [c for c, t in column_types.items() if t == "date"]
categorical_cols = [c for c, t in column_types.items() if t == "categorical" and c not in excluded_cols]

df_filtered = df_cleaned.copy()

# --- Date range filter (uses the first detected date column, if any) ---
if date_cols:
    date_col = date_cols[0]
    valid_dates = df_cleaned[date_col].dropna()
    if not valid_dates.empty:
        min_date, max_date = valid_dates.min().date(), valid_dates.max().date()
        st.sidebar.caption(f"Date range ({date_col})")
        selected_range = st.sidebar.date_input(
            "Select range", value=(min_date, max_date),
            min_value=min_date, max_value=max_date, label_visibility="collapsed"
        )
        if isinstance(selected_range, tuple) and len(selected_range) == 2:
            start, end = selected_range
            df_filtered = df_filtered[
                (df_filtered[date_col].dt.date >= start) & (df_filtered[date_col].dt.date <= end)
            ]

# --- Categorical dropdown filters ---
for col in categorical_cols:
    options = sorted(df_cleaned[col].dropna().unique().tolist())
    if len(options) < 2:
        continue  # not useful as a filter if there's only one value
    selected = st.sidebar.multiselect(col, options, default=options)
    if selected:  # if user clears all, treat as "no filter" instead of showing nothing
        df_filtered = df_filtered[df_filtered[col].isin(selected)]

st.sidebar.divider()
st.sidebar.caption(f"Showing **{len(df_filtered)}** of **{len(df_cleaned)}** rows after filters")


# =======================================================================
# SECTION 1: KPI CARDS
# =======================================================================
st.markdown('<div class="section-title">Key Metrics</div>', unsafe_allow_html=True)

numeric_cols = [c for c, t in column_types.items() if t == "numeric" and c not in excluded_cols]
top_numeric_cols = sorted(numeric_cols, key=lambda c: score_numeric_column(c, df_cleaned), reverse=True)[:3]

kpi_cols = st.columns(len(top_numeric_cols) + 1)

with kpi_cols[0]:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Total Records</div>
        <div class="kpi-value">{len(df_filtered):,}</div>
    </div>
    """, unsafe_allow_html=True)

for i, col in enumerate(top_numeric_cols):
    total = df_filtered[col].sum()
    display_val = f"{total:,.0f}" if abs(total) >= 1000 else f"{total:,.2f}"
    with kpi_cols[i + 1]:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Total {col}</div>
            <div class="kpi-value">{display_val}</div>
        </div>
        """, unsafe_allow_html=True)

st.write("")


# =======================================================================
# SECTION 2: DATA OVERVIEW (collapsed by default, less visual clutter)
# =======================================================================
with st.expander("🧹 Data cleaning summary & detected column types"):
    cleaning = report["cleaning_summary"]
    col_a, col_b = st.columns(2)

    with col_a:
        st.write("**Cleaning actions:**")
        if cleaning["duplicates_removed"] > 0:
            st.write(f"- Removed **{cleaning['duplicates_removed']}** duplicate rows")
        if cleaning["columns_dropped_high_missing"]:
            st.write(f"- Dropped columns with too much missing data: "
                     f"**{', '.join(cleaning['columns_dropped_high_missing'])}**")
        if cleaning["missing_values_filled"]:
            for col, method in cleaning["missing_values_filled"].items():
                st.write(f"- `{col}` → {method}")
        if cleaning["date_columns_converted"]:
            st.write(f"- Converted to proper date format: **{', '.join(cleaning['date_columns_converted'])}**")
        if not any(cleaning.values()):
            st.write("No cleaning was needed — data was already in good shape.")

    with col_b:
        st.write("**Detected column types:**")
        for col, ctype in column_types.items():
            st.write(f"- `{col}` → **{ctype}**")


# =======================================================================
# SECTION 3: DASHBOARD (CHARTS + AI INSIGHTS, RE-COMPUTED ON FILTERED DATA)
# =======================================================================
st.markdown('<div class="section-title">Dashboard</div>', unsafe_allow_html=True)

if df_filtered.empty:
    st.warning("No data matches the current filters. Try widening your filter selection.")
    st.stop()

# Charts are rebuilt on the FILTERED data (fast - no API calls here).
filtered_recommendations = generate_chart_recommendations(df_filtered, column_types)
filtered_charts = build_all_charts(df_filtered, filtered_recommendations)

# Match each filtered chart back to its AI insight from the original
# (unfiltered) run by title, so we don't re-call the Groq API on every
# filter interaction. If a chart is new to this filter view, show a note
# instead of a stale/misleading insight.
insight_lookup = {c["title"]: c["insight"] for c in base_charts}

if not filtered_charts:
    st.warning("No charts could be generated from this data. Try a file with at least one numeric or date column.")
else:
    for i in range(0, len(filtered_charts), 2):
        row_charts = filtered_charts[i:i + 2]
        cols = st.columns(len(row_charts))

        for col, chart in zip(cols, row_charts):
            with col:
                with st.container(border=True):
                    st.plotly_chart(chart["figure"], use_container_width=True)
                    insight_text = insight_lookup.get(
                        chart["title"],
                        "Insight reflects the full dataset and may shift slightly with your current filters."
                    )
                    st.info(f"💡 {insight_text}")


# =======================================================================
# SECTION 4: EXPORT (placeholder for Step 8)
# =======================================================================
st.markdown('<div class="section-title">Export</div>', unsafe_allow_html=True)
st.caption("PDF/PPT export coming in the next step.")