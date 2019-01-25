import time
from queue import Queue
from threading import Thread
from typing import List

from rtmidi.midiconstants import NOTE_ON, NOTE_OFF  # type: ignore

from publisher import queued


class MusicalFeedback(Thread):
    def __init__(self, out):
        Thread.__init__(self)
        self._out = out
        self._queue = Queue()

    def run(self):
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                break
            else:
                f = getattr(self, item[0])
                f.underlying_method(self, *item[1], **item[2])
                self._queue.task_done()

    def shutdown(self):
        self._queue.put(None)

    def _chord(self, notes: List[int], duration_in_secs: float):
        for note in notes:
            self._out.send_message([NOTE_ON, note, 112])
        time.sleep(duration_in_secs)
        for note in notes:
            self._out.send_message([NOTE_OFF, note, 0])

    def _play_notes(self, notes: List[int], duration_in_secs: float, velocity: int):
        for note in notes:
            self._out.send_message([NOTE_ON, note, velocity])
            time.sleep(duration_in_secs)
            self._out.send_message([NOTE_OFF, note, velocity])

    @queued
    def sad_sound(self):
        self._play_notes([60, 60, 59, 59, 58, 58, 57, 57], 0.1, 120)

    @queued
    def happy_sound(self):
        self._play_notes([100, 100, 101, 101, 102, 102, 103, 103], 0.1, 120)

    @queued
    def happy_chords(self):
        self._chord([60, 64, 67], 0.5)
        self._chord([61, 65, 68], 0.5)
        self._chord([60, 64, 67], 0.5)
