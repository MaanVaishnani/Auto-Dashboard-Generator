# """
# rule_engine.py
# ---------------
# Rule Engine module for Auto-Dashboard-Generator.

# Takes the cleaned DataFrame + column_types produced by profiler.py
# and decides:
# 1. Which columns are chartable (excludes IDs, pure-unique text).
# 2. Which chart type fits each column / column-pair.
# 3. Which charts matter most (priority scoring), since a wide dataset
#    could otherwise generate 50+ charts.

# Output: an ordered list of chart recommendation dicts, e.g.
#     {
#         "chart_type": "line",
#         "columns": ["OrderDate", "Sales"],
#         "reason": "Trend of Sales over OrderDate",
#         "priority": 95
#     }

# This list is what chart_builder.py (Plotly) will loop over next.
# """

# import pandas as pd

# # Keywords that suggest a numeric column is business-relevant
# # (used to boost priority - e.g. "Sales" matters more than a random numeric column)
# IMPORTANT_KEYWORDS = ["sales", "revenue", "amount", "price", "profit", "quantity",
#                       "cost", "total", "count", "score", "rating"]

# # Keywords that suggest a column is an identifier, not analytical data
# ID_KEYWORDS = ["id", "uuid", "code", "index"]

# MAX_CHARTS = 8  # don't overwhelm the dashboard


# # ---------------------------------------------------------------------
# # STEP 1: IDENTIFY ID-LIKE / NON-CHARTABLE COLUMNS
# # ---------------------------------------------------------------------
# def identify_excluded_columns(df: pd.DataFrame, column_types: dict) -> set:
#     """
#     Flags columns that should NOT be charted:
#     - Column name contains an ID-like keyword (OrderID, CustomerCode, etc.)
#     - text/id type with near-100% unique values (names, free text)
#     """
#     excluded = set()

#     for col, ctype in column_types.items():
#         col_lower = col.lower()

#         # Name-based exclusion
#         if any(keyword in col_lower for keyword in ID_KEYWORDS):
#             excluded.add(col)
#             continue

#         # High-cardinality text columns aren't chartable in a meaningful way
#         if ctype == "text/id":
#             unique_ratio = df[col].nunique(dropna=True) / max(len(df), 1)
#             if unique_ratio > 0.9:
#                 excluded.add(col)

#     return excluded


# # ---------------------------------------------------------------------
# # STEP 2: SCORE NUMERIC COLUMNS BY BUSINESS RELEVANCE
# # ---------------------------------------------------------------------
# def score_numeric_column(col_name: str, df: pd.DataFrame) -> int:
#     """
#     Assigns a base relevance score to a numeric column.
#     - +30 if the column name matches a business keyword (Sales, Revenue, etc.)
#     - + up to 20 points based on normalized variance (more variation = more interesting)
#     """
#     score = 50  # base score for any numeric column

#     col_lower = col_name.lower()
#     if any(keyword in col_lower for keyword in IMPORTANT_KEYWORDS):
#         score += 30

#     # Reward columns with meaningful variance (avoid near-constant columns)
#     series = df[col_name].dropna()
#     if len(series) > 1 and series.mean() != 0:
#         cv = series.std() / abs(series.mean())  # coefficient of variation
#         score += min(int(cv * 20), 20)

#     return score


# # ---------------------------------------------------------------------
# # STEP 3: SINGLE-COLUMN CHART RULES
# # ---------------------------------------------------------------------
# def single_column_rules(df: pd.DataFrame, column_types: dict, excluded: set) -> list:
#     """
#     Generates chart recommendations based on one column at a time:
#     - numeric -> histogram (distribution)
#     - categorical (few unique values) -> bar chart of value counts
#     """
#     recommendations = []

#     for col, ctype in column_types.items():
#         if col in excluded:
#             continue

#         if ctype == "numeric":
#             priority = score_numeric_column(col, df)
#             recommendations.append({
#                 "chart_type": "histogram",
#                 "columns": [col],
#                 "reason": f"Distribution of {col}",
#                 "priority": priority
#             })

#         elif ctype == "categorical":
#             unique_count = df[col].nunique(dropna=True)
#             if unique_count <= 15:  # too many categories = unreadable bar chart
#                 recommendations.append({
#                     "chart_type": "bar",
#                     "columns": [col],
#                     "reason": f"Count of records by {col}",
#                     "priority": 60
#                 })

#     return recommendations


# # ---------------------------------------------------------------------
# # STEP 4: TWO-COLUMN RELATIONSHIP RULES
# # ---------------------------------------------------------------------
# def two_column_rules(df: pd.DataFrame, column_types: dict, excluded: set) -> list:
#     """
#     Generates chart recommendations based on column-pair relationships:
#     - date + numeric -> line chart (trend over time)
#     - categorical + numeric -> bar chart (aggregated numeric by category)
#     """
#     recommendations = []

