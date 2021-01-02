from nio import (
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

SYNC_TIMEOUT = 10000
HOMESERVER_BASE_URL = "http://localhost:8008"
BOT_ID = "bot_id"
BOT_PW = "bot_pw"
USER_ID = "user_id"
USER_PW = "user_pw"
BOT_START_STR = "Hello from bot"
MSG_TIME_LIMIT_MS = 5e3
MS_PER_S = 1e3
ASK_FOR_SAMPLE_MSG = ""

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
    def __init__(self, homeserver, mid, mpw, bot_id, pass_event):
        super().__init__(homeserver, mid)
        self.mpw = mpw
        self.add_event_callback(self.message_callback, RoomMessageText)
        self.add_response_callback(self.sync_callback, SyncResponse)
        self.bot_room_id = None
        self.start_time = 0
        self.bot_id = bot_id
        self.pass_event = pass_event

    def login(self):
        self.start_time = datetime.now()
        return super().login(self.mpw)

    async def sync_callback(self, response):
        logging.info(self.start_time)
        time_now = datetime.now()
        logging.info(time_now)
        logging.info(time_now - self.start_time)
        #if time_now - self.start_time > timedelta(seconds=10):
            #logging.info("UserClient closing down")
            #raise asyncio.CancelledError

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

    async def main(self):
        resp = await self.login()
        logging.info(resp)
        self.pass_event.set()
        self.close()
        raise asyncio.CancelledError
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
            resp = await self.room_create(is_direct=True, invite=[self.bot_id])
            logging.info(resp)
            resp = await self.room_invite(resp.room_id, self.bot_id)
            logging.info(resp)
        timestamp = str(datetime.now())
        logging.info("User sending message to {}".format(self.bot_room_id))
        await self.send_message(self.bot_room_id, "Hej at {}".format(timestamp))
        await self.sync_and_close()

async def register_dummy_users():
    client_config = AsyncClientConfig(max_timeouts=1)
    client = AsyncClient(HOMESERVER_BASE_URL, config=client_config)
    resp = await client.register(BOT_ID, BOT_PW)
    logging.info(resp)
    resp = await client.register(USER_ID, USER_PW)
    logging.info(resp)
    await client.close()

async def run_bots():
    """ This function assumes that a homeserver is running at HOMESERVER_BASE_URL
    and that it's configured with enable_registration set to true
    """
    logging.info("Registering dummy users...")
    await register_dummy_users()
    bot_client = BotClient(HOMESERVER_BASE_URL, BOT_ID, BOT_PW)
    resp = await bot_client.login()
    logging.info(resp)
    user_event = asyncio.Event()
    user_client = UserClient(HOMESERVER_BASE_URL, USER_ID, USER_PW, BOT_ID, user_event)
    bot_task = asyncio.create_task(bot_client.main())
    user_task = asyncio.create_task(user_client.main())
    done, pending = await asyncio.wait(
        {user_task,
        bot_task},
        return_when=asyncio.FIRST_COMPLETED,
        timeout=10
    )
    for t in pending:
        t.cancel()
    await user_client.close()
    await bot_client.close()
    return user_event.is_set()

async def run_bots2(user_main):
    """ This function assumes that a homeserver is running at HOMESERVER_BASE_URL
    and that it's configured with enable_registration set to true
    
    This function is meant to be re-used for different user sequences, defined by the user_main argument
    """
    logging.info("Registering dummy users...")
    await register_dummy_users()
    bot_client = BotClient(HOMESERVER_BASE_URL, BOT_ID, BOT_PW)
    resp = await bot_client.login()
    #bot_client = TimeProfBot()
    #await bot_client.init(HOMESERVER_BASE_URL,
                   #BOT_ID,
                   #BOT_PW,
                   #leave_all_rooms=True)
    #logging.info(resp)
    user_event = asyncio.Event()
    user_client = UserClient(HOMESERVER_BASE_URL, USER_ID, USER_PW, BOT_ID, user_event)
    bot_task = asyncio.create_task(bot_client.main())
    user_event = asyncio.Event()
    user_task = asyncio.create_task(user_main(user_client))
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
    #return user_event.is_set()

@pytest.fixture 
def event_loop(scope="module"): 
    loop = asyncio.get_event_loop() 
    return loop
    #yield loop 
    #loop.close()

def event_loop2():
    loop = asyncio.get_event_loop() 
    yield loop 
    loop.close()

#def test_create_new_bot_room(event_loop):
    #logging.basicConfig(level=logging.INFO)
    #done = event_loop.run_until_complete(run_bots())
    #logging.info(done)
    #assert done 
    ##assert False
    ##assert True 

#def test_create_new_bot_room2(event_loop):
    #logging.basicConfig(level=logging.INFO)
    #done = event_loop.run_until_complete(run_bots())
    #logging.info(done)
    #assert done 
    ##assert False
    ##assert True 

async def boot_room_exists(uc):
    resp = await uc.joined_rooms()
    #logging.info(resp)
    joined_rooms = resp.rooms
    bot_room_exists = False
    for room in joined_rooms:
        joined_members = await uc.joined_members(room)
        ms = set([m.display_name for m in joined_members.members])
        bot_room_exists = ms == set((BOT_ID, USER_ID))
        if bot_room_exists:
            uc.bot_room_id = room
            break
    
async def async_test_help_message(uc):
    print(uc)
    resp = await uc.login()
    logging.info(resp)
    print(uc)
    uc.pass_event.set()
    raise asyncio.CancelledError
    bot_room_exists = await bot_room_exists(uc)
    if not bot_room_exists:
        resp = await uc.room_create(is_direct=True, invite=[uc.bot_id])
        logging.info(resp)
        resp = await uc.room_invite(resp.room_id, uc.bot_id)
        logging.info(resp)
    timestamp = str(datetime.now())
    logging.info("User sending message to {}".format(uc.bot_room_id))
    await uc.send_message(uc.bot_room_id, "Hej at {}".format(timestamp))
    await uc.sync_and_close()
    
def test_help_message(event_loop):
    logging.basicConfig(level=logging.INFO)
    done = event_loop.run_until_complete(run_bots2(async_test_help_message))
    logging.info(done)
    assert done 

def main2():
    loop = event_loop2()
    next(loop).run_until_complete(run_bots())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main2()
    #asyncio.get_event_loop().run_until_complete(run_bots())
