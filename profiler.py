# """
# profiler.py
# ------------
# Profiling & Cleaning Module for Auto-Dashboard-Generator.

# Responsibilities:
# 1. Load a CSV/Excel file into a pandas DataFrame.
# 2. Detect column types (numeric, categorical, date, text/ID).
# 3. Check data quality: duplicate rows, missing values, inconsistent types.
# 4. Clean the data (remove duplicates, fill missing values, fix obvious type issues).
# 5. Return a profiling report + cleaning summary + the cleaned DataFrame,
#    which is later passed to the rule_engine.py module.

# This file is designed to run standalone first (via the __main__ block)
# so you can test it against sample datasets before wiring it into
# FastAPI / Streamlit.
# """

# import pandas as pd
# import numpy as np
# import os
# import warnings

# # Suppress noisy (harmless) pandas date-parsing warnings when formats are mixed
# warnings.filterwarnings("ignore", message="Could not infer format")


# # ---------------------------------------------------------------------
# # STEP 1: LOAD FILE
# # ---------------------------------------------------------------------
# def load_file(file_path: str) -> pd.DataFrame:
#     """
#     Loads a CSV or Excel file into a pandas DataFrame.
#     Raises a clear error if the file type is unsupported or unreadable.
#     """
#     ext = os.path.splitext(file_path)[1].lower()

#     try:
#         if ext == ".csv":
#             df = pd.read_csv(file_path)
#         elif ext in (".xlsx", ".xls"):
#             df = pd.read_excel(file_path)
#         else:
#             raise ValueError(f"Unsupported file type: {ext}. Please upload a .csv or .xlsx file.")
#     except UnicodeDecodeError:
#         # Fallback for files with non-UTF8 encoding (common in real-world data)
#         df = pd.read_csv(file_path, encoding="latin1")

#     if df.empty:
#         raise ValueError("Uploaded file is empty. Please upload a file with data.")

#     return df


# # ---------------------------------------------------------------------
# # STEP 2: DETECT COLUMN TYPES
# # ---------------------------------------------------------------------
# def detect_column_types(df: pd.DataFrame) -> dict:
#     """
#     Classifies each column into one of: 'numeric', 'date', 'categorical', 'text/id'.

#     Logic:
#     - Try converting to datetime first (catches date columns stored as text).
#     - Numeric dtype -> numeric.
#     - Object dtype with low unique-value ratio -> categorical.
#     - Object dtype with high unique-value ratio (like names, IDs) -> text/id.
#     """
#     column_types = {}

#     for col in df.columns:
#         series = df[col]

#         # is_string_dtype/is_object_dtype covers both the legacy "object" dtype
#         # and pandas' newer dedicated "str" dtype (default from pandas 2.x/3.x)
#         is_text_like = pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)

#         # Try date detection first (only for text-like columns)
#         if is_text_like:
#             try:
#                 converted = pd.to_datetime(series, errors="coerce")
#                 # If most values successfully converted, treat as date
#                 if converted.notna().mean() > 0.8:
#                     column_types[col] = "date"
#                     continue
#             except Exception:
#                 pass

#         if pd.api.types.is_numeric_dtype(series):
#             column_types[col] = "numeric"
#         elif pd.api.types.is_datetime64_any_dtype(series):
#             column_types[col] = "date"
#         else:
#             unique_count = series.nunique(dropna=True)
#             unique_ratio = unique_count / max(len(series), 1)
#             # Categorical if unique values are a small share of rows, OR
#             # a small absolute number AND not almost-entirely unique
#             # (this second condition protects small datasets from
#             # misclassifying ID/name columns as categorical)
#             if unique_ratio <= 0.5 or (unique_count <= 20 and unique_ratio <= 0.7):
#                 column_types[col] = "categorical"
#             else:
#                 column_types[col] = "text/id"

#     return column_types


