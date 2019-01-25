from io import BytesIO
from queue import Queue
from tempfile import NamedTemporaryFile

import os
from threading import Thread

from google.oauth2 import service_account  # type: ignore
from googleapiclient.discovery import build  # type: ignore
from googleapiclient.http import MediaIoBaseUpload  # type: ignore
from midi2audio import FluidSynth  # type: ignore
from slackclient import SlackClient  # type: ignore
import json

from functools import wraps


def queued(f):
    @wraps(f)
    def wrapper(*args, **kwds):
        self = args[0]
        self._queue.put([f.__name__, list(args[1:]), kwds])
        return

    wrapper.underlying_method = f
    return wrapper


GOOGLE_SCOPES = ['https://www.googleapis.com/auth/drive']


class Publisher(Thread):
    def __init__(self, soundfont_path: str, slack_api_token: str, slack_channel_public: str, slack_channel_private: str,
                 google_credentials_json: str, google_folder_id: str):
        Thread.__init__(self)
        self._soundfont_path = soundfont_path
        self._slack_client = SlackClient(slack_api_token)
        self._slack_channel_public = slack_channel_public
        self._slack_channel_private = slack_channel_private
        service_credentials = service_account.Credentials.from_service_account_info(google_credentials_json,
                                                                                    scopes=GOOGLE_SCOPES)
        self._google_drive = build('drive', 'v2', credentials=service_credentials, cache_discovery=False)
        self._google_folder_id = google_folder_id

        self._queue: Queue = Queue()

    def shutdown(self) -> None:
        self._queue.put(None)

    def run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                break
            else:
                f = getattr(self, item[0])
                f.underlying_method(self, *item[1], **item[2])
                self._queue.task_done()

    @queued
    def publish_raw_data(self, file_prefix: str, data) -> None:
        self.google_upload(file_prefix + ".json", "application/json", json.dumps(data))

    @queued
    def publish_midi_file(self, file_prefix: str, midi_bytes, public: bool) -> None:
        with NamedTemporaryFile("wb", prefix=file_prefix + "-", suffix='.mid') as midi_output:
            midi_output.write(midi_bytes)
            midi_output.flush()

            self.slack_upload_private(file_prefix + ".mid", midi_bytes)
            self.google_upload(file_prefix + ".mid", "audio/midi", midi_bytes)
            if public:
                self.slack_upload_public(file_prefix + ".mid", midi_bytes)

            wav_output_name = midi_output.name + ".wav"
            fluidsynth = FluidSynth(self._soundfont_path)
            fluidsynth.midi_to_audio(midi_output.name, wav_output_name)

            with open(wav_output_name, "rb") as wav_file_handle:
                wav_bytes = wav_file_handle.read()
                self.slack_upload_private(file_prefix + ".wav", wav_bytes)
                self.google_upload(file_prefix + ".wav", "audio/wav", wav_bytes)
                if public:
                    self.slack_upload_public(file_prefix + ".wav", wav_bytes)
            os.remove(wav_output_name)

    @queued
    def slack_text(self, text: str) -> None:
        res = self._slack_client.api_call(
            "chat.postMessage",
            channel=self._slack_channel_public,
            text=text
        )

    @queued
    def google_upload(self, name: str, mime: str, data) -> str:
        file_metadata = {
            'title': name,
            'parents': [{'id': self._google_folder_id}]
        }
        bytes_to_upload = BytesIO(data)
        media = MediaIoBaseUpload(bytes_to_upload,
                                  mimetype=mime,
                                  resumable=False)
        file_insert = self._google_drive.files().insert(body=file_metadata,
                                                        media_body=media,
                                                        fields='id').execute()
        return file_insert.get('id')

    @queued
    def slack_upload_public(self, name: str, data) -> None:
        res = self._slack_client.api_call(
            "files.upload",
            channels=self._slack_channel_public,
            file=data,
            title=name
        )

    @queued
    def slack_upload_private(self, name: str, data) -> None:
        res = self._slack_client.api_call(
            "files.upload",
            channels=self._slack_channel_private,
            file=data,
            title=name
        )
