import asyncio
import logging
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import select, and_

from shared.infrastructure.persistence.configuration.database_configuration import init_db, close_db, AsyncSessionLocal
from iam.domain.model.aggregates.Role import Role
from iam.domain.model.aggregates.User import User
from iam.interface.api.rest.controllers.AuthController import router as auth_router
from iam.interface.api.rest.controllers.AdminController import router as admin_router
from iam.interface.api.rest.controllers.SignUpController import router as signup_router
from iam.interface.api.rest.controllers.AdminRegistrationController import router as admin_reg_router
from iam.interface.api.rest.controllers.PasswordResetController import router as password_reset_router

logger = logging.getLogger(__name__)

ROLES_SEED = [
    {"name": "ADMIN", "description": "Supervisor"},
    {"name": "USER", "description": "Ingeniero de Planta"},
]


async def seed_roles():
    async with AsyncSessionLocal() as session:
        for role_data in ROLES_SEED:
            result = await session.execute(
                select(Role).where(Role.name == role_data["name"])
            )
            if not result.scalar_one_or_none():
                session.add(Role(**role_data))
        await session.commit()


async def cleanup_expired_suspensions():
    """Borra cuentas cuyo expires_at ya paso. Duermen hasta el proximo vencimiento."""
    while True:
        try:
            now = datetime.now(timezone.utc)
            next_wake = now + timedelta(days=1)

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(User).where(
                        and_(User.expires_at.isnot(None), User.is_active == False)
                    )
                )
                users = list(result.scalars().all())
                deleted = 0
                earliest_future = None

                for user in users:
                    expires = user.expires_at.replace(tzinfo=timezone.utc) if user.expires_at.tzinfo is None else user.expires_at
                    if now >= expires:
                        await session.delete(user)
                        deleted += 1
                    elif earliest_future is None or expires < earliest_future:
                        earliest_future = expires

                if deleted:
                    await session.commit()
                    logger.info(f"Auto-deleted {deleted} expired user(s)")

                if earliest_future:
                    next_wake = earliest_future

            sleep_seconds = max((next_wake - datetime.now(timezone.utc)).total_seconds(), 60)
            logger.info(f"Next cleanup check in {sleep_seconds:.0f}s")
            await asyncio.sleep(sleep_seconds)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in cleanup_expired_suspensions: {e}")
            await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_roles()
    task = asyncio.create_task(cleanup_expired_suspensions())
    yield
    task.cancel()
    await close_db()


app = FastAPI(
    title="IAM Backend",
    description="Identity and Access Management API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(signup_router)
app.include_router(admin_reg_router)
app.include_router(password_reset_router)


@app.get("/")
async def root():
    return {"message": "Hello World"}
