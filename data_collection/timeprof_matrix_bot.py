#!/usr/bin/python3
import asyncio
from nio import (
    AsyncClient,
    RoomMessageText,
    InviteMemberEvent,
    JoinError,
    AsyncClientConfig,
    RoomMemberEvent,
    RoomCreateEvent
)
import time
import re
import logging
import os
import numpy as np
import aiofiles
import aiofiles.os
from datetime import (datetime, timedelta)
from pathlib import Path
import json


HOMESERVER = "https://matrix.org"
BOT_USER_ID = "@timeprof_bot:matrix.org"
MSG_TIME_LIMIT_MS = 5e3
MS_PER_S = 1e3

STATE_NONE = 0
STATE_ACTIVITY_WAIT = 1
STATE_ROOM_SWITCH_WAIT = 2

PATH_TO_THIS_DIR = Path(__file__).absolute().parent
DATA_FILENAME = PATH_TO_THIS_DIR.joinpath("data.csv")
DATA_DIR = PATH_TO_THIS_DIR.joinpath("data")

#WERPERS_ROOM_ID = "!axKzwhgxJKiKiOhYrD:matrix.org"
WERPERS_ROOM_ID = "!lkPsBhWrdHbdrnJajF:matrix.org"

FWERPERS_ROOM_ID = "!RSzOBpBQRUWLcnlzmq:matrix.org"
WERPERS_USER_ID = "@werpers:matrix.org"  # if of user to interact with
FWERPERS_USER_ID = "@fwerpers:matrix.org"

JOIN_ATTEMPT_LIMIT = 3
WELCOME_STR = """Hello from TimeProf =D
Type 'help' to see available inputs"""

# TODO: add ability to get data summary
# TODO: add ability to get the csv file
# TODO: add ability to get data vis image
# TODO: set up to run on Raspberry Pi


class User():
    def __init__(self):
        self.user_id
        self.room_id
        self.poisson_process_rate
        self.next_sample_time


class DataBase():
    def __init__(self):
        if not DATA_DIR.exists():
            os.mkdir(DATA_DIR)

        self.user_data = {}

    def is_user_room_registered(self, user_id):
        """Currently a user is registered if there exists a subdirectory in the data directory with the same same and the ID of the user"""
        if self.user_data.get(user_id).get("room_id"):
            return True
        
    def is_user_registered(self, user_id):
        users = os.listdir(DATA_DIR)
        if user_id in users:
            return True
        else:
            return False

    def register_user(self, user_id, room_id):
        USER_DIR = DATA_DIR.joinpath(user_id)
        os.mkdir(USER_DIR)
        state_dict = {}
        state_dict["new_room_id"] = room_id
        self.user_data[user_id] = state_dict

    def save_user_states(self):
        state_file_path = DATA_DIR.joinpath("user_states.json")
        with open(state_file_path) as state_file:
            state_dict = json.load(state_file)
            state_dict["room_id"] = room_id
            json.dump(state_dict, state_file)

    def switch_room(self, user_id, room_id):
        pass

    def switch_to_new_room(self, user_id):
        self.user_data["room_id"] = self.user_data.get("new_room_id")

    def get_room_user(self, room_id):
        for user_id in self.user_data.keys():
            if self.user_data[user_id].get("room_id") == room_id:
                return(user_id)