#     date_cols = [c for c, t in column_types.items() if t == "date" and c not in excluded]
#     numeric_cols = [c for c, t in column_types.items() if t == "numeric" and c not in excluded]
#     categorical_cols = [c for c, t in column_types.items() if t == "categorical" and c not in excluded]

#     # Date + numeric -> trend line (high priority, time-series is usually the most valuable insight)
#     for date_col in date_cols:
#         for num_col in numeric_cols:
#             priority = score_numeric_column(num_col, df) + 25  # trend charts get a boost
#             recommendations.append({
#                 "chart_type": "line",
#                 "columns": [date_col, num_col],
#                 "reason": f"Trend of {num_col} over {date_col}",
#                 "priority": priority
#             })

#     # Categorical + numeric -> grouped/aggregated bar chart
#     for cat_col in categorical_cols:
#         unique_count = df[cat_col].nunique(dropna=True)
#         if unique_count > 15:
#             continue  # skip unreadable high-cardinality groupings

#         for num_col in numeric_cols:
#             priority = score_numeric_column(num_col, df) + 10
#             recommendations.append({
#                 "chart_type": "bar_grouped",
#                 "columns": [cat_col, num_col],
#                 "reason": f"Total {num_col} by {cat_col}",
#                 "priority": priority
#             })

#     return recommendations


# # ---------------------------------------------------------------------
# # STEP 5: CORRELATION-BASED RULES (numeric vs numeric)
# # ---------------------------------------------------------------------
# def correlation_rules(df: pd.DataFrame, column_types: dict, excluded: set, threshold: float = 0.6) -> list:
#     """
#     Finds pairs of numeric columns with strong correlation (positive or negative)
#     and recommends a scatter plot for each notable pair.
#     """
#     recommendations = []
#     numeric_cols = [c for c, t in column_types.items() if t == "numeric" and c not in excluded]

#     if len(numeric_cols) < 2:
#         return recommendations

#     corr_matrix = df[numeric_cols].corr(numeric_only=True)

#     seen_pairs = set()
#     for col_a in numeric_cols:
#         for col_b in numeric_cols:
#             if col_a == col_b:
#                 continue
#             pair_key = tuple(sorted([col_a, col_b]))
#             if pair_key in seen_pairs:
#                 continue
#             seen_pairs.add(pair_key)

#             corr_value = corr_matrix.loc[col_a, col_b]
#             if pd.notna(corr_value) and abs(corr_value) >= threshold:
#                 recommendations.append({
#                     "chart_type": "scatter",
#                     "columns": [col_a, col_b],
#                     "reason": f"Strong {'positive' if corr_value > 0 else 'negative'} "
#                               f"correlation ({round(corr_value, 2)}) between {col_a} and {col_b}",
#                     "priority": 70 + int(abs(corr_value) * 20)
#                 })

#     return recommendations


# # ---------------------------------------------------------------------
# # STEP 6: MASTER FUNCTION - BUILD FINAL PRIORITIZED CHART LIST
# # ---------------------------------------------------------------------
# def generate_chart_recommendations(df: pd.DataFrame, column_types: dict, max_charts: int = MAX_CHARTS) -> list:
#     """
#     Runs all rule categories, merges results, sorts by priority (highest first),
#     and trims to max_charts so the dashboard stays readable.
#     """
#     excluded = identify_excluded_columns(df, column_types)

#     all_recommendations = []
#     all_recommendations += single_column_rules(df, column_types, excluded)
#     all_recommendations += two_column_rules(df, column_types, excluded)
#     all_recommendations += correlation_rules(df, column_types, excluded)

#     # Sort by priority, descending
#     all_recommendations.sort(key=lambda x: x["priority"], reverse=True)

#     return all_recommendations[:max_charts]


# # ---------------------------------------------------------------------
# # STANDALONE TEST BLOCK
# # ---------------------------------------------------------------------
# if __name__ == "__main__":
#     import sys
#     sys.path.insert(0, ".")
#     from profiler import profile_and_clean

#     test_file = "sales.csv"
#     report = profile_and_clean(test_file)

#     df_cleaned = report["cleaned_dataframe"]
#     column_types = report["column_types"]

#     charts = generate_chart_recommendations(df_cleaned, column_types)

#     print("\n===== RECOMMENDED CHARTS (priority order) =====")
#     for i, chart in enumerate(charts, start=1):
#         print(f"{i}. [{chart['chart_type']}] columns={chart['columns']} "
#               f"| priority={chart['priority']} | reason: {chart['reason']}")






