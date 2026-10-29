"""
Training settings: the Bi-LSTM the PoC chose, with the values it validated (see the PoC docs/hiperparametros.md).
Retraining repeats this recipe on newer data; changing it is a new image, not a runtime option.
"""

HORIZON_DAYS = 180  # forecast days
LOOKBACK_DAYS = 5  # input window of the model
SIGMA_LOOKBACK_DAYS = 30  # window an origin needs to count in the delta statistics
ANCHOR_DAYS = 3  # days averaged for the recent level of a cell
COV_CLIP = 5.0  # max |z| of the standardized covariates
KA_SHUTDOWN = 10.0  # kA below this is a shutdown day
# [Volts] adds up every physical cell of the electrolyzer even when the Excel lists fewer of them.
PHYSICAL_CELLS_PER_ELECTROLYZER = 181
STEP_THRESHOLD_MASK = 0.03  # level shift (V) after which the training targets are ignored
ES_BLOCK_DAYS = 270  # last days of the data used to stop training early and to evaluate
BACKTEST_DAYS = 60  # the evaluation forecasts this many days from an origin inside that block
VMD_HISTORY = 730  # days of history of the causal VMD
VMD_MIN_LEN = 60  # shortest in-service stretch that can be decomposed
VMD_N_DROP = 3  # highest-frequency modes left out of the filtered signal
MIN_DAYS = ES_BLOCK_DAYS + HORIZON_DAYS  # less data than this cannot train and evaluate
SEED = 42

TRAIN = {
    "hidden": 64, "layers": 1, "emb_dim": 8, "head_hidden": 256, "dropout": 0.2,
    "batch_size": 1024, "lr": 1e-3, "weight_decay": 1e-4, "clip": None,
    "max_epochs": 200, "patience": 20, "stride": 5,
}
