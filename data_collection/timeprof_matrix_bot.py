#!/usr/bin/python3
import asyncio
from nio import (
    AsyncClient,
    RoomMessageText,
    InviteMemberEvent,
    JoinError,
    AsyncClientConfig,
    RoomMemberEvent,
    RoomCreateEvent,
    RoomLeaveError
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
import copy

from argparse_test import (NonExitingArgParser, ArgumentException)
from csv_test import (get_csv_context, get_last_csv_context)

HOMESERVER = "https://matrix.org"
BOT_USER_ID = "@timeprof_bot:matrix.org"

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
LEAVE_ROOM_ATTEMPT_LIMIT = 10
WELCOME_STR = """Hello from TimeProf =D
Type 'help' to see available inputs"""


INFO_STR = """
This is a bot to collect user activity with sampling according to a Poisson process. Every now and then it will ask what you are up to and record it. Reply with a string of whitespace separated words. To see other available input, send 'help'.

The data saved at each sample is the timestamp, the string provided by the user and the currently set rate of the Poisson process.

Currently maintained at https://github.com/fwerpers/timeprof.
        """

# TODO: add ability to get data summary
# TODO: add ability to get data vis image
# TODO: user csv package to save the data
# TODO: what happens if the bot is in both room switch and activity wait state for a user?

class Argument():
    def __init__(self, name, regex):
        self.name = name
        self.regex = regex

class Command():
    def __init__(self, name, func, help_str):
        self.name = name
        self.func = func
        self.args = []
        self.help_str = help_str
        self.arg_parser = NonExitingArgParser(prog=name, add_help=False)

    def add_help_entry(self, help_str):
        self.help_str = help_str

    def get_help_entry(self):
        return self.help_str

    def is_simple_command(self):
        if len(self.args) > 0:
            return False
        else:
            return True

    async def __call__(self, msg, room_id):
        return await self.func(msg, room_id)

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
        if self.get_room(user_id):
            return True
        else:
            return False

    def is_user_registered(self, user_id):
        return user_id in self.user_data.keys()

    def is_user_registered(self, user_id):
        return user_id in self.user_data

    def register_user(self, user_id):
        user_dict = {}
        user_dict[KEY_NEW_ROOM] = None
        user_dict[KEY_RATE] = 45.0
        user_dict[KEY_NEXT_SAMPLE_TIME] = None
        user_dict[KEY_STATE] = STATE_NONE
        self.user_data[user_id] = user_dict
        logging.info("Registered user {},{}".format(user_id, user_dict))

    def add_new_room(self, user_id, room_id):
        self.user_data[user_id][KEY_NEW_ROOM] = room_id

    def save_user_states(self):
        with open(USER_STATES_PATH, 'w') as fp:
            user_data_str = copy.deepcopy(self.user_data)
            for user_id in user_data_str.keys():
                logging.info(self.get_next_sample_time(user_id))
                user_data_str[user_id][KEY_NEXT_SAMPLE_TIME] = self.get_next_sample_time(user_id).isoformat()
            json.dump(user_data_str, fp)

    def load_user_states(self):
        if USER_STATES_PATH.exists():
            with open(USER_STATES_PATH, 'r') as fp:
                user_data_str = json.load(fp)
                self.user_data = copy.deepcopy(user_data_str)
                for user_id in self.user_data.keys():
                    self.set_next_sample_time(
                        user_id,
                        datetime.fromisoformat(user_data_str[user_id][KEY_NEXT_SAMPLE_TIME]))

    def switch_to_new_room(self, user_id):
        new_room_id = self.user_data.get(user_id).get(KEY_NEW_ROOM)
        self.user_data[user_id][KEY_ROOM] = new_room_id

    def get_room_user(self, room_id):
        for user_id in self.user_data.keys():
            if self.get_room(user_id) == room_id:
                return(user_id)

    def unregister_user(self, user_id):
        self.user_data.pop(user_id, None)
        self.save_user_states()

    def get_room(self, user_id):
        room_id = self.user_data[user_id].get(KEY_ROOM)
        return room_id

    def get_new_room_user(self, room_id):
        for user_id in self.user_data.keys():
            if self.user_data[user_id].get(KEY_NEW_ROOM) == room_id:
                return(user_id)

    def get_user_state(self, user_id):
        return self.user_data.get(user_id).get(KEY_STATE)

    def set_user_state(self, user_id, state):
        self.user_data[user_id][KEY_STATE] = state
        self.save_user_states()

    def get_user_file_path(self, user_id):
        user_file_path = DATA_DIR.joinpath("{}.csv".format(user_id))
        return user_file_path

    def get_rate(self, user_id):
        logging.info(self.user_data)
        return self.user_data.get(user_id).get(KEY_RATE)

    def set_rate(self, user_id, rate):
        self.user_data[user_id][KEY_RATE] = rate
        self.save_user_states()

    def save_sample(self, user_id, sample_time, label):
        user_file_path = self.get_user_file_path(user_id)
        with open(user_file_path, 'a') as f:
            # TODO: use time when question was asked instead?
            timestamp = str(sample_time)
            poisson_process_rate = self.user_data.get(user_id).get(KEY_RATE)
            line_format_str = "{}, {}, {}\n"
            line = line_format_str.format(timestamp,
                                          label,
                                          poisson_process_rate)
            f.write(line)
        logging.info("Saving data '{}' to {}".format(line, user_file_path))

    def get_next_sample_time(self, user_id):
        next_sample_time = self.user_data.get(user_id).get(KEY_NEXT_SAMPLE_TIME)
        assert isinstance(next_sample_time, datetime), "{}".format(type(next_sample_time))
        return next_sample_time

    def set_next_sample_time(self, user_id, next_sample_time):
        assert isinstance(next_sample_time, datetime)
        self.user_data[user_id][KEY_NEXT_SAMPLE_TIME] = next_sample_time
        logging.info(type(next_sample_time))
        self.save_user_states()


class TimeProfBot(AsyncClient):
    def __init__(self, homeserver, mid, bot_pw):
        self.bot_pw = bot_pw
        client_config = AsyncClientConfig(
            max_limit_exceeded=0,
            max_timeouts=0,
            store_sync_tokens=True,
            encryption_enabled=True,
        )
        super().__init__(
            homeserver,
            mid,
            ssl=True,
            device_id="matrix-niotest1235",
            store_path="./store",
            config=client_config
        )

    async def init(self, leave_all_rooms=False):
        self.database = DataBase()
        self.database.load_user_states()
        self.sync_next_sample_times()
        resp = await self.login(self.bot_pw)
        logging.info(resp)
        await self.log_joined_rooms()
        if leave_all_rooms:
            await self.leave_all_rooms()
        self.add_commands()
        self.add_event_callback(self.message_callback, RoomMessageText)
        self.add_event_callback(self.invite_callback, InviteMemberEvent)
        self.add_event_callback(self.room_member_callback, RoomMemberEvent)
        self.add_event_callback(self.room_create_callback, RoomCreateEvent)
        logging.info("Initialised bot")

    def add_commands(self):
        self.commands = [
            Command("help", self.handle_help_message, "list commands (this message)"),
            Command("info", self.handle_info_message, "info about the bot"),
            Command("get data", self.handle_get_data, "get a download link for the data"),
            Command("get next", self.handle_get_next_sample_time, "get time of next sample"),
            Command("get rate", self.handle_get_rate_message, "get current rate")
        ]
        set_rate_cmd = Command("set rate", self.handle_set_rate_message, "set rate (minutes) of sampling process")
        set_rate_cmd.arg_parser.add_argument("rate", type=float)
        self.commands.append(set_rate_cmd)
        get_history_cmd = Command("get history", self.handle_get_history, "get activity history")
        get_history_cmd.arg_parser.add_argument("-i", dest="line", type=int)
        get_history_cmd.arg_parser.add_argument("-n", dest="size", type=int, default=10)
        self.commands.append(get_history_cmd)

    async def log_joined_rooms(self):
        joined_rooms_resp = await self.joined_rooms()
        logging.info(joined_rooms_resp)

    async def leave_all_rooms(self):
        joined_rooms_resp = await self.joined_rooms()
        for room_id in joined_rooms_resp.rooms:
            room_user = self.database.get_room_user(room_id)
            self.database.unregister_user(room_user)
            logging.info("Leaving room {}".format(room_id))
            for i in range(LEAVE_ROOM_ATTEMPT_LIMIT):
                resp = await self.room_leave(room_id)
                logging.info(resp)
                if isinstance(resp, RoomLeaveError):
                    await asyncio.sleep(resp.retry_after_ms * 1e-3)
                else:
                    break

    def sync_next_sample_times(self):
        for user_id in self.database.user_data.keys():
            self.sync_next_sample_time(user_id)

    def sync_next_sample_time(self, user_id):
        next_sample_time = self.database.get_next_sample_time(user_id)
        time_now = datetime.now()
        rate = self.database.get_rate(user_id)
        # TODO: do this in a cleaner way. Should next_sample_time ever be None?
        if next_sample_time is None:
            new_sample_time = self.create_next_sample_time(time_now, rate)
        else:
            new_sample_time = next_sample_time
            while new_sample_time <= time_now:
                time_now = datetime.now()
                logging.info("Saving placeholder sample")
                self.database.save_sample(user_id, new_sample_time, "EMPTY (BOT OFF)")
                new_sample_time = self.create_next_sample_time(new_sample_time, rate)
        logging.info("Setting next sample time for {} to {}".format(user_id, new_sample_time))
        self.schedule_next_sample(user_id, new_sample_time)

    async def collect_user_activity(self, user_id):
        room_id = self.database.get_room(user_id)
        sample_time = self.database.get_next_sample_time(user_id)
        if self.database.get_user_state(user_id) == STATE_ACTIVITY_WAIT:
            await self.send_room_message("Previous sample unanswered, saving placeholder label...", room_id)
            self.database.save_sample(user_id, sample_time, "EMPTY")
        await self.send_room_message("What's up?", room_id)
        self.database.set_user_state(user_id, STATE_ACTIVITY_WAIT)
        rate = self.database.get_rate(user_id)
        new_sample_time = self.create_next_sample_time(sample_time, rate)
        self.schedule_next_sample(user_id, new_sample_time)

    async def propose_to_switch_room(self, user_id, room_id):
        resp = "Hello {}, you are already registered. Want to move the conversation to this room?".format(user_id)
        await self.send_room_message(resp, room_id)
        self.database.set_user_state(user_id, STATE_ROOM_SWITCH_WAIT)

    async def room_create_callback(self, room, event):
        logging.info(event)
        await self.handle_room_join(room.room_id)

    async def handle_room_join(self, room_id):
        user_id = self.database.get_new_room_user(room_id)
        if self.database.is_user_room_registered(user_id):
            logging.info("User {} already registered with room {}".format(user_id, room_id))
            await self.propose_to_switch_room(user_id, room_id)
        else:
            self.database.switch_to_new_room(user_id)
            await self.send_room_message(WELCOME_STR, room_id)
            rate = self.database.get_rate(user_id)
            time_now = datetime.now()
            next_sample_time = self.create_next_sample_time(time_now, rate)
            self.schedule_next_sample(user_id, next_sample_time)

    async def room_member_callback(self, room, event):
        if event.membership == "leave":
            logging.info(self.database.user_data)
            user_id = self.database.get_room_user(room.room_id)
            if event.state_key == user_id:
                logging.info("Leaving room {}".format(room.room_id))
                await self.room_leave(room.room_id)
        # Did the bot join a new room?
        elif event.state_key == self.user_id and event.membership == "join":
            # Apparently this can happen more than once after joining a room
            logging.info(event.content)
            logging.info(await self.joined_rooms())

    async def invite_callback(self, room, event):
        logging.info(event)
        logging.info(event.state_key)

        for join_attempt in range(JOIN_ATTEMPT_LIMIT):
            resp = await self.join(room.room_id)
            if isinstance(resp, JoinError):
                logging.info("Failed to join room {}: {}".format(room.room_id, resp.message))
            else:
                logging.info("Joined room {}".format(room.room_id))
                user_id = event.sender
                if self.database.is_user_registered(user_id):
                    self.database.add_new_room(user_id, room.room_id)
                else:
                    self.database.register_user(user_id)
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
        help_str = ""
        for command in self.commands:
            help_str += "{} - {}\n".format(command.name, command.get_help_entry())
        await self.send_room_message(help_str, room_id)

    async def send_info_message(self, room_id):
        await self.send_room_message(INFO_STR, room_id)

    async def send_data_summary_message(self, room_id):
        # TODO: read saved data and summarize
        # Output a table with all recorded labels
        # Total number of samples
        # Samples and percentage per label
        return False

    async def handle_help_message(self, args, room_id):
        await self.send_help_message(room_id)

    async def handle_info_message(self, args, room_id):
        await self.send_info_message(room_id)

    async def handle_data_summary_message(self, args, room_id):
        await self.send_data_summary_message(room_id)

    async def handle_set_rate_message(self, args, room_id):
        rate = args.rate
        user_id = self.database.get_room_user(room_id)
        self.database.set_rate(user_id, float(rate))
        resp = "Updated rate to {}".format(rate)
        await self.send_room_message(resp, room_id)

    async def handle_get_rate_message(self, args, room_id):
        user_id = self.database.get_room_user(room_id)
        rate = self.database.get_rate(user_id)
        response = "Current rate is {}".format(rate)
        await self.send_room_message(response, room_id)

    async def handle_get_next_sample_time(self, args, room_id):
        user_id = self.database.get_room_user(room_id)
        next_sample_time = self.database.get_next_sample_time(user_id)
        response = "Next sample scheduled for {}".format(next_sample_time)
        await self.send_room_message(response, room_id)

    async def handle_get_data(self, args, room_id):
        await self.send_data(room_id)

    async def handle_get_history(self, args, room_id):
        user_id = self.database.get_room_user(room_id)
        user_file_path = self.database.get_user_file_path(user_id)
        if not args.line:
            rows = get_last_csv_context(user_file_path, args.size)
        else:
            rows = get_csv_context(user_file_path, args.line, args.size)
        rows = [','.join(row) for row in rows]
        response = "\n".join(rows)
        response_head = "ID, TIME, LABEL, RATE"
        response = "{}\n{}".format(response_head, response)
        await self.send_room_message(response, room_id)

    async def wait_until(self, dt):
        # sleep until the specified datetime
        now = datetime.now()
        await asyncio.sleep((dt - now).total_seconds())

    async def run_at(self, dt, coro):
        await self.wait_until(dt)
        return await coro

    def create_next_sample_time(self, prev_sample_time, rate):
        interval = np.random.exponential(scale=rate)
        next_sample_time = prev_sample_time + timedelta(minutes=interval)
        return next_sample_time

    def schedule_next_sample(self, user_id, sample_time):
        loop = asyncio.get_event_loop()
        self.database.set_next_sample_time(user_id, sample_time)
        loop.create_task(self.run_at(sample_time, self.collect_user_activity(user_id)))
        logging.info("Scheduled new sample time at {}".format(sample_time))

    async def handle_activity_message(self, msg, user_id, room_id):
        if self.is_activity_string(msg):
            resp = "Cool, I'll remember that >:)"
            await self.send_room_message(resp, room_id)
            time_now = datetime.now()
            self.database.save_sample(user_id, time_now, msg)
            self.database.set_user_state(user_id, STATE_NONE)
        else:
            err_str = "Expected lowercase words, not '{}'".format(msg)
            await self.send_room_message(err_str, room_id)

    async def handle_room_switch_message(self, msg, user_id, room_id):
        if msg == "yes":
            await self.send_room_message("Ok, let's keep talking here", room_id)
            self.database.switch_to_new_room(user_id)
            self.database.set_user_state(user_id, STATE_NONE)
        elif msg == "no":
            await self.send_room_message("Ok, I'm out", room_id)
            self.database.set_user_state(user_id, STATE_NONE)
            self.leave_room(room_id)
        else:
            err_str = "Expected yes or no, not '{}'".format(msg)
            await self.send_room_message(err_str, room_id)

    async def handle_command(self, msg, room_id):
        msg_lowercase = msg.lower()
        command_recognized = False
        for command in self.commands:
            if msg_lowercase.startswith(command.name):
                arg_str = msg_lowercase[len(command.name):].strip()
                try:
                    args = command.arg_parser.parse_args(arg_str.split())
                    await command(args, room_id)
                    command_recognized = True
                    break
                except ArgumentException:
                    logging.info("Parse failed")
                    command_recognized = False
        if not command_recognized:
            response_msg = "'{}' is not valid input. Send 'help' to list valid input".format(msg)
            await self.send_room_message(response_msg, room_id)

    async def handle_message(self, msg, user_id, room_id):
        state = self.database.get_user_state(user_id)
        logging.info("Handling valid message '{}' in state {}".format(msg, state))
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
        await self.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": msg
            },
            ignore_unverified_devices=True
        )

    async def send_to_all_registered_users(self, msg):
        for user_id in self.database.user_data.keys():
            room_id = self.database.get_room(user_id)
            await self.send_room_message(msg, room_id)

    async def send_data(self, room_id):
        user_id = self.database.get_room_user(room_id)
        file_path = self.database.get_user_file_path(user_id)
        if os.path.exists(file_path):
            file_stat = await aiofiles.os.stat(file_path)
            async with aiofiles.open(file_path, "r+b") as f:
                resp, maybe_keys = await self.upload(
                    f,
                    content_type="test/plain",
                    filename=file_path,
                    filesize=file_stat.st_size
                )
            await self.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.file",
                    "url": resp.content_uri,
                    "body": "TimeProf data"
                }
            )
        else:
            await self.send_room_message("There is no data", room_id)

    async def main(self):
        await self.sync_forever(timeout=10000)

async def main():
    pw = os.environ["TIMEPROF_MATRIX_PW"]
    bot = TimeProfBot(HOMESERVER, BOT_USER_ID, pw)
    logging.info("Initialising bot")
    await bot.init(leave_all_rooms=True)
    try:
        await bot.main()
    except:
        try:
            await bot.send_to_all_registered_users("There was a problem. Shutting down...")
            await bot.database.save_user_states()
        except:
            pass
        raise
    await bot.client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.get_event_loop().run_until_complete(main())
