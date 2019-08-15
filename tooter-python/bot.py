#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
xm2toot - the XMPP-Mastodon bot
Adapted for XMPP meetup Dresden 2019-08-15

Copyright 2018-2019 bitkeks <dev@bitkeks.eu>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import argparse
import asyncio
from collections import namedtuple
from datetime import datetime
import html
from html.parser import HTMLParser
import json
import logging
import re
import signal
import sys

import aioxmpp
import aioxmpp.dispatcher
import aiohttp


# aiohttp session
session = None


class ContentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def construct_message(to, body):
    msg = aioxmpp.Message(
        to=aioxmpp.JID.fromstr(to),  # recipient_jid must be an aioxmpp.JID
        type_=aioxmpp.MessageType.CHAT,
    )
    # None is for "default language"
    msg.body[None] = body
    return msg


def construct_muc_message(body):
    msg = aioxmpp.Message(type_=aioxmpp.MessageType.GROUPCHAT)
    msg.body[None] = body
    return msg


def message_received(msg):
    log.info(msg)

    if not msg.body:
        return

    sender = "{}@{}".format(msg.from_.localpart, msg.from_.domain)
    if sender in config.xmpp.admins:
        if msg.body.any() == "quit":
            log.info("Received quit command")
            stop_event.set()

    reply = msg.make_reply()
    reply.body.update(msg.body)
    client.enqueue(reply)


async def mastodon_get_user():
    endpoint = f"https://{instance}/api/v1/accounts/verify_credentials"
    async with session.get(endpoint, headers=headers) as response:
        log.debug(f"Endpoint {endpoint} connected.")
        return await response.json()


async def handle_xmpp_command(content_queue, room_message_queue) -> str:
    log.debug("Starting handle_xmpp_command loop")
    while True:
        try:
            content = await content_queue.get()
        except (asyncio.CancelledError, RuntimeError):
            log.debug("Returning from handle_xmpp_command because task was cancelled.")
            return

        msg = None

        # Mastodon stats
        if content == "stats":
            def __examine_stats(result_json):
                log.debug("result_json: %s" % result_json)
                user = result_json
                msg = "{display} (@{username}) has {followers} followers and {statuses} Toots. URL: {url}".format(
                    display=user["display_name"],
                    username=user["username"],
                    followers=user["followers_count"],
                    statuses=user["statuses_count"],
                    url=user["url"]
                )
                return msg

            result = await mastodon_get_user()
            msg = __examine_stats(result)
            log.info("Replied to 'stats' command")

        # More commands can be implemented, e.g. following and boosting
        # Don't forget to restrict sensitive commands to a list of allowed users

        await room_message_queue.put(msg)


async def http_stream(room_message_queue):
    timeout = aiohttp.ClientTimeout(total=None, connect=60, sock_connect=60, sock_read=None)
    endpoint = "https://{}/api/v1/streaming/user".format(instance)

    async def handle_stream(response):
        if response.status != 200:
            log.error("Response status from streaming endpoint: %s. Sleeping 10 seconds and trying again" % response.status)
            await asyncio.sleep(10)
            return

        log.info("Stream to %s opened" % instance)

        while True:
            try:
                line = await response.content.readline()
            except aiohttp.client_exceptions.ClientPayloadError:
                # Initialize new stream session
                break

            line = line.strip()
            log.debug("Received from %s: %s" % (instance, line))

            if len(line) == 0:
                log.debug("Line filtered because zero length")
                continue

            # Catch lines which hold data JSON dicts
            if line.startswith(b"data: {"):
                # Parse the line as JSON
                data = json.loads(line[len(b"data: "):])
                log.debug("Line was successfully loaded as JSON")
                log.debug(data)

                if "type" not in data:
                    continue

                # Extract notification type
                nt = data["type"]

                # New followers
                if nt == "follow":
                    await room_message_queue.put("{} ({}) started following {}".format(
                        data["account"]["display_name"],
                        data["account"]["url"],
                        config.mastodon.account
                    ))

                # Boosts
                elif nt == "reblog":
                    await room_message_queue.put("{} ({}) has boosted {}".format(
                        data["account"]["display_name"],
                        data["account"]["url"],
                        data["status"]["url"]
                    ))

                # Favs
                elif nt == "favourite":
                    await room_message_queue.put("{} ({}) has favorited {}".format(
                        data["account"]["display_name"],
                        data["account"]["url"],
                        data["status"]["url"]
                    ))

                # Mentions
                elif nt == "mention":
                    msg = "{} was mentioned, check notifications".format(config.mastodon.account)

                    if data["status"]:
                        # Public URL or hint to private message
                        reference = "a private message"
                        if data["status"]["visibility"] in ["public", "unlisted"]:
                            raw = html.unescape(data["status"]['content'])
                            cp = ContentParser()
                            cp.feed(raw)
                            content = cp.get_data()

                            reference = "{} \"{}\"".format(
                                data["status"]["url"],
                                content
                            )

                        msg = "{} ({}) has mentioned {} in {}".format(
                            data["status"]["account"]["display_name"],
                            data["status"]["account"]["url"],
                            config.mastodon.account,
                            reference
                        )

                    await room_message_queue.put(msg)

                else:
                    log.error(f"Received unknown notification type: {nt}")

    while True:
        log.info("Starting request to %s" % instance)
        async with session.get(endpoint, headers=headers, timeout=timeout) as response:
            await handle_stream(response)


