"""Cleaning thresholds of the ETL, the same values the PoC validated (see its docs/hiperparametros.md)."""

KA_SHUTDOWN = 10.0  # kA below this is a shutdown day
MAX_INTERP_DAYS = 12  # gaps of up to this many days are interpolated
OOS_MIN_DAYS = 7  # minimum length of an out-of-service stretch
OOS_MERGE_DAYS = 5  # interruptions of up to this many days do not split an out-of-service stretch
V_OUT_OF_SERVICE = 0.5  # V below this (or negative) with normal kA means the cell is out of service
V_MAX_PLAUSIBLE = 5.0  # V above this is an outlier
STEP_THRESHOLD_V = 0.10  # level shift (V) reported for diagnosis
STEP_WINDOW_DAYS = 7  # days of median before/after a candidate level shift
VAL_FRACTION = 0.20  # share of the most recent days kept for validation
MIN_DAYS = 900  # the least a model can be validated with (the training needs the same); a file that complements another is counted merged
