#!/usr/bin/env python

import logging
import sys
from threading import Thread, Event
import time
from slackclient import SlackClient
from midi2audio import FluidSynth
from tempfile import NamedTemporaryFile
from rtmidi.midiutil import open_midiinput, open_midioutput
from rtmidi.midiconstants import NOTE_OFF, NOTE_ON
from mido import Message, MidiFile, MidiTrack, second2tick
import os
from queue import Queue
import json
from base64 import b64decode
from google.oauth2 import service_account
from googleapiclient.discovery import build

PORT_NUMBER = os.environ["MIDI_PORT_NUMBER"]
NUMBER_OF_PIANO_KEYS = 120
SLACK_CHANNEL = os.environ["SLACK_CHANNEL"]
SLACK_API_TOKEN = os.environ["SLACK_API_TOKEN"]
SOUNDFONT_PATH = os.environ["SOUNDFONT_PATH"]
GOOGLE_CREDENTIALS_JSON_STRING = json.loads(b64decode(os.environ["GOOGLE_CREDENTIALS_JSON"]))
GOOGLE_FOLDER_ID = os.environ["GOOGLE_FOLDER_ID"]
GOOGLE_SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']

log = logging.getLogger('pianobot')
logging.basicConfig(level=logging.DEBUG)

slack_client = SlackClient(SLACK_API_TOKEN)


def slack(text):
    res = slack_client.api_call(
        "chat.postMessage",
        channel=SLACK_CHANNEL,
        text=text
    )


def ResettableTimer(*args, **kwargs):
    return _ResettableTimer(*args, **kwargs)


class _ResettableTimer(Thread):
    def __init__(self, interval, fn, args=[], kwargs={}):
        Thread.__init__(self)
        self._interval = interval
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._finished = Event()
        self._reset = True

    def cancel(self):
        self._finished.set()

    def run(self):
        while self._reset:
            self._reset = False
            self._finished.wait(self._interval)

        if not self._finished.isSet():
            self._fn(*self._args, **self._kwargs)
        self._finished.set()

    def reset(self, interval=None):
        if interval:
            self._interval = interval
        self._reset = True
        self._finished.set()
        self._finished.clear()


class Recorder(Thread):
    def __init__(self, musical_feedback):
        Thread.__init__(self)
        self._armed = False
        self._recording = False
        self._feedback = musical_feedback
        self._recording_started = None
        self._midifile = None
        self._miditrack = None
        self._started_recording = None
        self._recording_timeout = None
        self._rearm_timeout = None
        self._last_recorded_event = None
        self._queue = Queue()

    def run(self):
        while True:
            item = self._queue.get()
            if item is None:
                break
            event, note, velocity, t = item
            self._record_event(event, note, velocity, t)
            self._queue.task_done()

    def arm_recording(self):
        if self._armed:
            return
        self._armed = True
        self._feedback.happy_sound()
        slack("_will record when someone plays_")

    def disarm_recording(self):
        if not self._armed:
            return
        self.stop_recording()
        self._armed = False
        self._feedback.sad_sound()
        slack("_won't record for now_")
        self._rearm_timeout = ResettableTimer(60, self.arm_recording)
        self._rearm_timeout.start()

    def _google_upload(self, name, body):
        service_credentials = service_account.Credentials.from_service_account_info(GOOGLE_CREDENTIALS_JSON_STRING, scopes=GOOGLE_SCOPES)
        drive_service = build('drive', 'v2', credentials=service_credentials)
        file_metadata = {
            'title': name,
            'parents': [{'id': GOOGLE_FOLDER_ID}]
        }
        file_insert = drive_service.files.insert(body=file_metadata,
                                   media_body=body,
                                   fields='id').execute()
        print('File ID: %s' % file_insert.get('id'))

    def stop_recording(self):
        if not self._recording:
            return
        self._recording = False
        self._recording_started = None
        self._recording_timeout.cancel()
        self._recording_timeout = None
        self._last_recorded_event = None
        slack("_just stopped recording_")
        with NamedTemporaryFile("wb", suffix='.mid') as midi_output:
            self._midifile.save(file = midi_output)
            midi_output.flush()
            fs = FluidSynth(SOUNDFONT_PATH)
            fs.midi_to_audio(midi_output.name, midi_output.name + ".wav")
            with open(midi_output.name, "rb") as midi_file_handle:
                midi_bytes = midi_file_handle.read()
                res = slack_client.api_call(
                    "files.upload",
                    channels=SLACK_CHANNEL,
                    file=midi_bytes,
                    title="test.mid"
                )
                self._google_upload("test.mid", midi_bytes)

            with open(midi_output.name + ".wav", "rb") as file_content:
                res = slack_client.api_call(
                    "files.upload",
                    channels=SLACK_CHANNEL,
                    file=file_content,
                    title="test.wav"
                )
        self._midifile = None
        self._miditrack = None

    def start_recording(self, start_time):
        if self._recording:
            return
        self._recording = True
        self._started_recording = start_time
        self._midifile = MidiFile()
        self._miditrack = MidiTrack()
        self._midifile.tracks.append(self._miditrack)
        self._recording_timeout = ResettableTimer(15, self.stop_recording)
        self._recording_timeout.start()
        self._last_recorded_event = None
        slack("_just started recording_")

    def record_event(self, event, note, velocity, t):
        print("enq event %s %s %s" % (event, note, velocity))
        self._queue.put([event, note, velocity, t])

    def _record_event(self, event, note, velocity, t):
        print("processing real event %s %s %s" % (event, note, velocity))
        if self._rearm_timeout:
            self._rearm_timeout.reset()
        if not self._recording and self._armed:
            self.start_recording(t)
        if self._recording:
            self._recording_timeout.reset()
            if self._last_recorded_event is None:
                self._last_recorded_event = t
            self._miditrack.append(Message(event, note=note, velocity=velocity, time=int(second2tick(t - self._last_recorded_event, self._midifile.ticks_per_beat, 120))))
            self._last_recorded_event = t

    def shutdown(self):
        self.stop_recording()
        self._queue.put(None)

    # def record_note(self, note, velocity, duration, start_time):
    #     if velocity == 0:
    #         velocity = 100
    #
    #     if self._rearm_timeout:
    #         self._rearm_timeout.reset()
    #     if not self._recording and self._armed:
    #         self.start_recording(start_time)
    #     if self._recording:
    #         self._recording_timeout.reset()
    #         self._midifile.append(Message( 0, 0, note, start_time - self._started_recording, duration, velocity)

    def toggle(self):
        if self._armed:
            self.disarm_recording()
        else:
            self.arm_recording()

