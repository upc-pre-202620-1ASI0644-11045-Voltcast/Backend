from cell_management.domain.model.aggregates.Component import Component
from cell_management.domain.model.queries.ComponentQueries import (
    GetComponentByIdQuery,
    GetAllComponentsQuery,
)
from cell_management.domain.repositories.ComponentRepository import ComponentRepository


class ComponentQueryServiceImpl:

    def __init__(self, repository: ComponentRepository):
        self._repository = repository

    async def get_component_by_id(self, query: GetComponentByIdQuery) -> Component | None:
        return await self._repository.find_component_by_id(query.component_id)

    async def get_all_components(self, query: GetAllComponentsQuery) -> list[Component]:
        return await self._repository.find_all_components(
            component_type=query.component_type,
            cell_id=query.cell_id,
            is_active=query.is_active,
        )
