import asyncio
from nio import (
    AsyncClient,
    RoomMessageText)
import time
import re
import logging
import os
import numpy as np
from datetime import (datetime, timedelta)


HOMESERVER = "https://matrix.org"
BOT_USER_ID = "@timeprof_bot:matrix.org"
MSG_TIME_LIMIT_MS = 5e3
MS_PER_S = 1e3
DEFAULT_AMOUNT = int(1e3)


STATE_NONE = 0
STATE_ACTIVITY_WAIT = 1

DATA_FILENAME = "data.csv"

WERPERS_ROOM_ID = "!axKzwhgxJKiKiOhYrD:matrix.org"
FWERPERS_ROOM_ID = "!RSzOBpBQRUWLcnlzmq:matrix.org"
WERPERS_USER_ID = "@werpers:matrix.org"  # if of user to interact with
FWERPERS_USER_ID = "@fwerpers:matrix.org"


class Bot():
    def __init__(self):
        pass

    async def init(self, homeserver, bot_id, bot_pw, room_id, user_id):
        self.client = AsyncClient(homeserver,
                                  bot_id,
                                  ssl=True,
                                  device_id="matrix-nio")
        self.client.add_event_callback(self.message_callback, RoomMessageText)
        await self.client.login(bot_pw)
        self.state = STATE_NONE
        self.room_id = room_id
        self.user_id = user_id
        self.poisson_process_rate = 45  # minutes
        self.next_sample_time = 0  # set after user activity input
        logging.info("Initialised bot")

    async def collect_user_activity(self):
        await self.send_message("What's up?")
        self.state = STATE_ACTIVITY_WAIT

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

    async def send_help_message(self):
        # TODO: don't hardcode this
        help_str = """Available inputs:
help - this message
info - description of the bot
set rate <rate> - set rate (minutes) of sampling process. Must be an integer
get rate - get current rate
get next - get time of next sample
        """
        await self.send_message(help_str)

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

    async def handle_help_message(self, msg):
        ret = False
        if msg == "help":
            await self.send_help_message()
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

    async def handle_valid_message(self, msg):
        logging.info("Handling valid message '{}'".format(msg))
        response_msg = ""
        if self.state == STATE_ACTIVITY_WAIT:
            if self.is_activity_string(msg):
                await self.send_message("Saving data...")
                self.save_data(msg)
                self.state = STATE_NONE
                loop = asyncio.get_event_loop()
                next_sample_dt = self.get_next_sample_time()
                self.next_sample_time = next_sample_dt
                loop.create_task(self.run_at(next_sample_dt, self.collect_user_activity()))
            else:
                err_str = "Expected lowercase words, not '{}'".format(msg)
                await self.send_message(err_str)
        elif self.state == STATE_NONE:
            if (await self.handle_help_message(msg)):
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
            else:
                response_msg = "'{}' is not valid input. Send 'help' to list valid input".format(msg)
                await self.send_message(response_msg)

    async def message_callback(self, room, event) -> None:
        msg = event.body
        if self.msg_event_valid(event):
            await self.handle_valid_message(msg)
        else:
            logging.info("Discarding message {}".format(msg))

    async def send_message(self, msg):
        await self.client.room_send(
            room_id=self.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": msg
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
    await bot.send_message("Hello from TimeProf =D")
    await bot.send_message("Send 'help' for possible input")
    await bot.collect_user_activity()
    await bot.client.sync_forever(timeout=10000)
    await bot.client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.get_event_loop().run_until_complete(main())
