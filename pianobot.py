import sys
import time

from rtmidi.midiutil import open_midiport

from keyboard import Keyboard
from musical_feedback import MusicalFeedback
from recorder import Recorder


class Pianobot(object):
    def __init__(self, port_number, publisher):
        self._port_number = port_number
        self._publisher = publisher

    def run(self):
        try:
            midi_in, in_port_name = open_midiport(self._port_number, "input", use_virtual=False, interactive=False)
            midi_out, out_port_name = open_midiport(self._port_number, "output", use_virtual=False, interactive=False)
        except (IOError, EOFError, KeyboardInterrupt):
            print("Unable to open MIDI port %s" % self._port_number)
            sys.exit()

        musical_feedback = MusicalFeedback(midi_out)
        recorder = Recorder(musical_feedback, self._publisher)
        recorder.start()

        keyboard = Keyboard(midi_in, [{
            "combo": [105, 107, 108],
            "fn": lambda: recorder.arm_public()
        }, {
            "combo": [102, 104, 106],
            "fn": lambda: recorder.disarm_recording()
        }], recorder)

        recorder.arm_recording()

        try:
            while not keyboard._timedout:
                time.sleep(1)
            print("Exiting because MIDI device timed out.")
        except KeyboardInterrupt:
            print('Exiting due to Ctrl-C.')
        finally:
            print("Shutting down...")
            recorder.shutdown()
            keyboard.shutdown()
            midi_in.close_port()
            midi_out.close_port()
            del midi_in
            del midi_out
