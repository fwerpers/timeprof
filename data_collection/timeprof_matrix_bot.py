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

KEY_STATE = "state"
KEY_NEW_ROOM = "new_room_id"
KEY_ROOM = "room_id"
KEY_RATE = "poisson_process_rate"
KEY_NEXT_SAMPLE_TIME = "next_sample_time"

PATH_TO_THIS_DIR = Path(__file__).absolute().parent
DATA_DIR = PATH_TO_THIS_DIR.joinpath("data")
USER_STATES_PATH = DATA_DIR.joinpath("user_states.json")

JOIN_ATTEMPT_LIMIT = 3
WELCOME_STR = """Hello from TimeProf =D
Type 'help' to see available inputs"""

# TODO: should be bot nofity each user when it shuts down and when it starts?
# TODO: add ability to get data summary
# TODO: add ability to get data vis image
# TODO: set up to run on Raspberry Pi
# TODO: decide when to save the user state data to disk and implement it
# TODO: load the saved user state data at init. Make sure the room switch sequence works as intended
# TODO: add handling of non-answered sample
# TODO: continuously re-reschedule sampling


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
        if self.user_data.get(user_id).get(KEY_ROOM):
            return True
        else:
            return False

    def is_user_registered(self, user_id):
        return user_id in self.user_data.keys()

    def register_user(self, user_id, room_id):
        user_dict = {}
        user_dict[KEY_NEW_ROOM] = room_id
        user_dict[KEY_RATE] = 45.0
        self.user_data[user_id] = user_dict
        logging.info("Registered user {},{}".format(user_id, user_dict))

    def save_user_states(self):
        with open(USER_STATES_PATH, 'w') as fp:
            json.dump(self.user_data, fp)

    def load_user_states(self):
        with open(USER_STATES_PATH, 'r') as fp:
            self.user_data = json.load(fp)

    def switch_to_new_room(self, user_id):
        new_room_id = self.user_data.get(user_id).get(KEY_NEW_ROOM)
        self.user_data[user_id][KEY_ROOM] = new_room_id

    def get_room_user(self, room_id):
        for user_id in self.user_data.keys():
            if self.user_data[user_id].get(KEY_ROOM) == room_id:
                return(user_id)

    def get_new_room_user(self, room_id):
        for user_id in self.user_data.keys():
            if self.user_data[user_id].get(KEY_NEW_ROOM) == room_id:
                return(user_id)

    def set_user_state(self, user_id, state):
        self.user_data[user_id][KEY_STATE] = state

    def get_user_state(self, user_id):
        return self.user_data.get(user_id).get(KEY_STATE)

    def get_user_file_path(self, user_id):
        user_file_path = DATA_DIR.joinpath("{}.csv".format(user_id))
        return user_file_path

    def get_rate(self, user_id):
        logging.info(self.user_data)
        return self.user_data.get(user_id).get(KEY_RATE)

    def set_rate(self, user_id, rate):
        self.user_data[user_id][KEY_RATE] = rate

    def save_data(self, user_id, label):
        user_file_path = self.get_user_file_path(user_id)
        with open(user_file_path, 'a') as f:
            # TODO: use time when question was asked instead?
            timestamp = str(datetime.now())
            poisson_process_rate = self.user_data.get(user_id).get(KEY_RATE)
            line_format_str = "{}, {}, {}\n"
            line = line_format_str.format(timestamp,
                                          label,
                                          poisson_process_rate)
            f.write(line)
        logging.info("Saving data '{}' to {}".format(line, user_file_path))

    def get_next_sample_time(self, user_id):
        return self.user_data.get(user_id).get(KEY_NEXT_SAMPLE_TIME)

    def set_next_sample_time(self, user_id, next_sample_time):
        self.user_data[user_id][KEY_NEXT_SAMPLE_TIME] = next_sample_time