async def xmpp(room_message_queue):
    async with client.connected() as stream:
        # Join MUC
        room, room_future = muc.join(
            mucjid=aioxmpp.JID.fromstr(config.xmpp.muc),
            nick=config.xmpp.muc_nick,
            history=aioxmpp.muc.xso.History(seconds=0))  # Fetch no history

        def _send_room_message(msg):
            room.send_message(construct_muc_message(msg))

        def _on_message(message, member, source, **kwargs):
            mynick = room.me.nick
            content = message.body.any()

            # Ignore own messages
            if member == room.me:
                return

            log.debug(f"MUC message from {member.nick}: \"{content}\"")

            if content.startswith(mynick):
                # Remove nick prefix
                content = content[len(mynick):]

                # Remove possible following symbols
                if content[0] == "," or content[0] == ":":
                    content = content[1:].strip()

                log.debug("Formatted content: \"{}\"".format(content))

                content_queue.put_nowait(content)


        def _on_enter(**kwargs):
            log.info("Entered room {} as {}".format(room.jid, room.me.nick))

        content_queue = asyncio.Queue()
        command_task = asyncio.create_task(handle_xmpp_command(content_queue, room_message_queue))

        room.on_message.connect(_on_message)
        room.on_enter.connect(_on_enter)

        await room_future

        while True:
            try:
                message = await room_message_queue.get()
                log.debug("Got message from queue: %s" % message)
                msg = construct_muc_message(message)
                room.send_message(msg)
            except asyncio.CancelledError:
                # Catch Task.cancel()
                log.debug("Catched task.cancel() during runtime. Leaving room, exiting client context.")
                await room.leave()
                command_task.cancel()
                return


async def run():
    room_message_queue = asyncio.Queue()

    # Set up aiohttp ClientSession
    global session
    session = aiohttp.ClientSession()

    tasks = [
        asyncio.create_task(http_stream(room_message_queue)),
        asyncio.create_task(xmpp(room_message_queue)),
        asyncio.create_task(stop_event.wait()),
    ]

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    # cancel all tasks, wait for clean shutdown, log any exceptions
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            continue

    for task in done:
        if task.exception():
            log.error(f"Task {task} raised an exception", exc_info=task.exception())

    await session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", "-d", dest="debug", action="store_true", help="enable debugging output")
    parser.add_argument("-x", dest="xmppdebug", action="store_true", help="enable XMPP debugging output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG if args.debug else logging.INFO)
    xmpp_logger = logging.getLogger('aioxmpp')
    xmpp_logger.setLevel(logging.DEBUG if args.xmppdebug else logging.INFO)

    config = None
    with open('config.json', 'r') as fh:
        config = json.loads(fh.read(),
            object_hook=lambda d: namedtuple('config', d.keys())(*d.values()))
    instance = config.mastodon.instance

    headers = {
        "User-Agent": "xm2toot",
        "Authorization": "Bearer {}".format(config.mastodon.token)
    }

    # Setup XMPP
    client = aioxmpp.PresenceManagedClient(
        aioxmpp.JID.fromstr(config.xmpp.username),
        aioxmpp.make_security_layer(config.xmpp.password),
        logger=xmpp_logger
    )
    message_dispatcher = client.summon(aioxmpp.dispatcher.SimpleMessageDispatcher)
    message_dispatcher.register_callback(
        aioxmpp.MessageType.CHAT,
        None,
        message_received,
    )
    muc = client.summon(aioxmpp.MUCClient)

    # Start
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()
    loop.add_signal_handler(
        signal.SIGINT,
        stop_event.set,
    )
    loop.run_until_complete(run())
    loop.close()