class Bot():
    def __init__(self):
        pass

    async def init(self, homeserver, bot_id, bot_pw, room_id, user_id):
        client_config = AsyncClientConfig(
            max_limit_exceeded=0,
            max_timeouts=0,
            store_sync_tokens=True,
            encryption_enabled=True,
        )
        self.client = AsyncClient(
            homeserver,
            bot_id,
            ssl=True,
            device_id="matrix-niotest1235",
            store_path="./store",
            config=client_config
        )
        self.database = DataBase()
        logging.info(self.client.access_token)
        self.client.add_event_callback(self.message_callback, RoomMessageText)
        self.client.add_event_callback(self.invite_callback, InviteMemberEvent)
        self.client.add_event_callback(self.room_member_callback, RoomMemberEvent)
        self.client.add_event_callback(self.room_create_callback, RoomCreateEvent)
        await self.client.login(bot_pw)
        logging.info(self.client.access_token)
        self.state = STATE_NONE
        self.room_id = room_id
        self.user_id = user_id
        self.poisson_process_rate = 45  # minutes
        self.next_sample_time = 0  # set after user activity input
        logging.info("Initialised bot")

    async def collect_user_activity(self):
        await self.send_message("What's up?")
        self.state = STATE_ACTIVITY_WAIT

    async def propose_to_switch_room(self, user_id, room_id):
        await self.send_room_message("Hello {}, you are already registered. Want to move the conversation to this room?".format(user_id), room_id)
        self.state = STATE_ROOM_SWITCH_WAIT

    async def room_create_callback(self, room, event):
        logging.info(event)

    async def room_member_callback(self, room, event):
        logging.info(event)
        # Check if the event corresponds to the bot joining a room it was invited to
        if event.state_key == self.user_id and event.membership == "join":
            await self.send_room_message("hejhejhej", room.room_id)
            room_user = self.database.get_room_user(room.room_id)
            if self.database.is_user_room_registered(room_user):
                await self.propose_to_switch_room(room_user, room.room_id)
            else:
                self.database.switch_to_new_room(room_user)
                await self.send_room_message(WELCOME_STR, room.room_id)
                self.collect_user_activity()
                # TODO: schedule next sample
                # TODO: add handling of non-answered sample

    async def invite_callback(self, room, event):
        logging.info(event)
        logging.info(event.state_key)

        for join_attempt in range(JOIN_ATTEMPT_LIMIT):
            resp = await self.client.join(room.room_id)
            if isinstance(resp, JoinError):
                logging.info("Failed to join room {}: {}".format(room.room_id, resp.message))
            else:
                logging.info("Joined room {}".format(room.room_id))
                self.database.register_user(event.sender, room.room_id)

    def msg_event_valid(self, event):
        """ Make sure the message is from the expected user
        Make sure the message is not older than 5 seconds
        """
        ret = True
        time_now = int(round(time.time() * MS_PER_S))
        if event.sender != self.user_id:
            ret = False
        elif time_now - event.server_timestamp > MSG_TIME_LIMIT_MS:
            ret = False
        return ret

    def is_simple_phrase(self, msg):
        ret = False
        re_pattern = r"^\w+$"
        m = re.match(re_pattern, msg)
        if m is not None:
            ret = True
        return ret

    def is_activity_string(self, msg):
        ret = False
        # Match a string with white-space separated lower-case words
        re_pattern = r"^([a-z]+)(\s[a-z]+)*$"
        m = re.match(re_pattern, msg)
        if m is not None:
            ret = True
        return ret

    def save_data(self, label):
        with open(DATA_FILENAME, 'a') as f:
            timestamp = str(datetime.now())
            line = "{}, {}, {}\n".format(timestamp,
                                         label,
                                         self.poisson_process_rate)
            f.write(line)
        logging.info("Saving data '{}'".format(line))

    def set_rate(self, rate):
        self.poisson_process_rate = rate
        logging.info("Setting rate to {}".format(rate))

    async def send_help_message(self, room_id):
        # TODO: don't hardcode this
        help_str = """Available inputs:
help - this message
info - description of the bot
set rate <rate> - set rate (minutes) of sampling process. Must be an integer
get rate - get current rate
get next - get time of next sample
get data - get a download link for the data
        """
        await self.send_room_message(help_str, room_id)

    async def send_info_message(self):
        info_str = """
This is a bot to collect user activity with sampling according to a Poisson process. Every now and then it will ask what you are up to and record it. Reply with a string of whitespace separated words. To see other available input, send 'help'.
        
The data saved at each sample is the timestamp, the string provided by the user and the currently set rate of the Poisson process.
        """
        await self.send_message(info_str)

    async def send_data_summary_message(self):
        # TODO: read saved data and summarize
        # Output a table with all recorded labels
        # Total number of samples
        # Samples and percentage per label
        return False

    async def handle_help_message(self, msg, room_id):
        ret = False
        if msg == "help":
            await self.send_help_message(room_id)
            ret = True
        return ret

    async def handle_info_message(self, msg):
        ret = False
        if msg == "info":
            await self.send_info_message()
            ret = True
        return ret

    async def handle_data_summary_message(self, msg):
        ret = False
        if msg == "data summary":
            await self.send_data_summary_message()
            ret = True
        return ret

    def set_sample_rate(self, rate):
        self.poisson_process_rate = rate

    async def handle_set_rate_message(self, msg):
        ret = False
        re_pattern = r"^set rate (\d+)$"
        m = re.match(re_pattern, msg)
        if m is not None:
            rate = m.groups()[0]
            self.set_sample_rate(float(rate))
            await self.send_message("Updated rate to {}".format(rate))
            ret = True
        return ret

    async def handle_get_rate_message(self, msg):
        ret = False
        if msg == "get rate":
            response = "Current rate is {}".format(self.poisson_process_rate)
            await self.send_message(response)
            ret = True
        return ret

    async def handle_get_next_sample_time(self, msg):
        ret = False
        if msg == "get next":
            response = "Next sample scheduled for {}".format(self.next_sample_time)
            await self.send_message(response)
            ret = True
        return ret

    async def handle_get_data(self, msg):
        ret = False
        if msg == "get data":
            await self.send_data()
            ret = True
        return ret

    async def wait_until(self, dt):
        # sleep until the specified datetime
        now = datetime.now()
        await asyncio.sleep((dt - now).total_seconds())

    async def run_at(self, dt, coro):
        await self.wait_until(dt)
        return await coro

    def get_next_sample_time(self):
        time_now = datetime.now()
        interval = np.ceil(np.random.exponential(scale=self.poisson_process_rate))
        next_sample_dt = time_now + timedelta(minutes=interval)
        return next_sample_dt

    async def handle_valid_message(self, msg, user_id, room_id):
        logging.info("Handling valid message '{}'".format(msg))
        response_msg = ""
        if self.state == STATE_ACTIVITY_WAIT:
            if self.is_activity_string(msg):
                await self.send_message("Cool, I'll remember that >:)")
                self.save_data(msg)
                self.state = STATE_NONE
                loop = asyncio.get_event_loop()
                next_sample_dt = self.get_next_sample_time()
                self.next_sample_time = next_sample_dt
                loop.create_task(self.run_at(next_sample_dt, self.collect_user_activity()))
            else:
                err_str = "Expected lowercase words, not '{}'".format(msg)
                await self.send_message(err_str)
        elif self.state == STATE_ROOM_SWITCH_WAIT:
            if msg == "yes":
                self.database.switch_room(user_id, room_id)
                self.database.set_user_state(user_id, STATE_NONE)
            elif msg == "no":
                await self.send_room_message("Ok, I'm out", room_id)
                self.database.set_user_state(user_id, STATE_NONE)
                self.leave_room(room_id)
            else:
                err_str = "Expected yes or no, not '{}'".format(msg)
                await self.send_message(err_str)

        elif self.state == STATE_NONE:
            if (await self.handle_help_message(msg, room_id)):
                pass
            elif (await self.handle_info_message(msg)):
                pass
            elif (await self.handle_data_summary_message(msg)):
                pass
            elif (await self.handle_set_rate_message(msg)):
                pass
            elif (await self.handle_get_rate_message(msg)):
                pass
            elif (await self.handle_get_next_sample_time(msg)):
                pass
            elif (await self.handle_get_data(msg)):
                pass
            else:
                response_msg = "'{}' is not valid input. Send 'help' to list valid input".format(msg)
                await self.send_room_message(response_msg, room_id)

    async def message_callback(self, room, event):
        msg = event.body
        if self.msg_event_valid(event):
            await self.handle_valid_message(msg, event.sender, room.room_id)
        else:
            logging.info("Discarding message {}".format(msg))

    async def send_message(self, msg):
        await self.send_room_message(msg, self.room_id)

    async def send_room_message(self, msg, room_id):
        await self.client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": msg
            },
            ignore_unverified_devices=True
        )

    async def send_data(self):
        file_stat = await aiofiles.os.stat(DATA_FILENAME)
        async with aiofiles.open(DATA_FILENAME, "r+b") as f:
            resp, maybe_keys = await self.client.upload(
                f,
                content_type="test/plain",
                filename=DATA_FILENAME,
                filesize=file_stat.st_size
            )
        await self.client.room_send(
            room_id=self.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.file",
                "url": resp.content_uri,
                "body": "TimeProf data"
            }
        )


async def main():
    bot = Bot()
    pw = os.environ["TIMEPROF_MATRIX_PW"]
    logging.info("Initialising bot")
    await bot.init(HOMESERVER,
                   BOT_USER_ID,
                   pw,
                   FWERPERS_ROOM_ID,
                   FWERPERS_USER_ID)
    #await bot.send_message("Hello from TimeProf =D")
    #await bot.send_message("Send 'help' for possible input")
    #await bot.collect_user_activity()
    await bot.client.sync_forever(timeout=10000)
    await bot.client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.get_event_loop().run_until_complete(main())