"""
rule_engine.py
---------------
Rule Engine module for Auto-Dashboard-Generator.

Takes the cleaned DataFrame + column_types produced by profiler.py
and decides:
1. Which columns are chartable (excludes IDs, pure-unique text).
2. Which chart type fits each column / column-pair.
3. Which charts matter most (priority scoring), since a wide dataset
   could otherwise generate 50+ charts.

Output: an ordered list of chart recommendation dicts, e.g.
    {
        "chart_type": "line",
        "columns": ["OrderDate", "Sales"],
        "reason": "Trend of Sales over OrderDate",
        "priority": 95
    }

This list is what chart_builder.py (Plotly) will loop over next.
"""

import pandas as pd

# Keywords that suggest a numeric column is business-relevant
# (used to boost priority - e.g. "Sales" matters more than a random numeric column)
IMPORTANT_KEYWORDS = ["sales", "revenue", "amount", "price", "profit", "quantity",
                      "cost", "total", "count", "score", "rating"]

# Keywords that suggest a column is an identifier, not analytical data
ID_KEYWORDS = ["id", "uuid", "code", "index"]

MAX_CHARTS = 8  # don't overwhelm the dashboard


# ---------------------------------------------------------------------
# STEP 1: IDENTIFY ID-LIKE / NON-CHARTABLE COLUMNS
# ---------------------------------------------------------------------
def identify_excluded_columns(df: pd.DataFrame, column_types: dict) -> set:
    """
    Flags columns that should NOT be charted:
    - Column name contains an ID-like keyword (OrderID, CustomerCode, etc.)
    - text/id type with near-100% unique values (names, free text)
    """
    excluded = set()

    for col, ctype in column_types.items():
        col_lower = col.lower()

        # Name-based exclusion
        if any(keyword in col_lower for keyword in ID_KEYWORDS):
            excluded.add(col)
            continue

        # High-cardinality text columns aren't chartable in a meaningful way
        if ctype == "text/id":
            unique_ratio = df[col].nunique(dropna=True) / max(len(df), 1)
            if unique_ratio > 0.9:
                excluded.add(col)

    return excluded


# ---------------------------------------------------------------------
# STEP 2: SCORE NUMERIC COLUMNS BY BUSINESS RELEVANCE
# ---------------------------------------------------------------------
def score_numeric_column(col_name: str, df: pd.DataFrame) -> int:
    """
    Assigns a base relevance score to a numeric column.
    - +30 if the column name matches a business keyword (Sales, Revenue, etc.)
    - + up to 20 points based on normalized variance (more variation = more interesting)
    """
    score = 50  # base score for any numeric column

    col_lower = col_name.lower()
    if any(keyword in col_lower for keyword in IMPORTANT_KEYWORDS):
        score += 30

    # Reward columns with meaningful variance (avoid near-constant columns)
    series = df[col_name].dropna()
    if len(series) > 1 and series.mean() != 0:
        cv = series.std() / abs(series.mean())  # coefficient of variation
        score += min(int(cv * 20), 20)

    return score


# ---------------------------------------------------------------------
# STEP 3: SINGLE-COLUMN CHART RULES
# ---------------------------------------------------------------------
def single_column_rules(df: pd.DataFrame, column_types: dict, excluded: set) -> list:
    """
    Generates chart recommendations based on one column at a time:
    - numeric -> histogram (distribution)
    - categorical (few unique values) -> bar chart of value counts
    """
    recommendations = []

    for col, ctype in column_types.items():
        if col in excluded:
            continue

        if ctype == "numeric":
            priority = score_numeric_column(col, df)
            recommendations.append({
                "chart_type": "histogram",
                "columns": [col],
                "reason": f"Distribution of {col}",
                "priority": priority
            })

        elif ctype == "categorical":
            unique_count = df[col].nunique(dropna=True)
            if unique_count <= 15:  # too many categories = unreadable bar chart
                recommendations.append({
                    "chart_type": "bar",
                    "columns": [col],
                    "reason": f"Count of records by {col}",
                    "priority": 60
                })

    return recommendations


