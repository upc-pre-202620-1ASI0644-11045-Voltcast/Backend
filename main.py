import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import select

from shared.infrastructure.persistence.configuration.database_configuration import init_db, close_db, AsyncSessionLocal
from iam.domain.model.aggregates.Role import Role, ROLE_ADMIN, ROLE_USER
from iam.domain.model.aggregates.User import User, UserStatus
from iam.interface.api.rest.controllers.AuthController import router as auth_router
from iam.interface.api.rest.controllers.UserController import router as user_router
from cell_management.interface.api.rest.controllers.CellController import router as cell_router
from cell_management.interface.api.rest.controllers.ComponentController import router as component_router

logger = logging.getLogger(__name__)

ROLES_SEED = [ROLE_ADMIN, ROLE_USER]  # Supervisor, Ingeniero de Planta


async def seed_roles():
    async with AsyncSessionLocal() as session:
        for role_name in ROLES_SEED:
            result = await session.execute(select(Role).where(Role.name == role_name))
            if not result.scalars().first():
                session.add(Role(name=role_name))
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
    await seed_roles()
    await seed_supervisor()
    yield
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


@app.get("/")
async def root():
    return {"message": "Hello World"}
