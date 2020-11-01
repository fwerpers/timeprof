from nio import AsyncClient
import logging
import asyncio

SYNC_TIMEOUT = 10000
HOMESERVER_BASE_URL = "http://localhost:8008"
BOT_ID = "bot_id"
BOT_PW = "bot_pw"
USER_ID = "user_id"
USER_PW = "user_pw"

async def register_dummy_users():
    client = AsyncClient(HOMESERVER_BASE_URL)
    resp = await client.register(BOT_ID, BOT_PW)
    resp = await client.register(USER_ID, USER_PW)
    await client.close()

async def bot_coroutine():
    client = AsyncClient(HOMESERVER_BASE_URL, BOT_ID)
    resp = await client.login(BOT_PW)
    logging.info(resp)
    await client.sync_forever(timeout=SYNC_TIMEOUT)
    await client.close()

async def user_coroutine():
    client = AsyncClient(HOMESERVER_BASE_URL, USER_ID)
    resp = await client.login(USER_PW)
    logging.info(resp)
    await client.sync_forever(timeout=SYNC_TIMEOUT)
    await client.close()

async def main():
    await register_dummy_users()
    bot_future = asyncio.run_coroutine_threadsafe(bot_coroutine(), asyncio.get_event_loop())
    await user_coroutine()

if __name__ == "__main__":
   logging.basicConfig(level=logging.INFO)
   asyncio.get_event_loop().run_until_complete(main())
