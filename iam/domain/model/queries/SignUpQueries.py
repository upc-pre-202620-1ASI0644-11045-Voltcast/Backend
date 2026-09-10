from dataclasses import dataclass, field

from iam.domain.model.aggregates.RegistrationRequest import RegistrationStatus


@dataclass(frozen=True)
class ListPendingSignUpRequestsQuery:
    """List registration requests, optionally filtered by status"""
    status: RegistrationStatus = RegistrationStatus.PENDING
    page: int = 1
    page_size: int = 20