class Bot():
    def __init__(self):
        pass

    async def init(self, homeserver, bot_id, bot_pw):
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
        await self.client.login(bot_pw)
        self.client.add_event_callback(self.message_callback, RoomMessageText)
        self.client.add_event_callback(self.invite_callback, InviteMemberEvent)
        self.client.add_event_callback(self.room_member_callback, RoomMemberEvent)
        self.client.add_event_callback(self.room_create_callback, RoomCreateEvent)
        logging.info("Initialised bot")

    async def collect_user_activity(self, user_id, room_id):
        await self.send_room_message("What's up?", room_id)
        self.database.set_user_state(user_id, STATE_ACTIVITY_WAIT)

    async def propose_to_switch_room(self, user_id, room_id):
        resp = "Hello {}, you are already registered. Want to move the conversation to this room?".format(user_id)
        await self.send_room_message(resp, room_id)
        self.database.set_user_state(user_id, STATE_ROOM_SWITCH_WAIT)

    async def room_create_callback(self, room, event):
        logging.info(event)
        await self.handle_room_join(room.room_id)

    async def handle_room_join(self, room_id):
        room_user = self.database.get_new_room_user(room_id)
        if self.database.is_user_room_registered(room_user):
            logging.info("User {} already registered with room {}".format(room_user, room_id))
            await self.propose_to_switch_room(room_user, room_id)
        else:
            self.database.switch_to_new_room(room_user)
            await self.send_room_message(WELCOME_STR, room_id)
            await self.collect_user_activity(room_user, room_id)

    async def room_member_callback(self, room, event):
        if event.membership == "leave":
            logging.info(self.database.user_data)
            user_id = self.database.get_room_user(room.room_id)
            if event.state_key == user_id:
                logging.info("Leaving room {}".format(room.room_id))
                await self.client.room_leave(room.room_id)
        # Did the bot join a new room?
        elif event.state_key == self.client.user_id and event.membership == "join":
            # Apparently this can happen more than once after joining a room
            logging.info(event.content)
            logging.info(await self.client.joined_rooms())

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
                break

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

    async def send_info_message(self, room_id):
        info_str = """
This is a bot to collect user activity with sampling according to a Poisson process. Every now and then it will ask what you are up to and record it. Reply with a string of whitespace separated words. To see other available input, send 'help'.
        
The data saved at each sample is the timestamp, the string provided by the user and the currently set rate of the Poisson process.

Currently maintained at https://github.com/fwerpers/timeprof.
        """
        await self.send_room_message(info_str, room_id)

    async def send_data_summary_message(self, room_id):
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

    async def handle_info_message(self, msg, room_id):
        ret = False
        if msg == "info":
            await self.send_info_message(room_id)
            ret = True
        return ret

    async def handle_data_summary_message(self, msg, room_id):
        ret = False
        if msg == "data summary":
            await self.send_data_summary_message(room_id)
            ret = True
        return ret

    async def handle_set_rate_message(self, msg, room_id):
        ret = False
        re_pattern = r"^set rate (\d+)$"
        m = re.match(re_pattern, msg)
        if m is not None:
            rate = m.groups()[0]
            user_id = self.database.get_room_user(room_id)
            self.database.set_rate(user_id, float(rate))
            resp = "Updated rate to {}".format(rate)
            await self.send_room_message(resp, room_id)
            ret = True
        return ret

    async def handle_get_rate_message(self, msg, room_id):
        ret = False
        if msg == "get rate":
            user_id = self.database.get_room_user(room_id)
            rate = self.database.get_rate(user_id)
            response = "Current rate is {}".format(rate)
            await self.send_room_message(response, room_id)
            ret = True
        return ret

    async def handle_get_next_sample_time(self, msg, room_id):
        ret = False
        if msg == "get next":
            user_id = self.database.get_room_user(room_id)
            next_sample_time = self.database.get_next_sample_time(user_id)
            response = "Next sample scheduled for {}".format(next_sample_time)
            await self.send_room_message(response, room_id)
            ret = True
        return ret

    async def handle_get_data(self, msg, room_id):
        ret = False
        if msg == "get data":
            await self.send_data(room_id)
            ret = True
        return ret

    async def wait_until(self, dt):
        # sleep until the specified datetime
        now = datetime.now()
        await asyncio.sleep((dt - now).total_seconds())

    async def run_at(self, dt, coro):
        await self.wait_until(dt)
        return await coro

    def get_next_sample_time(self, rate):
        time_now = datetime.now()
        interval = np.ceil(np.random.exponential(scale=rate))
        next_sample_dt = time_now + timedelta(minutes=interval)
        return next_sample_dt

    async def handle_activity_message(self, msg, user_id, room_id):
        if self.is_activity_string(msg):
            resp = "Cool, I'll remember that >:)"
            await self.send_room_message(resp, room_id)
            self.database.save_data(user_id, msg)
            self.database.set_user_state(user_id, STATE_NONE)
            loop = asyncio.get_event_loop()
            rate = self.database.get_rate(user_id)
            next_sample_dt = self.get_next_sample_time(rate)
            self.database.set_next_sample_time(user_id, next_sample_dt)
            loop.create_task(self.run_at(next_sample_dt, self.collect_user_activity(user_id, room_id)))
        else:
            err_str = "Expected lowercase words, not '{}'".format(msg)
            await self.send_room_message(err_str, room_id)

    async def handle_room_switch_message(self, msg, user_id, room_id):
        if msg == "yes":
            self.database.switch_to_new_room(user_id, room_id)
            self.database.set_user_state(user_id, STATE_NONE)
        elif msg == "no":
            await self.send_room_message("Ok, I'm out", room_id)
            self.database.set_user_state(user_id, STATE_NONE)
            self.leave_room(room_id)
        else:
            err_str = "Expected yes or no, not '{}'".format(msg)
            await self.send_room_message(err_str, room_id)

    async def handle_command(self, msg, room_id):
        if (await self.handle_help_message(msg, room_id)):
            pass
        elif (await self.handle_info_message(msg, room_id)):
            pass
        elif (await self.handle_data_summary_message(msg, room_id)):
            pass
        elif (await self.handle_set_rate_message(msg, room_id)):
            pass
        elif (await self.handle_get_rate_message(msg, room_id)):
            pass
        elif (await self.handle_get_next_sample_time(msg, room_id)):
            pass
        elif (await self.handle_get_data(msg, room_id)):
            pass
        else:
            response_msg = "'{}' is not valid input. Send 'help' to list valid input".format(msg)
            await self.send_room_message(response_msg, room_id)

    async def handle_message(self, msg, user_id, room_id):
        logging.info("Handling valid message '{}'".format(msg))
        state = self.database.get_user_state(user_id)
        if state == STATE_ACTIVITY_WAIT:
            await self.handle_activity_message(msg, user_id, room_id)
        elif state == STATE_ROOM_SWITCH_WAIT:
            await self.handle_room_switch_message(msg, user_id, room_id)
        elif state == STATE_NONE:
            await self.handle_command(msg, room_id)

    async def message_callback(self, room, event):
        try:
            msg = event.body
            if self.database.is_user_registered(event.sender):
                await self.handle_message(msg, event.sender, room.room_id)
            else:
                logging.info("Discarding message {}".format(msg))
        except:
            resp = "Sorry, there was en error. Contact the developer :("
            await self.send_room_message(resp, room.room_id)
            raise

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

    async def send_data(self, room_id):
        user_id = self.database.get_room_user(room_id)
        file_path = self.database.get_user_file_path(user_id)
        file_stat = await aiofiles.os.stat(file_path)
        async with aiofiles.open(file_path, "r+b") as f:
            resp, maybe_keys = await self.client.upload(
                f,
                content_type="test/plain",
                filename=file_path,
                filesize=file_stat.st_size
            )
        await self.client.room_send(
            room_id=room_id,
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
                   pw)
    await bot.client.sync_forever(timeout=10000)
    await bot.client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.get_event_loop().run_until_complete(main())
