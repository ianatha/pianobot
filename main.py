#!/usr/bin/env python

import logging
import sys
import time
from rtmidi.midiutil import open_midiinput
from rtmidi.midiconstants import NOTE_OFF, NOTE_ON
from midiutil import MIDIFile
import os

PORT_NUMBER = os.environ["MIDI_PORT_NUMBER"]
NUMBER_OF_PIANO_KEYS = 120

log = logging.getLogger('pianobot')
logging.basicConfig(level=logging.DEBUG)


class Keyboard(object):
    def __init__(self):
        self._active_notes = [None] * NUMBER_OF_PIANO_KEYS
        self._active_notes_velocity = [None] * NUMBER_OF_PIANO_KEYS

    def is_note_active(self, note):
        return self._active_notes[note] is not None and self._active_notes_velocity[note] is not None

    def note_on(self, t, note, velocity):
        self._active_notes[note] = t
        self._active_notes_velocity[note] = velocity

    def note_off(self, t, note, velocity):
        if not self.is_note_active(note):
            print("guard fail")

        start_time = self._active_notes[note]
        initial_velocity = self._active_notes_velocity[note]
        self._active_notes[note] = None
        self._active_notes_velocity[note] = None
        duration = t - start_time
        print("Note: %d %d -> %d at %s" % (note, initial_velocity, velocity, start_time))


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
    except (EOFError, KeyboardInterrupt):
        sys.exit()

    keyboard = Keyboard()

    midi_in.set_callback(MidiInCallback(keyboard))

    print("Entering main Pianobot loop. Press Control-C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('')
    finally:
        print("Exit.")
        midi_in.close_port()
        del midi_in


if __name__ == "__main__":
    main()
