from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient

from config import settings


def _mask_mongo_uri(uri: str) -> str:
    # mongodb+srv://user:pass@host/...  -> mask pass
    try:
        if "@" not in uri or "://" not in uri:
            return uri
        scheme, rest = uri.split("://", 1)
        if "@" not in rest:
            return uri
        creds, tail = rest.split("@", 1)
        if ":" in creds:
            user, _ = creds.split(":", 1)
            return f"{scheme}://{user}:***@{tail}"
        return uri
    except Exception:
        return uri


class Database:
    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.db = None
        self.ads = None

    async def connect(self):
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db = self.client[settings.database_name]
        self.ads = self.db[settings.ads_collection]

        # ping
        await self.db.command("ping")

        print(
            "MongoDB ulandi | URI:",
            _mask_mongo_uri(settings.mongodb_uri),
            "| DB:",
            settings.database_name,
            "| Collection:",
            settings.ads_collection,
        )

        # duplicate oldini olish uchun unique index
        # background=True - eskirgan pymongo opsiyasi bo'lishi mumkin; motor/pymongo o'zi fon rejimida yaratadi
        await self.ads.create_index([("link", 1)], unique=True, name="uniq_link")
        print("Index tekshirildi/yaratildi: uniq_link (link UNIQUE)")

    async def close(self):
        if self.client:
            self.client.close()


db = Database()
