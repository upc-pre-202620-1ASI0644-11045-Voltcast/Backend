from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class GetForecastsQuery:
    date_from: date | None = None
    date_to: date | None = None
    cell_id: int | None = None
    exceeds: bool | None = None  # only the forecasts above (True) or within (False) the allowed voltage


@dataclass(frozen=True)
class GetModelMetricsQuery:
    pass


@dataclass(frozen=True)
class GetEvaluationQuery:
    day: date | None = None  # defaults to the latest day with validation data
    limit: int = 10
    worst_first: bool = True


@dataclass(frozen=True)
class GetEvaluationSeriesQuery:
    date_from: date | None = None  # defaults to the first day of the backtest
    date_to: date | None = None  # defaults to the last day of the backtest


@dataclass(frozen=True)
class GetTrainingByIdQuery:
    training_id: int


@dataclass(frozen=True)
class GetAllTrainingsQuery:
    pass


@dataclass(frozen=True)
class GetAlertRulesQuery:
    pass
