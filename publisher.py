from io import BytesIO
from queue import Queue
from tempfile import NamedTemporaryFile

import os
from threading import Thread

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from midi2audio import FluidSynth
from slackclient import SlackClient

GOOGLE_SCOPES = ['https://www.googleapis.com/auth/drive']
SOUNDFONT_PATH = os.environ["SOUNDFONT_PATH"]


class Publisher(Thread):
    def __init__(self, slack_api_token, slack_channel_public, slack_channel_private, google_credentials_json_str, google_folder_id):
        Thread.__init__(self)
        self._slack_client = SlackClient(slack_api_token)
        self._slack_channel_public = slack_channel_public
        self._slack_channel_private = slack_channel_private
        service_credentials = service_account.Credentials.from_service_account_info(google_credentials_json_str,
                                                                                    scopes=GOOGLE_SCOPES)
        self._google_drive = build('drive', 'v2', credentials=service_credentials, cache_discovery=False)
        self._google_folder_id = google_folder_id

        self._queue = Queue()

    def shutdown(self):
        self._queue.put(None)

    def run(self):
        while True:
            item = self._queue.get()
            if item is None:
                break
            if item[0] == 'slack_text':
                self._slack_text(item[1])
                pass
            elif item[0] == 'publish_midi_file':
                self._publish_midi_file(item[1], item[2], item[3])
            else:
                print(item)
                print("bad queued event. abort")
            self._queue.task_done()

    def publish_midi_file(self, file_prefix, midi_bytes, public):
        self._queue.put(["publish_midi_file", file_prefix, midi_bytes, public])

    def _publish_midi_file(self, file_prefix, midi_bytes, public):
        with NamedTemporaryFile("wb", prefix=file_prefix + "-", suffix='.mid') as midi_output:
            midi_output.write(midi_bytes)
            midi_output.flush()

            self._slack_upload_private(file_prefix + ".mid", midi_bytes)
            self._google_upload(file_prefix + ".mid", "audio/midi", midi_bytes)
            if public:
                self._slack_upload_public(file_prefix + ".mid", midi_bytes)

            wav_output_name = midi_output.name + ".wav"
            fluidsynth = FluidSynth(SOUNDFONT_PATH)
            fluidsynth.midi_to_audio(midi_output.name, wav_output_name)

            with open(wav_output_name, "rb") as wav_file_handle:
                wav_bytes = wav_file_handle.read()
                self._slack_upload_private(file_prefix + ".wav", wav_bytes)
                self._google_upload(file_prefix + ".wav", "audio/wav", wav_bytes)
                if public:
                    self._slack_upload_public(file_prefix + ".wav", wav_bytes)
            os.remove(wav_output_name)

    def slack_text(self, text):
        self._queue.put(["slack_text", text])

    def _slack_text(self, text):
        res = self._slack_client.api_call(
            "chat.postMessage",
            channel=self._slack_channel_public,
            text=text
        )

    def _google_upload(self, name, mime, data):
        file_metadata = {
            'title': name,
            'parents': [{'id': self._google_folder_id}]
        }
        bytes_to_upload = BytesIO(data)
        media = MediaIoBaseUpload(bytes_to_upload,
                                  mimetype=mime,
                                  resumable=True)
        file_insert = self._google_drive.files().insert(body=file_metadata,
                                                        media_body=media,
                                                        fields='id').execute()
        return file_insert.get('id')

    def _slack_upload_public(self, name, data):
        res = self._slack_client.api_call(
            "files.upload",
            channels=self._slack_channel_public,
            file=data,
            title=name
        )

    def _slack_upload_private(self, name, data):
        res = self._slack_client.api_call(
            "files.upload",
            channels=self._slack_channel_private,
            file=data,
            title=name
        )
