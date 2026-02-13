from motor.motor_asyncio import AsyncIOMotorClient
from config import settings


class Database:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db = self.client[settings.database_name]
        try:
            await self.db.command("ping")
            print("MongoDB ga ulandi")
        except Exception as e:
            print(f"MongoDB ulanish xatosi: {e}")

    async def close(self):
        if self.client:
            self.client.close()


db = Database()