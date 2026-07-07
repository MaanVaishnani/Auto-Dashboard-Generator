"""
app.py
-------
Streamlit UI for Auto-Dashboard-Generator.

Full pipeline:
    Upload -> profiler.py (profile + clean) -> rule_engine.py (pick charts)
    -> chart_builder.py (build Plotly figures) -> insight_generator.py (AI insights)
    -> rendered dashboard

Run with:
    streamlit run app.py
"""

import os
import tempfile
import streamlit as st

from profiler import profile_and_clean
from Rule_engine import generate_chart_recommendations
from Chart_builder import build_all_charts
from Insight_generator import generate_insights_for_charts


# ---------------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="Auto-Dashboard Generator",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Auto-Dashboard Generator")
st.caption("Upload any CSV or Excel file. The system profiles, cleans, and builds a dashboard "
           "with AI-written insights automatically — no manual chart building required.")


# ---------------------------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------------------------
uploaded_file = st.file_uploader("Upload your CSV or Excel file", type=["csv", "xlsx", "xls"])

if uploaded_file is None:
    st.info("Upload a file above to generate your dashboard.")
    st.stop()


# ---------------------------------------------------------------------
# SAVE UPLOADED FILE TEMPORARILY (profiler.py expects a file path)
# ---------------------------------------------------------------------
file_ext = os.path.splitext(uploaded_file.name)[1]
with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
    tmp_file.write(uploaded_file.getvalue())
    tmp_path = tmp_file.name


# ---------------------------------------------------------------------
# RUN THE PIPELINE (cached so re-renders don't re-run everything)
# ---------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def run_pipeline(file_path: str, file_name: str):
    """
    file_name is passed only so Streamlit's cache key changes when a
    different file is uploaded (file_path alone, being a temp path,
    isn't a reliable cache key across uploads).
    """
    report = profile_and_clean(file_path)
    df_cleaned = report["cleaned_dataframe"]
    column_types = report["column_types"]

    recommendations = generate_chart_recommendations(df_cleaned, column_types)
    charts = build_all_charts(df_cleaned, recommendations)
    charts = generate_insights_for_charts(df_cleaned, charts)

    return report, charts


try:
    with st.spinner("Profiling, cleaning, and analyzing your data..."):
        report, charts = run_pipeline(tmp_path, uploaded_file.name)
except Exception as e:
    st.error(f"Something went wrong while processing your file: {e}")
    st.stop()
finally:
    os.remove(tmp_path)


# ---------------------------------------------------------------------
# SECTION 1: DATA OVERVIEW + CLEANING SUMMARY
# ---------------------------------------------------------------------
st.header("1. Data Overview")

col1, col2, col3 = st.columns(3)
col1.metric("Rows (original)", report["row_count_original"])
col2.metric("Rows (after cleaning)", report["row_count_cleaned"])
col3.metric("Columns", len(report["column_types"]))

with st.expander("🧹 Cleaning summary (what changed)", expanded=True):
    cleaning = report["cleaning_summary"]

    if cleaning["duplicates_removed"] > 0:
        st.write(f"- Removed **{cleaning['duplicates_removed']}** duplicate rows")

    if cleaning["columns_dropped_high_missing"]:
        st.write(f"- Dropped columns with too much missing data: "
                 f"**{', '.join(cleaning['columns_dropped_high_missing'])}**")

    if cleaning["missing_values_filled"]:
        st.write("- Filled missing values:")
        for col, method in cleaning["missing_values_filled"].items():
            st.write(f"   - `{col}` → {method}")

    if cleaning["date_columns_converted"]:
        st.write(f"- Converted to proper date format: **{', '.join(cleaning['date_columns_converted'])}**")

    if not any([cleaning["duplicates_removed"], cleaning["columns_dropped_high_missing"],
                cleaning["missing_values_filled"], cleaning["date_columns_converted"]]):
        st.write("No cleaning was needed — your data was already in good shape.")

with st.expander("🔍 Detected column types"):
    for col, ctype in report["column_types"].items():
        st.write(f"- `{col}` → **{ctype}**")


# ---------------------------------------------------------------------
# SECTION 2: DASHBOARD (CHARTS + AI INSIGHTS)
# ---------------------------------------------------------------------
st.header("2. Dashboard")

if not charts:
    st.warning("No charts could be generated from this dataset. "
               "Try a file with at least one numeric or date column.")
else:
    # Render 2 charts per row for a cleaner layout
    for i in range(0, len(charts), 2):
        row_charts = charts[i:i + 2]
        cols = st.columns(len(row_charts))

        for col, chart in zip(cols, row_charts):
            with col:
                st.plotly_chart(chart["figure"], use_container_width=True)
                st.info(f"💡 {chart['insight']}")


# ---------------------------------------------------------------------
# SECTION 3: EXPORT (placeholder for Step 8)
# ---------------------------------------------------------------------
st.header("3. Export")
st.caption("PDF/PPT export coming in the next step.")