# # ---------------------------------------------------------------------
# # STEP 3: CHECK DUPLICATES
# # ---------------------------------------------------------------------
# def check_duplicates(df: pd.DataFrame) -> dict:
#     """
#     Returns count of fully duplicate rows.
#     """
#     duplicate_count = int(df.duplicated().sum())
#     return {
#         "duplicate_rows_found": duplicate_count,
#         "duplicate_percentage": round((duplicate_count / len(df)) * 100, 2) if len(df) > 0 else 0
#     }


# # ---------------------------------------------------------------------
# # STEP 4: CHECK MISSING VALUES
# # ---------------------------------------------------------------------
# def check_missing_values(df: pd.DataFrame) -> dict:
#     """
#     Returns missing value count and percentage per column.
#     """
#     missing_report = {}
#     total_rows = len(df)

#     for col in df.columns:
#         missing_count = int(df[col].isna().sum())
#         missing_pct = round((missing_count / total_rows) * 100, 2) if total_rows > 0 else 0
#         if missing_count > 0:
#             missing_report[col] = {
#                 "missing_count": missing_count,
#                 "missing_percentage": missing_pct
#             }

#     return missing_report


# # ---------------------------------------------------------------------
# # STEP 5: CHECK INCONSISTENT TYPES
# # ---------------------------------------------------------------------
# def check_inconsistent_types(df: pd.DataFrame, column_types: dict) -> list:
#     """
#     Flags columns where the detected type doesn't match the stored dtype,
#     e.g. a 'date' column still stored as text (object).
#     """
#     flags = []
#     for col, ctype in column_types.items():
#         is_text_like = pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col])
#         if ctype == "date" and is_text_like:
#             flags.append(f"Column '{col}' looks like a date but is stored as text.")
#         if ctype == "numeric" and is_text_like:
#             flags.append(f"Column '{col}' looks numeric but is stored as text.")
#     return flags


# # ---------------------------------------------------------------------
# # STEP 6: CLEAN DATA
# # ---------------------------------------------------------------------
# def clean_data(df: pd.DataFrame, column_types: dict) -> tuple[pd.DataFrame, dict]:
#     """
#     Cleans the DataFrame:
#     - Removes exact duplicate rows.
#     - Fills missing numeric values with median.
#     - Fills missing categorical values with 'Unknown'.
#     - Converts flagged date columns to proper datetime.
#     - Drops columns that are more than 60% missing (too unreliable to use).

#     Returns the cleaned DataFrame + a summary dict of what was changed.
#     """
#     summary = {}
#     original_rows = len(df)

#     # --- Remove duplicates ---
#     df_clean = df.drop_duplicates()
#     removed_duplicates = original_rows - len(df_clean)
#     summary["duplicates_removed"] = removed_duplicates

#     # --- Drop columns with excessive missing data (>60%) ---
#     threshold = 0.6
#     cols_to_drop = [
#         col for col in df_clean.columns
#         if df_clean[col].isna().mean() > threshold
#     ]
#     if cols_to_drop:
#         df_clean = df_clean.drop(columns=cols_to_drop)
#     summary["columns_dropped_high_missing"] = cols_to_drop

#     # --- Fill remaining missing values ---
#     filled_columns = {}
#     for col in df_clean.columns:
#         if df_clean[col].isna().sum() == 0:
#             continue

#         ctype = column_types.get(col, "text/id")

#         if ctype == "numeric":
#             median_val = df_clean[col].median()
#             df_clean[col] = df_clean[col].fillna(median_val)
#             filled_columns[col] = f"filled with median ({median_val})"
#         elif ctype == "date":
#             df_clean[col] = pd.to_datetime(df_clean[col], errors="coerce")
#         else:
#             df_clean[col] = df_clean[col].fillna("Unknown")
#             filled_columns[col] = "filled with 'Unknown'"

#     summary["missing_values_filled"] = filled_columns

