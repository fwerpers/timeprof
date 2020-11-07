from nio import (
    AsyncClient,
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

    def login(self):
        return super().login(self.mpw)

    async def message_callback(self, room, event):
        if event.sender != self.user_id:
            logging.info(event)
        #time_now = int(round(time.time() * MS_PER_S))
        #if event.sender != self.user_id and time_now - event.server_timestamp < MSG_TIME_LIMIT_MS:
        #    logging.info(event)

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
        #resp = await self.joined_rooms()
        #logging.info(resp)
        await self.sync_forever(timeout=SYNC_TIMEOUT)
        await self.close()

class UserClient(AsyncClient):
    def __init__(self, homeserver, mid, mpw):
        super().__init__(homeserver, mid)
        self.mpw = mpw
        self.add_event_callback(self.message_callback, RoomMessageText)
        self.add_response_callback(self.sync_callback, SyncResponse)
        self.bot_room_id = None
        self.start_time = 0

    def login(self):
        self.start_time = datetime.now()
        return super().login(self.mpw)

    async def sync_callback(self, response):
        logging.info(self.start_time)
        time_now = datetime.now()
        logging.info(time_now)
        logging.info(time_now - self.start_time)
        if time_now - self.start_time > timedelta(seconds=10):
            logging.info("Closing down")
            raise asyncio.CancelledError

    async def message_callback(self, room, event):
        time_now = int(round(time.time() * MS_PER_S))
        if event.sender != self.user_id and time_now - event.server_timestamp < MSG_TIME_LIMIT_MS:
            logging.info(event)
            msg = event.body
            if msg == ASK_FOR_SAMPLE_MSG:
                await self.send_message(room.room_id, "bajsa")
            logging.info(msg)
            await self.send_message(room.room_id, "Hello from User")

    async def send_message(self, room_id, msg):
        await self.room_send(
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

    async def main(self, bot_user_id):
        resp = await self.login()
        logging.info(resp)
        resp = await self.joined_rooms()
        #logging.info(resp)
        joined_rooms = resp.rooms
        bot_room_exists = False
        for room in joined_rooms:
            joined_members = await self.joined_members(room)
            ms = set([m.display_name for m in joined_members.members])
            bot_room_exists = ms == set((BOT_ID, USER_ID))
            if bot_room_exists:
                self.bot_room_id = room
                break
        if not bot_room_exists:
            resp = await self.room_create(is_direct=True, invite=[bot_user_id])
            logging.info(resp)
            resp = await self.room_invite(resp.room_id, bot_user_id)
            logging.info(resp)
        timestamp = str(datetime.now())
        logging.info("User sending message to {}".format(self.bot_room_id))
        await self.send_message(self.bot_room_id, "Hej at {}".format(timestamp))
        await self.sync_and_close()

async def register_dummy_users():
    client = AsyncClient(HOMESERVER_BASE_URL)
    resp = await client.register(BOT_ID, BOT_PW)
    resp = await client.register(USER_ID, USER_PW)
    await client.close()

async def main():
    await register_dummy_users()
    bot_client = BotClient(HOMESERVER_BASE_URL, BOT_ID, BOT_PW)
    resp = await bot_client.login()
    logging.info(resp)
    user_client = UserClient(HOMESERVER_BASE_URL, USER_ID, USER_PW)
    bot_task = asyncio.create_task(bot_client.main())
    user_task = asyncio.create_task(user_client.main(bot_client.user_id))
    #await asyncio.gather(
    #    bot_task,
    #    user_task,
    #    return_exceptions=True
    #)
    await asyncio.wait(
        {user_task,
        bot_task},
        return_when=asyncio.FIRST_COMPLETED
    )

@pytest.fixture 
def event_loop(): 
    loop = asyncio.get_event_loop() 
    yield loop 
    loop.close()

def test_create_new_bot_room(event_loop):
    logging.basicConfig(level=logging.INFO)
    event_loop.run_until_complete(main())
    assert True

if __name__ == "__main__":
   logging.basicConfig(level=logging.INFO)
   asyncio.get_event_loop().run_until_complete(main())
