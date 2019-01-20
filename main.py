#!/usr/bin/env python

import json
import logging
import os
from base64 import b64decode

from slackclient import SlackClient

from pianobot import Pianobot
from publisher import Publisher

PORT_NUMBER = os.environ["MIDI_PORT_NUMBER"]
SLACK_CHANNEL_PUBLIC = os.environ["SLACK_CHANNEL_PUBLIC"]
SLACK_CHANNEL_PRIVATE = os.environ["SLACK_CHANNEL_PRIVATE"]
SLACK_API_TOKEN = os.environ["SLACK_API_TOKEN"]
GOOGLE_CREDENTIALS_JSON_STRING = json.loads(b64decode(os.environ["GOOGLE_CREDENTIALS_JSON"]))
GOOGLE_FOLDER_ID = os.environ["GOOGLE_FOLDER_ID"]
SOUNDFONT_PATH = os.environ["SOUNDFONT_PATH"]

slack_client = SlackClient(SLACK_API_TOKEN)

if __name__ == "__main__":
    try:
        publisher = Publisher(
            soundfont_path=SOUNDFONT_PATH,
            slack_api_token=SLACK_API_TOKEN,
            slack_channel_public=SLACK_CHANNEL_PUBLIC,
            slack_channel_private=SLACK_CHANNEL_PRIVATE,
            google_credentials_json_str=GOOGLE_CREDENTIALS_JSON_STRING,
            google_folder_id=GOOGLE_FOLDER_ID
        )
        publisher.start()

        pianobot = Pianobot(
            port_number=PORT_NUMBER,
            publisher=publisher
        )
        pianobot.run()
    finally:
        publisher.shutdown()