#     # --- Fix inconsistent date columns ---
#     date_cols_fixed = []
#     for col, ctype in column_types.items():
#         if ctype == "date" and col in df_clean.columns:
#             is_text_like = pd.api.types.is_object_dtype(df_clean[col]) or pd.api.types.is_string_dtype(df_clean[col])
#             if is_text_like:
#                 df_clean[col] = pd.to_datetime(df_clean[col], errors="coerce")
#                 date_cols_fixed.append(col)
#     summary["date_columns_converted"] = date_cols_fixed

#     return df_clean, summary


# # ---------------------------------------------------------------------
# # STEP 7: MASTER FUNCTION - RUN FULL PROFILE + CLEAN PIPELINE
# # ---------------------------------------------------------------------
# def profile_and_clean(file_path: str) -> dict:
#     """
#     Runs the full pipeline end-to-end:
#     load -> detect types -> check duplicates/missing/inconsistent -> clean.

#     Returns a dictionary with everything the rule_engine.py and
#     Streamlit UI will need next.
#     """
#     df_raw = load_file(file_path)
#     column_types = detect_column_types(df_raw)

#     duplicate_report = check_duplicates(df_raw)
#     missing_report = check_missing_values(df_raw)
#     type_flags = check_inconsistent_types(df_raw, column_types)

#     df_cleaned, cleaning_summary = clean_data(df_raw, column_types)

#     result = {
#         "row_count_original": len(df_raw),
#         "row_count_cleaned": len(df_cleaned),
#         "column_types": column_types,
#         "duplicate_report": duplicate_report,
#         "missing_value_report": missing_report,
#         "inconsistent_type_flags": type_flags,
#         "cleaning_summary": cleaning_summary,
#         "cleaned_dataframe": df_cleaned,  # passed forward to rule_engine.py
#     }

#     return result


# # ---------------------------------------------------------------------
# # STANDALONE TEST BLOCK
# # ---------------------------------------------------------------------
# if __name__ == "__main__":
#     # Point this at any sample file inside sample_data/ to test locally
#     test_file = ""

#     if not os.path.exists(test_file):
#         print(f"Test file not found at {test_file}. "
#               f"Add a sample CSV/Excel file to sample_data/ and update the path above.")
#     else:
#         report = profile_and_clean(test_file)

#         print("\n===== COLUMN TYPES =====")
#         for col, ctype in report["column_types"].items():
#             print(f"  {col}: {ctype}")

#         print("\n===== DUPLICATE REPORT =====")
#         print(f"  {report['duplicate_report']}")

#         print("\n===== MISSING VALUE REPORT =====")
#         if report["missing_value_report"]:
#             for col, info in report["missing_value_report"].items():
#                 print(f"  {col}: {info}")
#         else:
#             print("  No missing values found.")

#         print("\n===== INCONSISTENT TYPE FLAGS =====")
#         if report["inconsistent_type_flags"]:
#             for flag in report["inconsistent_type_flags"]:
#                 print(f"  - {flag}")
#         else:
#             print("  None found.")

#         print("\n===== CLEANING SUMMARY =====")
#         print(f"  Rows before: {report['row_count_original']}")
#         print(f"  Rows after:  {report['row_count_cleaned']}")
#         print(f"  Duplicates removed: {report['cleaning_summary']['duplicates_removed']}")
#         print(f"  Columns dropped (high missing): {report['cleaning_summary']['columns_dropped_high_missing']}")
#         print(f"  Missing values filled: {report['cleaning_summary']['missing_values_filled']}")
#         print(f"  Date columns converted: {report['cleaning_summary']['date_columns_converted']}")

#         print("\n===== CLEANED DATA PREVIEW =====")
#         print(report["cleaned_dataframe"].head())



"""
profiler.py
------------
Profiling & Cleaning Module for Auto-Dashboard-Generator.

Responsibilities:
1. Load a CSV/Excel file into a pandas DataFrame.
2. Detect column types (numeric, categorical, date, text/ID).
3. Check data quality: duplicate rows, missing values, inconsistent types.
4. Clean the data (remove duplicates, fill missing values, fix obvious type issues).
5. Return a profiling report + cleaning summary + the cleaned DataFrame,
   which is later passed to the rule_engine.py module.

This file is designed to run standalone first (via the __main__ block)
so you can test it against sample datasets before wiring it into
FastAPI / Streamlit.
"""

