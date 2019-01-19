#!/usr/bin/env python
import logging
import sys
import time

from rtmidi.midiutil import open_midiinput
from rtmidi.midiconstants import NOTE_OFF, NOTE_ON

active_notes = [None] * 120
active_notes_velocity = [None] * 120

def is_key_pressed(note):
    return active_notes[note] is not None and active_notes_velocity[note] is not None

class MidiInputHandler(object):
    def __init__(self, port):
        self.port = port
        self._wallclock = time.time()

    def __call__(self, event, data=None):
        message, deltatime = event
        self._wallclock += deltatime
        if message[0] == NOTE_ON:
            t = self._wallclock
            note = message[1]
            velocity = message[2]
            active_notes[note] = t
            active_notes_velocity[note] = velocity
        elif message[0] == NOTE_OFF:
            t = self._wallclock
            note = message[1]
            if not is_key_pressed(note):
                print("guard fail")
            start_time = active_notes[note]
            duration = t - start_time
            velocity = active_notes_velocity[note]

            active_notes[note] = None
            active_notes_velocity[note] = None

            print("Note %d, velocity %d, duration %f, start %f" % (note, velocity, duration, start_time))
        else:
            print("uncognized message")
            print(message)

port = sys.argv[1] if len(sys.argv) > 1 else None

try:
    midiin, port_name = open_midiinput(1)
except (EOFError, KeyboardInterrupt):
    sys.exit()

print("Attaching MIDI input callback handler.")
midiin.set_callback(MidiInputHandler(port_name))

print("Entering main loop. Press Control-C to exit.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print('')
finally:
    print("Exit.")
    midiin.close_port()
    midiout.close_port()
    del midiin
    del midiout
