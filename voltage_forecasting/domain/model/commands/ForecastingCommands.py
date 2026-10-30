from dataclasses import dataclass


@dataclass(frozen=True)
class RequestTrainingCommand:
    dataset_id: int
    user_id: int


@dataclass(frozen=True)
class CreateAlertRuleCommand:
    max_voltage: float
    cell_id: int | None = None