import pandas as pd
import numpy as np
import os
import csv
import warnings

# Suppress noisy (harmless) pandas date-parsing warnings when formats are mixed
warnings.filterwarnings("ignore", message="Could not infer format")


def _detect_delimiter(file_path: str) -> str:
    """
    Sniffs the delimiter of a text/CSV file by sampling its first few lines.
    Falls back to comma if detection is inconclusive - comma is the most
    common default and a safe fallback for ambiguous single-column files.
    """
    candidates = [",", ";", "\t", "|"]

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            sample = f.read(4096)
        sniffed = csv.Sniffer().sniff(sample, delimiters="".join(candidates))
        return sniffed.delimiter
    except Exception:
        # Sniffer can fail on ambiguous samples - fall back to a manual count:
        # pick whichever candidate delimiter appears most consistently in the sample
        try:
            first_line = sample.splitlines()[0] if sample else ""
            counts = {d: first_line.count(d) for d in candidates}
            best = max(counts, key=counts.get)
            return best if counts[best] > 0 else ","
        except Exception:
            return ","


# ---------------------------------------------------------------------
# STEP 1: LOAD FILE
# ---------------------------------------------------------------------
def load_file(file_path: str) -> pd.DataFrame:
    """
    Loads a CSV or Excel file into a pandas DataFrame.
    Raises a clear error if the file type is unsupported or unreadable.
    """
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".csv":
            delimiter = _detect_delimiter(file_path)
            df = pd.read_csv(file_path, sep=delimiter)
            # Safety net: if detection still resulted in a single column but
            # the file clearly has other common delimiters in it, retry with python engine's sniffer
            if df.shape[1] == 1:
                df_retry = pd.read_csv(file_path, sep=None, engine="python")
                if df_retry.shape[1] > 1:
                    df = df_retry
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}. Please upload a .csv or .xlsx file.")
    except UnicodeDecodeError:
        # Fallback for files with non-UTF8 encoding (common in real-world data)
        df = pd.read_csv(file_path, encoding="latin1")

    if df.empty:
        raise ValueError("Uploaded file is empty. Please upload a file with data.")

    return df


# ---------------------------------------------------------------------
# STEP 2: DETECT COLUMN TYPES
# ---------------------------------------------------------------------
def detect_column_types(df: pd.DataFrame) -> dict:
    """
    Classifies each column into one of: 'numeric', 'date', 'categorical', 'text/id'.

    Logic:
    - Try converting to datetime first (catches date columns stored as text).
    - Numeric dtype -> numeric.
    - Object dtype with low unique-value ratio -> categorical.
    - Object dtype with high unique-value ratio (like names, IDs) -> text/id.
    """
    column_types = {}

    for col in df.columns:
        series = df[col]

        # is_string_dtype/is_object_dtype covers both the legacy "object" dtype
        # and pandas' newer dedicated "str" dtype (default from pandas 2.x/3.x)
        is_text_like = pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)

        # Try date detection first (only for text-like columns)
        if is_text_like:
            try:
                converted = pd.to_datetime(series, errors="coerce")
                # If most values successfully converted, treat as date
                if converted.notna().mean() > 0.8:
                    column_types[col] = "date"
                    continue
            except Exception:
                pass

        if pd.api.types.is_numeric_dtype(series):
            column_types[col] = "numeric"
        elif pd.api.types.is_datetime64_any_dtype(series):
            column_types[col] = "date"
        else:
            unique_count = series.nunique(dropna=True)
            unique_ratio = unique_count / max(len(series), 1)
            # Categorical if unique values are a small share of rows, OR
            # a small absolute number AND not almost-entirely unique
            # (this second condition protects small datasets from
            # misclassifying ID/name columns as categorical)
            if unique_ratio <= 0.5 or (unique_count <= 20 and unique_ratio <= 0.7):
                column_types[col] = "categorical"
            else:
                column_types[col] = "text/id"

    return column_types


