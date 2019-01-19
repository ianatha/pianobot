import sys
import time

from rtmidi.midiconstants import NOTE_ON, NOTE_OFF
from rtmidi.midiutil import open_midiinput, open_midioutput

from keyboard import Keyboard
from musical_feedback import MusicalFeedback
from recorder import Recorder


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
            self._keyboard.note_on(t, note, velocity, deltatime)
        elif event_type == NOTE_OFF:
            self._keyboard.note_off(t, note, velocity, deltatime)
        else:
            print("Unrecognized message: %s" % message)


class Pianobot(object):
    def __init__(self, port_number, publisher):
        self._port_number = port_number
        self._publisher = publisher

    def run(self):
        try:
            midi_in, in_port_name = open_midiinput(self._port_number)
            midi_out, out_port_name = open_midioutput(self._port_number, 0)
        except (EOFError, KeyboardInterrupt):
            sys.exit()

        musical_feedback = MusicalFeedback(midi_out)
        recorder = Recorder(musical_feedback, self._publisher)
        recorder.start()

        keyboard = Keyboard([{
            "combo": [105, 107, 108],
            "fn": lambda: recorder.arm_recording(force_feedback=True)
        }, {
            "combo": [102, 104, 106],
            "fn": lambda: recorder.disarm_recording(force_feedback=True)
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
            self._publisher.shutdown()
            midi_in.close_port()
            midi_out.close_port()
            del midi_in
            del midi_out
