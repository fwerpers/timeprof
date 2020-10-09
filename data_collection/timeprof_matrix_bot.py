import asyncio
from nio import (
    AsyncClient,
    RoomMessageText)
import time
import re
import logging
import os


HOMESERVER = "https://matrix.org"
BOT_USER_ID = "@timeprof_bot:matrix.org"
WERPERS_ROOM_ID = "!axKzwhgxJKiKiOhYrD:matrix.org"
FWERPERS_ROOM_ID = "!RSzOBpBQRUWLcnlzmq:matrix.org"
WERPERS_USER_ID = "@werpers:matrix.org"  # if of user to interact with
FWERPERS_USER_ID = "@fwerpers:matrix.org"
MSG_TIME_LIMIT_MS = 5e3
MS_PER_S = 1e3
DEFAULT_AMOUNT = int(1e3)


STATE_NONE = 0
STATE_ACTIVITY_WAIT = 1


""" This is a bot to collect user activity with sampling according to a Poisson process. Every now and then it will ask what you are up to. To set the rate of the Poisson process sampling, type "set rate <rate>"
"""


class Bot():
    def __init__(self):
        pass

    async def init(self, homeserver, bot_id, bot_pw, room_id, user_id):
        self.client = AsyncClient(homeserver, bot_id, ssl=True, device_id="matrix-nio")
        self.client.add_event_callback(self.message_callback, RoomMessageText)
        await self.client.login(bot_pw)
        self.state = STATE_NONE
        self.room_id = room_id
        self.user_id = user_id
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

    def save_save(self):
        logging.info("Saving data")

    async def message_callback(self, room, event) -> None:
        print("asdfasdfasdf")
        logging.info("dasdasdasdasds")
        msg = event.body
        logging.info("Got message {}".format(msg))
        if not self.msg_event_valid(event):
            #logging.info("Discarding message {}".format(msg))
            return
        if self.state == STATE_ACTIVITY_WAIT:
            if self.is_simple_phrase(msg):
                await self.send_message("Saving data...")
                self.save_data()
            else:
                err_str = "Expected simple words, not '{}'".format(msg)
                await self.send_message(err_str)

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
    await bot.collect_user_activity()
    await bot.client.sync_forever(timeout=10000)
    await bot.client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.get_event_loop().run_until_complete(main())
