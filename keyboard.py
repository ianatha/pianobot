NUMBER_OF_PIANO_KEYS = 120


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
