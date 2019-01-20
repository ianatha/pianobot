import time

from rtmidi.midiconstants import NOTE_ON, NOTE_OFF, ACTIVE_SENSING, CONTROL_CHANGE

from resettable_timer import ResettableTimer

NUMBER_OF_PIANO_KEYS = 120

class Keyboard(object):
    def __init__(self, midi_in, commands=[], recorder=None):
        self._midi_in = midi_in
        self._active_notes = [None] * NUMBER_OF_PIANO_KEYS
        self._active_notes_velocity = [None] * NUMBER_OF_PIANO_KEYS
        self._active_hotkey = [False] * NUMBER_OF_PIANO_KEYS
        self._commands = commands
        self._special_keys = sum([commands[cmd]['combo'] for cmd in range(len(commands))], [])
        self._recorder = recorder

        self._midi_in.ignore_types(sysex=False, timing=False, active_sense=False)
        self._wallclock = time.time()
        self._midi_in.set_callback(self)
        self._no_midi_timeout = ResettableTimer(3, self.connection_timeout)
        self._no_midi_timeout.start()
        self._timedout = False

    # Called as a callback by rtmidi
    def __call__(self, event, data=None):
        message, deltatime = event
        self._wallclock += deltatime

        t = self._wallclock
        event_type = message[0]

        if event_type == NOTE_ON:
            note = message[1]
            velocity = message[2]
            self.note_on(t, message[1], message[2], deltatime)
        elif event_type == NOTE_OFF:
            note = message[1]
            velocity = message[2]
            self.note_on(t, message[1], message[2], deltatime)
        elif event_type == CONTROL_CHANGE:
            self.control_change(t, message[1], message[2], deltatime)
        elif event_type == ACTIVE_SENSING:
            self._no_midi_timeout.reset()
            pass
        else:
            print("Unrecognized message: %s" % message)

    def shutdown(self):
        self._no_midi_timeout.cancel()
        self._timedout = False

    def connection_timeout(self):
        self._timedout = True
        print("connection timed out. is the piano still alive?")

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

    def control_change(self):
        pass

    def note_on(self, t, note, velocity, deltatime):
        self._active_notes[note] = t
        self._active_notes_velocity[note] = velocity
        self.check_hotkeys(note)

        if self._recorder:
            self._recorder.record_event("note_on", note, velocity, t, deltatime)

    def note_off(self, t, note, velocity, deltatime):
        if not self.is_note_active(note):
            print("guard fail")

        if self._recorder:
            self._recorder.record_event("note_off", note, velocity, t, deltatime)

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
