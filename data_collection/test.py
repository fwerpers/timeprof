from nio import AsyncClient
import logging
import asyncio

SYNC_TIMEOUT = 10000
HOMESERVER_BASE_URL = "http://localhost:8008"
BOT_ID = "bot_id"
BOT_PW = "bot_pw"
USER_ID = "user_id"
USER_PW = "user_pw"

class BotClient(AsyncClient):
    def __init__(self, homeserver, mid, mpw):
        super().__init__(homeserver, mid)
        self.mpw = mpw

    def login(self):
        return super().login(self.mpw)

    async def sync_and_close(self):
        await self.sync_forever(timeout=SYNC_TIMEOUT)
        await self.close()

class UserClient(AsyncClient):
    def __init__(self, homeserver, mid, mpw):
        super().__init__(homeserver, mid)
        self.mpw = mpw

    def login(self):
        return super().login(self.mpw)

    async def sync_and_close(self):
        await self.sync_forever(timeout=SYNC_TIMEOUT)
        await self.close()

async def register_dummy_users():
    client = AsyncClient(HOMESERVER_BASE_URL)
    resp = await client.register(BOT_ID, BOT_PW)
    resp = await client.register(USER_ID, USER_PW)
    await client.close()

async def user_coroutine():
    user_client = UserClient(HOMESERVER_BASE_URL, USER_ID, USER_PW)
    resp = await user_client.login()
    logging.info(resp)
    await user_client.sync_and_close()

async def main():
    await register_dummy_users()
    bot_client = BotClient(HOMESERVER_BASE_URL, BOT_ID, BOT_PW)
    resp = await bot_client.login()
    logging.info(resp)
    bot_future = asyncio.run_coroutine_threadsafe(bot_client.sync_and_close(), asyncio.get_event_loop())
    await user_coroutine()

if __name__ == "__main__":
   logging.basicConfig(level=logging.INFO)
   asyncio.get_event_loop().run_until_complete(main())