# ---------------------------------------------------------------------
# STEP 3: CHECK DUPLICATES
# ---------------------------------------------------------------------
def check_duplicates(df: pd.DataFrame) -> dict:
    """
    Returns count of fully duplicate rows.
    """
    duplicate_count = int(df.duplicated().sum())
    return {
        "duplicate_rows_found": duplicate_count,
        "duplicate_percentage": round((duplicate_count / len(df)) * 100, 2) if len(df) > 0 else 0
    }


# ---------------------------------------------------------------------
# STEP 4: CHECK MISSING VALUES
# ---------------------------------------------------------------------
def check_missing_values(df: pd.DataFrame) -> dict:
    """
    Returns missing value count and percentage per column.
    """
    missing_report = {}
    total_rows = len(df)

    for col in df.columns:
        missing_count = int(df[col].isna().sum())
        missing_pct = round((missing_count / total_rows) * 100, 2) if total_rows > 0 else 0
        if missing_count > 0:
            missing_report[col] = {
                "missing_count": missing_count,
                "missing_percentage": missing_pct
            }

    return missing_report


# ---------------------------------------------------------------------
# STEP 5: CHECK INCONSISTENT TYPES
# ---------------------------------------------------------------------
def check_inconsistent_types(df: pd.DataFrame, column_types: dict) -> list:
    """
    Flags columns where the detected type doesn't match the stored dtype,
    e.g. a 'date' column still stored as text (object).
    """
    flags = []
    for col, ctype in column_types.items():
        is_text_like = pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col])
        if ctype == "date" and is_text_like:
            flags.append(f"Column '{col}' looks like a date but is stored as text.")
        if ctype == "numeric" and is_text_like:
            flags.append(f"Column '{col}' looks numeric but is stored as text.")
    return flags


# ---------------------------------------------------------------------
# STEP 6: CLEAN DATA
# ---------------------------------------------------------------------
def clean_data(df: pd.DataFrame, column_types: dict) -> tuple[pd.DataFrame, dict]:
    """
    Cleans the DataFrame:
    - Removes exact duplicate rows.
    - Fills missing numeric values with median.
    - Fills missing categorical values with 'Unknown'.
    - Converts flagged date columns to proper datetime.
    - Drops columns that are more than 60% missing (too unreliable to use).

    Returns the cleaned DataFrame + a summary dict of what was changed.
    """
    summary = {}
    original_rows = len(df)

    # --- Remove duplicates ---
    df_clean = df.drop_duplicates()
    removed_duplicates = original_rows - len(df_clean)
    summary["duplicates_removed"] = removed_duplicates

    # --- Drop columns with excessive missing data (>60%) ---
    threshold = 0.6
    cols_to_drop = [
        col for col in df_clean.columns
        if df_clean[col].isna().mean() > threshold
    ]
    if cols_to_drop:
        df_clean = df_clean.drop(columns=cols_to_drop)
    summary["columns_dropped_high_missing"] = cols_to_drop

    # --- Fill remaining missing values ---
    filled_columns = {}
    for col in df_clean.columns:
        if df_clean[col].isna().sum() == 0:
            continue

        ctype = column_types.get(col, "text/id")

        if ctype == "numeric":
            median_val = df_clean[col].median()
            df_clean[col] = df_clean[col].fillna(median_val)
            filled_columns[col] = f"filled with median ({median_val})"
        elif ctype == "date":
            df_clean[col] = pd.to_datetime(df_clean[col], errors="coerce")
        else:
            df_clean[col] = df_clean[col].fillna("Unknown")
            filled_columns[col] = "filled with 'Unknown'"

    summary["missing_values_filled"] = filled_columns

    # --- Fix inconsistent date columns ---
    date_cols_fixed = []
    for col, ctype in column_types.items():
        if ctype == "date" and col in df_clean.columns:
            is_text_like = pd.api.types.is_object_dtype(df_clean[col]) or pd.api.types.is_string_dtype(df_clean[col])
            if is_text_like:
                df_clean[col] = pd.to_datetime(df_clean[col], errors="coerce")
                date_cols_fixed.append(col)
    summary["date_columns_converted"] = date_cols_fixed

    return df_clean, summary


