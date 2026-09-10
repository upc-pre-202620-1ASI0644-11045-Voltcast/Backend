from datetime import datetime, timezone


class DomainException(Exception):
    def __init__(self, message: str, code: str | None = None):
        self.message = message
        self.code = code or "DOMAIN_ERROR"
        super().__init__(self.message)


class EntityNotFoundException(DomainException):
    def __init__(self, entity_name: str, entity_id: int | str):
        message = f"{entity_name} with id '{entity_id}' not found"
        super().__init__(message, "ENTITY_NOT_FOUND")
        self.entity_name = entity_name
        self.entity_id = entity_id


class ValidationException(DomainException):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message, "VALIDATION_ERROR")
        self.field = field


class ConcurrencyException(DomainException):
    def __init__(self, message: str = "Entity was modified by another process"):
        super().__init__(message, "CONCURRENCY_ERROR")
