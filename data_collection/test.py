from nio import (
    AsyncClient,
    InviteEvent,
    RoomMessageText
)
import logging
import asyncio

SYNC_TIMEOUT = 10000
HOMESERVER_BASE_URL = "http://localhost:8008"
BOT_ID = "bot_id"
BOT_PW = "bot_pw"
USER_ID = "user_id"
USER_PW = "user_pw"
BOT_START_STR = "Hello from bot"

class BotClient(AsyncClient):
    def __init__(self, homeserver, mid, mpw):
        super().__init__(homeserver, mid)
        self.mpw = mpw
        self.add_event_callback(self.autojoin_room, InviteEvent)

    def login(self):
        return super().login(self.mpw)

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

    async def sync_and_close(self):
        await self.sync_forever(timeout=SYNC_TIMEOUT)
        await self.close()

class UserClient(AsyncClient):
    def __init__(self, homeserver, mid, mpw):
        super().__init__(homeserver, mid)
        self.mpw = mpw
        self.add_event_callback(self.message_callback, RoomMessageText)

    def login(self):
        return super().login(self.mpw)

    def message_callback(self, room, event):
        logging.info(event)
        msg = event.body
        logging.info(msg)
        self.send_message(room.room_id, "Hello from User")

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

async def register_dummy_users():
    client = AsyncClient(HOMESERVER_BASE_URL)
    resp = await client.register(BOT_ID, BOT_PW)
    resp = await client.register(USER_ID, USER_PW)
    await client.close()

async def user_coroutine(bot_user_id):
    user_client = UserClient(HOMESERVER_BASE_URL, USER_ID, USER_PW)
    resp = await user_client.login()
    logging.info(resp)
    logging.info("Inviting {}".format(bot_user_id))
    resp = await user_client.joined_rooms()
    logging.info(resp)
    joined_rooms = resp.rooms
    bot_room_exists = False
    for room in joined_rooms:
        logging.info(room)
        joined_members = await user_client.joined_members(room)
        ms = set([m.display_name for m in joined_members.members])
        bot_room_exists = ms == set((BOT_ID, USER_ID))
        if bot_room_exists:
            break
    if not bot_room_exists:
        resp = await user_client.room_create(is_direct=True, invite=[bot_user_id])
        logging.info(resp)
        resp = await user_client.room_invite(resp.room_id, bot_user_id)
        logging.info(resp)
    await user_client.sync_and_close()

async def main():
    await register_dummy_users()
    bot_client = BotClient(HOMESERVER_BASE_URL, BOT_ID, BOT_PW)
    resp = await bot_client.login()
    logging.info(resp)
    #bot_future = asyncio.run_coroutine_threadsafe(bot_client.sync_and_close(), asyncio.get_event_loop())
    #user_future = asyncio.run_coroutine_threadsafe(user_coroutine(bot_client.user_id), asyncio.get_event_loop())
    bot_task = asyncio.create_task(bot_client.sync_and_close())
    user_task = asyncio.create_task(user_coroutine(bot_client.user_id))
    await asyncio.gather(
        bot_task,
        user_task
    )

if __name__ == "__main__":
   logging.basicConfig(level=logging.INFO)
   asyncio.get_event_loop().run_until_complete(main())
