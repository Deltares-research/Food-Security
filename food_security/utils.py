"""Module containing utility functions."""
import pandas as pd


def _prep_conversion_table(conversion_df: pd.DataFrame) -> pd.DataFrame:
    # drop duplicate occurrences of item code, retaining the first occurrence
    conversion_df = conversion_df.drop_duplicates(subset="code", keep="first").dropna()

    # Remove left padded zeros on code column
    conversion_df.loc[:, "code"] = conversion_df["code"].str.lstrip("0")

    # Rename code column to Item code to match FAOSTAT
    return conversion_df.rename(columns={"code": "Item Code"})
