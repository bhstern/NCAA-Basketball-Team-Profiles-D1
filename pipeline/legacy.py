"""
Legacy-equivalence shims — the few places a one-season run needs help to produce
exactly what the all-seasons original produced.

Each shim reproduces a side effect of processing 2016-2026 in one frame. None of them
changes a value; they exist so per-year output is byte-identical to the original's.
"""


def pin_float_dtypes(df, int_columns=()):
    """
    Give numeric columns the dtype they had in the original all-seasons frame.

    The originals concatenated every season before cleaning, so a column that is
    whole-numbered in one season (e.g. PAKE/PASE all 0 in 2026) was still float
    because other seasons hold fractions or blanks, and was written as "0.0", not "0".
    A one-season frame would infer int. Every numeric column is float in the original
    except those listed in `int_columns`.
    """
    for col in df.columns:
        if df[col].dtype.kind in "iu" and col not in int_columns:
            df[col] = df[col].astype("float64")
    return df
