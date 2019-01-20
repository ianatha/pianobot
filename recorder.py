import logging
import time
from io import BytesIO
from queue import Queue
from threading import Thread

from mido import MidiFile, MidiTrack, Message, second2tick, bpm2tempo

from publisher import queued
from resettable_timer import ResettableTimer

DEFAULT_BPM = 120
RECORDING_END_TIMEOUT = 15
RECORDING_REARM_TIMEOUT = 3 * 60


class Recorder(Thread):
    def __init__(self, musical_feedback, publisher):
        Thread.__init__(self)
        self._armed = False
        self._armed_public = False
        self._recording = False
        self._feedback = musical_feedback
        self._publisher = publisher
        self._midifile = None
        self._miditrack = None
        self._started_recording = None
        self._recording_timeout = None
        self._rearm_timeout = None
        self._last_recorded_event = None
        self._raw_events = []
        self._queue = Queue()

    def run(self):
        while True:
            item = self._queue.get()
            logging.debug("recorder dequeued %s", item)
            if item is None:
                self._queue.task_done()
                break
            else:
                f = getattr(self, item[0])
                f.underlying_method(self, *item[1], **item[2])
                self._queue.task_done()

    @queued
    def arm_public(self):
        self.arm_recording()
        self._armed_public = True
        self._feedback.happy_sound()
        logging.info("recording armed as public")
        # self._publisher.slack_text("_the next session will be publicized_")
        pass

    @queued
    def arm_recording(self):
        if self._armed:
            logging.info("recording already armed")
            return
        self._armed = True
        logging.info("recording armed")
        self._publisher.slack_text("_will record for research purposes only when someone plays_")

    @queued
    def disarm_recording(self):
        if not self._armed:
            logging.info("recording already disarmed")
            self._feedback.sad_sound()
            return
        self.stop_recording()
        self._armed = False
        logging.info("recording disarmed")
        self._feedback.sad_sound()
        self._rearm_timeout = ResettableTimer(RECORDING_REARM_TIMEOUT, self.arm_recording(), name="recording_rearm")
        self._rearm_timeout.start()
        self._publisher.slack_text("_won't record for now_")

    @queued
    def stop_recording(self):
        if not self._recording:
            return
        self._recording = False
        file_prefix = "piano-%s" % (time.strftime('%Y%m%d%H%M%S', time.localtime(self._started_recording)))
        self._started_recording = None
        self._recording_timeout.cancel()
        self._recording_timeout = None
        if self._last_recorded_event is None:
            return
        self._last_recorded_event = None

        midi_bytes = BytesIO()
        self._midifile.save(file=midi_bytes)
        self._publisher.publish_midi_file(file_prefix, midi_bytes.getbuffer(), public=self._armed_public)
        self._publisher.publish_raw_data(file_prefix, self._raw_events)
        del midi_bytes
        self._armed_public = False
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
        self._recording_timeout = ResettableTimer(RECORDING_END_TIMEOUT, self.stop_recording, name="recording_idle")
        self._recording_timeout.start()
        self._last_recorded_event = None
        self._raw_events = []
        if self._armed_public:
            self._publisher.slack_text("_just started a recording for public consumption_")

    @queued
    def record_raw_event(self, t, message, deltatime, data):
        if self._rearm_timeout:
            self._rearm_timeout.reset()
        if not self._recording and self._armed:
            self.start_recording(t)
        if self._recording:
            self._recording_timeout.reset()
            self._raw_events.append([t, deltatime, message, data])

    @queued
    def record_event(self, event, note, velocity, t, deltatime):
        if self._rearm_timeout:
            self._rearm_timeout.reset()
        if not self._recording and self._armed:
            self.start_recording(t)
        if self._recording:
            self._recording_timeout.reset()
            if self._last_recorded_event is None:
                self._last_recorded_event = t
            self._miditrack.append(Message(event, note=note, velocity=velocity, time=int(
                second2tick(t - self._last_recorded_event, self._midifile.ticks_per_beat, bpm2tempo(DEFAULT_BPM)))))
            self._last_recorded_event = t

    def shutdown(self):
        self.stop_recording()
        self._queue.put(None)

    def toggle(self):
        if self._armed:
            self.disarm_recording()
        else:
            self.arm_recording()
