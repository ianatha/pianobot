import logging
import sys
import time

import rtmidi
from rtmidi.midiutil import open_midiport

from keyboard import Keyboard
from musical_feedback import MusicalFeedback
from publisher import Publisher
from recorder import Recorder

log = logging.getLogger('pianobot')


class Pianobot(object):
    def __init__(self, port_name: str, publisher: Publisher):
        self._port_name = port_name
        self._publisher = publisher
        self._midi_in = None
        self._midi_out = None

    def _open_midi(self):
        try:
            port_names = rtmidi.MidiIn().get_ports()
            port_number = port_names.index(self._port_name)
        except (ValueError, IOError) as e:
            log.debug("_open_midi, port_names=%s, e=%s", port_names, e)
            return False
        try:
            if self._midi_in is None:
                self._midi_in, _ = open_midiport(port_number, "input", use_virtual=False, interactive=False)
            if self._midi_out is None:
                self._midi_out, _ = open_midiport(port_number, "output", use_virtual=False, interactive=False)
        except IOError as e:
            log.debug("_open_midi, port_number=%s, in=%s, out=%s, IOError=%s", self._port_number, self._midi_in is not None, self._midi_out is not None, e)
            return False
        return True

    def run(self):
        log.info("Trying to connect to %s", self._port_name)
        while not self._open_midi():
            time.sleep(2)
        log.info("Connected to %s", self._port_name)

        musical_feedback = MusicalFeedback(self._midi_out)
        musical_feedback.start()

        recorder = Recorder(musical_feedback, self._publisher)
        recorder.start()

        keyboard = Keyboard(self._midi_in, [{
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
            musical_feedback.shutdown()
            recorder.shutdown()
            keyboard.shutdown()
            self._midi_in.close_port()
            self._midi_out.close_port()
            self._midi_in = None
            self._midi_out = None