class MusicalFeedback(object):
    def __init__(self, out):
        self._out = out

    def _chord(self, notes, duration_in_secs):
        for note in notes:
            self._out.send_message([NOTE_ON, note, 112])
        time.sleep(duration_in_secs)
        for note in notes:
            self._out.send_message([NOTE_OFF, note, 0])

    def _play_notes(self, notes, duration_in_secs, velocity):
        for note in notes:
            self._out.send_message([NOTE_ON, note, velocity])
            time.sleep(duration_in_secs)
            self._out.send_message([NOTE_OFF, note, velocity])

    def sad_sound(self):
        self._play_notes([60, 60, 59, 59, 58, 58, 57, 57], 0.1, 120)

    def happy_sound(self):
        self._play_notes([100, 100, 101, 101, 102, 102, 103, 103], 0.1, 120)

    def happy_chords(self):
        self._chord([60, 64, 67], 0.5)
        self._chord([61, 65, 68], 0.5)
        self._chord([60, 64, 67], 0.5)


class Keyboard(object):
    def __init__(self, commands, recorder=None):
        self._active_notes = [None] * NUMBER_OF_PIANO_KEYS
        self._active_notes_velocity = [None] * NUMBER_OF_PIANO_KEYS
        self._active_hotkey = [False] * NUMBER_OF_PIANO_KEYS
        self._commands = commands
        self._special_keys = sum([commands[cmd]['combo'] for cmd in range(len(commands))], [])
        self._recorder = recorder

    def is_note_active(self, note):
        return self._active_notes[note] is not None and self._active_notes_velocity[note] is not None

    def check_hotkeys(self, note):
        if note in self._special_keys:
            for cmd in self._commands:
                combo = cmd['combo']
                if all(self.is_note_active(x) for x in combo):
                    for x in combo:
                        self._active_hotkey[x] = True
                    fn = cmd['fn']
                    fn()
                    break

    def note_on(self, t, note, velocity):
        self._active_notes[note] = t
        self._active_notes_velocity[note] = velocity
        self.check_hotkeys(note)

        if self._recorder:
            self._recorder.record_event("note_on", note, velocity, t)

    def note_off(self, t, note, velocity):
        if not self.is_note_active(note):
            print("guard fail")

        if self._recorder:
            self._recorder.record_event("note_off", note, velocity, t)

        start_time = self._active_notes[note]
        # initial_velocity = self._active_notes_velocity[note]
        self._active_notes[note] = None
        self._active_notes_velocity[note] = None

        if self._active_hotkey[note]:
            self._active_hotkey[note] = False
        else:
            duration = t - start_time
            # if self._recorder:
            #     self._recorder.record_note(note, velocity, duration, start_time)


class MidiInCallback(object):
    def __init__(self, keyboard):
        self._wallclock = time.time()
        self._keyboard = keyboard

    def __call__(self, event, data=None):
        message, deltatime = event
        self._wallclock += deltatime

        t = self._wallclock
        event_type = message[0]
        note = message[1]
        velocity = message[2]

        if event_type == NOTE_ON:
            self._keyboard.note_on(t, note, velocity)
        elif event_type == NOTE_OFF:
            self._keyboard.note_off(t, note, velocity)
        else:
            print("Unrecognized message: %s" % message)


def main():
    try:
        midi_in, in_port_name = open_midiinput(PORT_NUMBER)
        midi_out, out_port_name = open_midioutput(PORT_NUMBER, 0)
    except (EOFError, KeyboardInterrupt):
        sys.exit()

    musical_feedback = MusicalFeedback(midi_out)
    recorder = Recorder(musical_feedback)
    recorder.start()

    keyboard = Keyboard([{
        "combo": [105, 107, 108],
        "fn": recorder.toggle
    }, {
        "combo": [64, 65, 62],
        "fn": recorder.toggle
    }], recorder)

    midi_in.set_callback(MidiInCallback(keyboard))
    recorder.arm_recording()

    print("Entering main Pianobot loop. Press Control-C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('')
    finally:
        print("Exit.")
        recorder.shutdown()
        midi_in.close_port()
        midi_out.close_port()
        del midi_in
        del midi_out


if __name__ == "__main__":
    main()
