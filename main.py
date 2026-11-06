import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import select

from shared.infrastructure.cache.redis_client import close_redis
from shared.infrastructure.persistence.configuration.database_configuration import init_db, close_db, AsyncSessionLocal, engine
from iam.domain.model.aggregates.Role import Role, ROLE_ADMIN, ROLE_USER
from iam.domain.model.aggregates.User import User, UserStatus
from iam.interface.api.rest.controllers.AuthController import router as auth_router
from iam.interface.api.rest.controllers.UserController import router as user_router
from cell_management.interface.api.rest.controllers.CellController import router as cell_router
from cell_management.interface.api.rest.controllers.ComponentController import router as component_router
from cell_management.infrastructure.persistence.schema_sync import sync_cell_management_schema
from dataset_management.infrastructure.persistence.schema_sync import sync_dataset_management_schema
from dataset_management.interface.api.rest.controllers.DatasetController import router as dataset_router
from voltage_forecasting.interface.api.rest.controllers.ForecastController import router as forecast_router
from voltage_forecasting.interface.api.rest.controllers.TrainingController import router as training_router
from voltage_forecasting.interface.api.rest.controllers.AlertRuleController import router as alert_rule_router
from notification_management.domain.model.aggregates.Notification import NOTIFICATION_TYPES, NotificationType
from notification_management.interface.api.rest.controllers.NotificationController import router as notification_router
# Imported so create_all also creates the tables only the Job writes to.
from voltage_forecasting.domain.model.aggregates import ModelEvaluation as _model_evaluation  # noqa: F401

logger = logging.getLogger(__name__)

ROLES_SEED = [ROLE_ADMIN, ROLE_USER]  # Supervisor, Ingeniero de Planta


async def seed_roles():
    async with AsyncSessionLocal() as session:
        for role_name in ROLES_SEED:
            result = await session.execute(select(Role).where(Role.name == role_name))
            if not result.scalars().first():
                session.add(Role(name=role_name))
        await session.commit()


async def seed_notification_types():
    async with AsyncSessionLocal() as session:
        known = set((await session.execute(select(NotificationType.type))).scalars())
        session.add_all(
            NotificationType(type=code, message=message) for code, message in NOTIFICATION_TYPES.items() if code not in known
        )
        await session.commit()


async def seed_supervisor():
    """
    Creates the first Supervisor from SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD / SEED_ADMIN_NAME,
    so the access requests of the engineers can be reviewed. Does nothing if the variables are
    not set or the account already exists.
    """
    email = os.getenv("SEED_ADMIN_EMAIL", "").lower().strip()
    password = os.getenv("SEED_ADMIN_PASSWORD", "")
    if not email or not password:
        return

    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            return
        role = (await session.execute(select(Role).where(Role.name == ROLE_ADMIN))).scalars().first()
        session.add(User(
            email=email,
            hashed_password=User.hash_password(password),
            full_name=os.getenv("SEED_ADMIN_NAME", "Supervisor"),
            role_id=role.id,
            status=UserStatus.ACTIVE,
        ))
        await session.commit()
        logger.info("Seeded the first supervisor account")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    async with engine.begin() as connection:
        await sync_cell_management_schema(connection)
        await sync_dataset_management_schema(connection)
    await seed_roles()
    await seed_notification_types()
    await seed_supervisor()
    yield
    await close_redis()
    await close_db()


app = FastAPI(
    title="VoltCast Backend",
    description="RESTful API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(cell_router)
app.include_router(component_router)
app.include_router(dataset_router)
app.include_router(forecast_router)
app.include_router(training_router)
app.include_router(alert_rule_router)
app.include_router(notification_router)


@app.get("/")
async def root():
    return {"message": "Hello World"}
