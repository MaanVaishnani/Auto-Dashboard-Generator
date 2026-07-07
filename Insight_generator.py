"""
insight_generator.py
----------------------
AI Insight Layer for Auto-Dashboard-Generator.

Sits AFTER chart_builder.py in the pipeline:
    profiler.py -> rule_engine.py -> chart_builder.py -> insight_generator.py -> Streamlit UI

For each built chart, this module:
1. Extracts small SUMMARY STATISTICS from the chart's underlying data
   (never sends the full raw dataset - keeps prompts small and avoids
   leaking unnecessary raw data to a third-party API).
2. Sends those summaries to Groq's LLaMA3 model with a tight prompt.
3. Attaches the returned plain-language insight to each chart dict.

Requires a GROQ_API_KEY set in a .env file at the project root:
    GROQ_API_KEY=API_KEY_HERE
"""

import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # reads GROQ_API_KEY from .env into environment variables

try:
    from groq import Groq
    _groq_import_error = None
except ImportError as e:
    Groq = None
    _groq_import_error = e

MODEL_NAME = "llama-3.3-70b-versatile"  # Groq's current LLaMA3 model name (verify on console.groq.com if it changes)


# ---------------------------------------------------------------------
# STEP 1: SUMMARIZE CHART DATA (small stats only, never raw rows)
# ---------------------------------------------------------------------
def summarize_chart(df: pd.DataFrame, chart: dict) -> str:
    """
    Builds a short text summary of the data behind ONE chart,
    tailored to its chart_type. This summary - not the raw dataframe -
    is what gets sent to the LLM.
    """
    chart_type = chart["chart_type"]
    figure = chart["figure"]

    try:
        # Pull the underlying data straight from the Plotly figure so this
        # function doesn't need to re-derive groupings already done in chart_builder.py
        chart_data = figure.data[0]

        if chart_type == "histogram":
            col = figure.layout.xaxis.title.text
            series = df[col].dropna()
            return (f"Histogram of '{col}': min={series.min():.2f}, max={series.max():.2f}, "
                    f"mean={series.mean():.2f}, median={series.median():.2f}")

        elif chart_type in ("bar", "bar_grouped"):
            x_vals = list(chart_data.x)[:10]  # cap at top 10 to keep prompt small
            y_vals = list(chart_data.y)[:10]
            pairs = ", ".join(f"{x}={y}" for x, y in zip(x_vals, y_vals))
            return f"{chart['title']}: {pairs}"

        elif chart_type == "line":
            x_vals = list(chart_data.x)
            y_vals = list(chart_data.y)
            first_val, last_val = y_vals[0], y_vals[-1]
            peak_val = max(y_vals)
            peak_x = x_vals[y_vals.index(peak_val)]
            return (f"{chart['title']}: starts at {first_val}, ends at {last_val}, "
                    f"peak of {peak_val} at {peak_x}")

        elif chart_type == "scatter":
            x_col, y_col = chart["reason"], ""  # reason already contains both column names
            corr = df[[figure.layout.xaxis.title.text, figure.layout.yaxis.title.text]].corr().iloc[0, 1]
            return f"{chart['title']}: correlation coefficient = {round(corr, 2)}"

        else:
            return chart["title"]

    except Exception:
        # Fall back to just the chart's reason text if summarization fails -
        # keeps the pipeline running instead of crashing on one bad chart
        return chart.get("reason", chart.get("title", "Chart"))


# ---------------------------------------------------------------------
# STEP 2: BUILD PROMPT
# ---------------------------------------------------------------------
def build_prompt(summary: str) -> str:
    """
    Tight, constrained prompt - asks for a short, plain-language,
    business-relevant explanation. Avoids generic filler like
    "this chart shows a bar chart of...".
    """
    return (
        "You are a data analyst writing a one-sentence insight for a business dashboard. "
        "Given the summary below, write ONE concise, plain-English sentence (max 30 words) "
        "highlighting the most useful takeaway. Do not restate the chart type or filler phrases "
        "like 'this chart shows'. Be specific and use the actual numbers.\n\n"
        f"Data summary: {summary}\n\n"
        "Insight:"
    )


# ---------------------------------------------------------------------
# STEP 3: CALL GROQ
# ---------------------------------------------------------------------
def get_insight_from_groq(prompt: str, client) -> str:
    """
    Sends the prompt to Groq's LLaMA3 model and returns the plain-text insight.
    Raises exceptions upward - the caller decides how to handle failures.
    """
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=80,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------
# STEP 4: MASTER FUNCTION - ADD INSIGHTS TO ALL CHARTS
# ---------------------------------------------------------------------
def generate_insights_for_charts(df: pd.DataFrame, charts: list) -> list:
    """
    Loops through built charts, generates a summary + calls Groq for each,
    and attaches an 'insight' key to every chart dict.

    Fails gracefully: if the API key is missing or a call fails, the chart
    still gets returned with a fallback insight instead of crashing the app.
    """
    api_key = os.getenv("GROQ_API_KEY")

    if Groq is None:
        fallback_msg = f"Groq SDK not installed ({_groq_import_error}). Run: pip install groq"
        for chart in charts:
            chart["insight"] = fallback_msg
        return charts

    if not api_key:
        for chart in charts:
            chart["insight"] = "No GROQ_API_KEY found. Add it to your .env file to enable AI insights."
        return charts

    client = Groq(
        api_key=os.getenv("GROQ_API_KEY")
    )

    for chart in charts:
        summary = summarize_chart(df, chart)
        prompt = build_prompt(summary)
        try:
            insight = get_insight_from_groq(prompt, client)
        except Exception as e:
            insight = f"(AI insight unavailable: {e})"
        chart["insight"] = insight

    return charts


# ---------------------------------------------------------------------
# STANDALONE TEST BLOCK
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from profiler import profile_and_clean
    from Rule_engine import generate_chart_recommendations
    from Chart_builder import build_all_charts

    test_file = "../sample_data/sales.csv"
    report = profile_and_clean(test_file)
    df_cleaned = report["cleaned_dataframe"]

    recommendations = generate_chart_recommendations(df_cleaned, report["column_types"])
    charts = build_all_charts(df_cleaned, recommendations)

    # Test summarization WITHOUT calling the API (always works, no key needed)
    print("===== CHART SUMMARIES (input to the LLM) =====")
    for c in charts:
        summary = summarize_chart(df_cleaned, c)
        print(f"- [{c['chart_type']}] {summary}")

    # Test the full pipeline (will use fallback messages if no GROQ_API_KEY is set)
    print("\n===== FULL PIPELINE WITH INSIGHTS =====")
    charts_with_insights = generate_insights_for_charts(df_cleaned, charts)
    for c in charts_with_insights:
        print(f"\n[{c['chart_type']}] {c['title']}")
        print(f"  Insight: {c['insight']}")