""" Consider this experimental.

The aim is to create high-level tests.

Currently the bot client and a user client is run in two asyncio tasks.
The passing condition is that an asyncio event is set by the user client task
"""

from nio import (
    Api,
    AsyncClient,
    AsyncClientConfig,
    InviteEvent,
    RoomMessageText,
    SyncResponse
)
import logging
import asyncio
from datetime import (
    datetime,
    timedelta
)
import time
import pytest
from timeprof_matrix_bot import TimeProfBot
from timeprof_matrix_bot import WELCOME_STR
from timeprof_matrix_bot import INFO_STR

SYNC_TIMEOUT = 10000
HOMESERVER_BASE_URL = "http://localhost:8008"
BOT_ID = "bot_id"
BOT_PW = "bot_pw"
USER_ID = "user_id"
USER_PW = "user_pw"
BOT_START_STR = "Hello from bot"
MSG_TIME_LIMIT_MS = 5e3
MS_PER_S = 1e3

class BotClient(AsyncClient):
    def __init__(self, homeserver, mid, mpw):
        super().__init__(homeserver, mid)
        self.mpw = mpw
        self.add_event_callback(self.autojoin_room, InviteEvent)
        self.add_event_callback(self.message_callback, RoomMessageText)
        logging.info("BotClient initialised")

    def login(self):
        return super().login(self.mpw)

    async def message_callback(self, room, event):
        if event.sender != self.user_id:
            logging.info(event)
            await self.send_message(room.room_id, "Response from BotClient")

    async def autojoin_room(self, room, event):
        logging.info(event)
        logging.info("Got room invite")
        resp = await self.join(room.room_id)
        logging.info(resp)
        resp = await self.send_message(room.room_id, BOT_START_STR)
        logging.info(resp)

    async def send_message(self, room_id, msg):
        await self.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": msg
            }
        )

    async def main(self):
        await self.sync_forever(timeout=SYNC_TIMEOUT)
        await self.close()

class UserClient(AsyncClient):
    def __init__(self, homeserver, mid, mpw, bot_id, pass_event):
        super().__init__(homeserver, mid)
        self.mpw = mpw
        self.add_event_callback(self.message_callback, RoomMessageText)
        self.add_response_callback(self.sync_callback, SyncResponse)
        self.bot_room_id = None
        self.bot_id = bot_id
        self.pass_event = pass_event

    async def sync_callback(self, response):
        if self.pass_event.is_set():
            raise asyncio.CancelledError

    async def message_callback(self, room, event):
        raise NotImplementedError

    async def send_message(self, room_id, msg):
        return await self.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": msg
            }
        )

    async def sync_and_close(self):
        await self.sync_forever(timeout=SYNC_TIMEOUT)
        await self.close()

    async def bot_room_exists(self):
        resp = await self.joined_rooms()
        joined_rooms = resp.rooms
        bot_room_exists = False
        for room in joined_rooms:
            joined_members = await self.joined_members(room)
            logging.info(joined_members)
            ms = set([m.display_name for m in joined_members.members])
            #bot_room_exists = ms == set((BOT_ID, USER_ID))
            #bot_room_exists = ms == set(("@bot_id:my.domain.name", USER_ID))
            if bot_room_exists:
                self.bot_room_id = room
                break
        return bot_room_exists

class InfoMessageUserClient(UserClient):
    def __init__(self, homeserver, mid, mpw, bot_id, pass_event):
        super().__init__(homeserver, mid, mpw, bot_id, pass_event)

    async def message_callback(self, room, event):
        time_now = int(round(time.time() * MS_PER_S))
        if event.sender != self.user_id and time_now - event.server_timestamp < MSG_TIME_LIMIT_MS:
            msg = event.body
            if msg == INFO_STR:
                self.pass_event.set()

    async def main(self, bot_id):
        resp = await self.login(self.mpw)
        bot_room_exists = await self.bot_room_exists()
        if not bot_room_exists:
            resp = await self.room_create(is_direct=True, invite=[bot_id])
            logging.info(resp)
            self.bot_room_id = resp.room_id
        
        resp = await self.send_message(self.bot_room_id, "info")
        logging.info(resp)
        await self.sync_and_close()

async def register_dummy_users():
    client_config = AsyncClientConfig(max_timeouts=1)
    client = AsyncClient(HOMESERVER_BASE_URL, config=client_config)
    resp = await client.register(BOT_ID, BOT_PW)
    logging.info(resp)
    resp = await client.register(USER_ID, USER_PW)
    logging.info(resp)
    await client.close()

async def run_bots(user_client):
    """ This function assumes that a homeserver is running at HOMESERVER_BASE_URL
    and that it's configured with enable_registration set to true
    
    This function is meant to be re-used for different user sequences, defined by the user_client argument
    """
    logging.info("Registering dummy users...")
    await register_dummy_users()
    bot_client = TimeProfBot(HOMESERVER_BASE_URL, BOT_ID, BOT_PW)
    await bot_client.init(leave_all_rooms=True)
    logging.info(bot_client.user_id)
    #logging.info(resp)
    bot_task = asyncio.create_task(bot_client.main())
    user_task = asyncio.create_task(user_client.main(bot_client.user_id))
    done, pending = await asyncio.wait(
        {user_task,
        bot_task},
        return_when=asyncio.FIRST_COMPLETED,
        timeout=10
    )
    for t in pending:
        t.cancel()
    print(user_client)
    await user_client.close()
    await bot_client.close()
    return user_client.pass_event.is_set()

@pytest.fixture 
def event_loop(scope="module"): 
    loop = asyncio.get_event_loop() 
    return loop
    #yield loop 
    #loop.close()

def test_info_message():
    event_loop = asyncio.get_event_loop()
    logging.basicConfig(level=logging.INFO)
    user_event = asyncio.Event()
    user_client = InfoMessageUserClient(HOMESERVER_BASE_URL, USER_ID, USER_PW, BOT_ID, user_event)
    done = event_loop.run_until_complete(run_bots(user_client))
    logging.info(done)
    assert done 

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_info_message()