# ---------------------------------------------------------------------
# STEP 7: MASTER FUNCTION - RUN FULL PROFILE + CLEAN PIPELINE
# ---------------------------------------------------------------------
def profile_and_clean(file_path: str) -> dict:
    """
    Runs the full pipeline end-to-end:
    load -> detect types -> check duplicates/missing/inconsistent -> clean.

    Returns a dictionary with everything the rule_engine.py and
    Streamlit UI will need next.
    """
    df_raw = load_file(file_path)
    column_types = detect_column_types(df_raw)

    duplicate_report = check_duplicates(df_raw)
    missing_report = check_missing_values(df_raw)
    type_flags = check_inconsistent_types(df_raw, column_types)

    df_cleaned, cleaning_summary = clean_data(df_raw, column_types)

    # CRITICAL FIX: column_types was built from the ORIGINAL dataframe, but
    # clean_data() may have dropped columns (e.g. >60% missing). Downstream
    # modules (rule_engine.py, chart_builder.py) receive column_types and
    # assume every key exists in the dataframe - so we filter it here to
    # only keep columns that survived cleaning. This prevents KeyError
    # crashes when a dropped column is still referenced later.
    column_types = {col: ctype for col, ctype in column_types.items() if col in df_cleaned.columns}

    result = {
        "row_count_original": len(df_raw),
        "row_count_cleaned": len(df_cleaned),
        "column_types": column_types,
        "duplicate_report": duplicate_report,
        "missing_value_report": missing_report,
        "inconsistent_type_flags": type_flags,
        "cleaning_summary": cleaning_summary,
        "cleaned_dataframe": df_cleaned,  # passed forward to rule_engine.py
    }

    return result


# ---------------------------------------------------------------------
# STANDALONE TEST BLOCK
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # Point this at any sample file inside sample_data/ to test locally
    test_file = "../sample_data/sales.csv"

    if not os.path.exists(test_file):
        print(f"Test file not found at {test_file}. "
              f"Add a sample CSV/Excel file to sample_data/ and update the path above.")
    else:
        report = profile_and_clean(test_file)

        print("\n===== COLUMN TYPES =====")
        for col, ctype in report["column_types"].items():
            print(f"  {col}: {ctype}")

        print("\n===== DUPLICATE REPORT =====")
        print(f"  {report['duplicate_report']}")

        print("\n===== MISSING VALUE REPORT =====")
        if report["missing_value_report"]:
            for col, info in report["missing_value_report"].items():
                print(f"  {col}: {info}")
        else:
            print("  No missing values found.")

        print("\n===== INCONSISTENT TYPE FLAGS =====")
        if report["inconsistent_type_flags"]:
            for flag in report["inconsistent_type_flags"]:
                print(f"  - {flag}")
        else:
            print("  None found.")

        print("\n===== CLEANING SUMMARY =====")
        print(f"  Rows before: {report['row_count_original']}")
        print(f"  Rows after:  {report['row_count_cleaned']}")
        print(f"  Duplicates removed: {report['cleaning_summary']['duplicates_removed']}")
        print(f"  Columns dropped (high missing): {report['cleaning_summary']['columns_dropped_high_missing']}")
        print(f"  Missing values filled: {report['cleaning_summary']['missing_values_filled']}")
        print(f"  Date columns converted: {report['cleaning_summary']['date_columns_converted']}")

        print("\n===== CLEANED DATA PREVIEW =====")
        print(report["cleaned_dataframe"].head())