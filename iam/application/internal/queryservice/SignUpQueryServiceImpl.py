from iam.domain.model.aggregates.RegistrationRequest import RegistrationRequest
from iam.domain.model.queries.SignUpQueries import ListPendingSignUpRequestsQuery
from iam.domain.repositories.RegistrationRequestRepository import RegistrationRequestRepository


class SignUpQueryServiceImpl:

    def __init__(self, registration_repo: RegistrationRequestRepository):
        self._registration_repo = registration_repo

    async def list_requests(self, query: ListPendingSignUpRequestsQuery) -> tuple[list[RegistrationRequest], int]:
        offset = (query.page - 1) * query.page_size
        requests = await self._registration_repo.list_by_status(query.status, offset, query.page_size)
        total = await self._registration_repo.count_by_status(query.status)
        return requests, total
