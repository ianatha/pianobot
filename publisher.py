from io import BytesIO

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from slackclient import SlackClient

GOOGLE_SCOPES = ['https://www.googleapis.com/auth/drive']


class Publisher(object):
    def __init__(self, slack_api_token, slack_channel, google_credentials_json_str, google_folder_id):
        self._slack_client = SlackClient(slack_api_token)
        self._slack_channel = slack_channel
        service_credentials = service_account.Credentials.from_service_account_info(google_credentials_json_str,
                                                                                    scopes=GOOGLE_SCOPES)
        self._google_drive = build('drive', 'v2', credentials=service_credentials)
        self._google_folder_id = google_folder_id

    def slack_text(self, text):
        res = self._slack_client.api_call(
            "chat.postMessage",
            channel=self._slack_channel,
            text=text
        )

    def google_upload(self, name, mime, data):
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

    def slack_upload(self, name, data):
        res = self._slack_client.api_call(
            "files.upload",
            channels=self._slack_channel,
            file=data,
            title=name
        )
