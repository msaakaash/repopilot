from app.db.database import engine
from app.db.models import Base
async def init_db():
    async with engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)