# ---------------------------------------------------------------------
# STEP 4: TWO-COLUMN RELATIONSHIP RULES
# ---------------------------------------------------------------------
def two_column_rules(df: pd.DataFrame, column_types: dict, excluded: set) -> list:
    """
    Generates chart recommendations based on column-pair relationships:
    - date + numeric -> line chart (trend over time)
    - categorical + numeric -> bar chart (aggregated numeric by category)
    """
    recommendations = []

    date_cols = [c for c, t in column_types.items() if t == "date" and c not in excluded]
    numeric_cols = [c for c, t in column_types.items() if t == "numeric" and c not in excluded]
    categorical_cols = [c for c, t in column_types.items() if t == "categorical" and c not in excluded]

    # Date + numeric -> trend line (high priority, time-series is usually the most valuable insight)
    for date_col in date_cols:
        for num_col in numeric_cols:
            priority = score_numeric_column(num_col, df) + 25  # trend charts get a boost
            recommendations.append({
                "chart_type": "line",
                "columns": [date_col, num_col],
                "reason": f"Trend of {num_col} over {date_col}",
                "priority": priority
            })

    # Categorical + numeric -> grouped/aggregated bar chart
    for cat_col in categorical_cols:
        unique_count = df[cat_col].nunique(dropna=True)
        if unique_count > 15:
            continue  # skip unreadable high-cardinality groupings

        for num_col in numeric_cols:
            priority = score_numeric_column(num_col, df) + 10
            recommendations.append({
                "chart_type": "bar_grouped",
                "columns": [cat_col, num_col],
                "reason": f"Total {num_col} by {cat_col}",
                "priority": priority
            })

    return recommendations


# ---------------------------------------------------------------------
# STEP 5: CORRELATION-BASED RULES (numeric vs numeric)
# ---------------------------------------------------------------------
def correlation_rules(df: pd.DataFrame, column_types: dict, excluded: set, threshold: float = 0.6) -> list:
    """
    Finds pairs of numeric columns with strong correlation (positive or negative)
    and recommends a scatter plot for each notable pair.
    """
    recommendations = []
    numeric_cols = [c for c, t in column_types.items() if t == "numeric" and c not in excluded]

    if len(numeric_cols) < 2:
        return recommendations

    corr_matrix = df[numeric_cols].corr(numeric_only=True)

    seen_pairs = set()
    for col_a in numeric_cols:
        for col_b in numeric_cols:
            if col_a == col_b:
                continue
            pair_key = tuple(sorted([col_a, col_b]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            corr_value = corr_matrix.loc[col_a, col_b]
            if pd.notna(corr_value) and abs(corr_value) >= threshold:
                recommendations.append({
                    "chart_type": "scatter",
                    "columns": [col_a, col_b],
                    "reason": f"Strong {'positive' if corr_value > 0 else 'negative'} "
                              f"correlation ({round(corr_value, 2)}) between {col_a} and {col_b}",
                    "priority": 70 + int(abs(corr_value) * 20)
                })

    return recommendations


# ---------------------------------------------------------------------
# STEP 6: MASTER FUNCTION - BUILD FINAL PRIORITIZED CHART LIST
# ---------------------------------------------------------------------
def generate_chart_recommendations(df: pd.DataFrame, column_types: dict, max_charts: int = MAX_CHARTS) -> list:
    """
    Runs all rule categories, merges results, sorts by priority (highest first),
    applies a per-chart-type cap so the dashboard stays visually diverse
    (otherwise a dataset with many date+numeric pairs could fill every slot
    with near-identical line charts), then trims to max_charts.
    """
    excluded = identify_excluded_columns(df, column_types)

    all_recommendations = []
    all_recommendations += single_column_rules(df, column_types, excluded)
    all_recommendations += two_column_rules(df, column_types, excluded)
    all_recommendations += correlation_rules(df, column_types, excluded)

    # Sort by priority, descending
    all_recommendations.sort(key=lambda x: x["priority"], reverse=True)

    # --- Diversity pass: cap how many charts of the same type can appear ---
    type_caps = {"line": 3, "bar_grouped": 3, "bar": 3, "histogram": 3, "scatter": 2}
    type_counts = {}
    diverse_selection = []
    leftover = []

    for rec in all_recommendations:
        ctype = rec["chart_type"]
        count = type_counts.get(ctype, 0)
        if count < type_caps.get(ctype, 3):
            diverse_selection.append(rec)
            type_counts[ctype] = count + 1
        else:
            leftover.append(rec)  # over the cap for now, may still be used to fill remaining slots

        if len(diverse_selection) >= max_charts:
            break

    # Backfill: if caps left us with fewer than max_charts (e.g. dataset only
    # has 2 chartable columns total), fill remaining slots from leftovers
    if len(diverse_selection) < max_charts:
        remaining_slots = max_charts - len(diverse_selection)
        diverse_selection += leftover[:remaining_slots]

    return diverse_selection[:max_charts]


# ---------------------------------------------------------------------
# STANDALONE TEST BLOCK
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from profiler import profile_and_clean

    test_file = "../sample_data/sales.csv"
    report = profile_and_clean(test_file)

    df_cleaned = report["cleaned_dataframe"]
    column_types = report["column_types"]

    charts = generate_chart_recommendations(df_cleaned, column_types)

    print("\n===== RECOMMENDED CHARTS (priority order) =====")
    for i, chart in enumerate(charts, start=1):
        print(f"{i}. [{chart['chart_type']}] columns={chart['columns']} "
              f"| priority={chart['priority']} | reason: {chart['reason']}")