import time
from io import BytesIO
from queue import Queue
from threading import Thread

from mido import MidiFile, MidiTrack, Message, second2tick, bpm2tempo

from resettable_timer import ResettableTimer

DEFAULT_BPM = 120
RECORDING_END_TIMEOUT = 15
RECORDING_REARM_TIMEOUT = 3 * 60

##
# rightmost sustain pedal

# 19.01.19 19:46:12 (-0800)  main  Unrecognized message: [176, 64, 17]
# 19.01.19 19:46:12 (-0800)  main  Unrecognized message: [176, 64, 42]
# 19.01.19 19:46:12 (-0800)  main  Unrecognized message: [176, 64, 75]
# 19.01.19 19:46:12 (-0800)  main  Unrecognized message: [176, 64, 127]
# 19.01.19 19:46:12 (-0800)  main  Unrecognized message: [176, 64, 39]
# 19.01.19 19:46:12 (-0800)  main  Unrecognized message: [176, 64, 0]

# leftmost pedal
# 19.01.19 19:46:38 (-0800)  main  Unrecognized message: [176, 67, 127]
# 19.01.19 19:46:38 (-0800)  main  Unrecognized message: [176, 67, 0]
# 19.01.19 19:46:39 (-0800)  main  Unrecognized message: [176, 67, 127]
# 19.01.19 19:46:39 (-0800)  main  Unrecognized message: [176, 67, 0]
#middle pedal
#19.01.19 19:46:52 (-0800)  main  Unrecognized message: [176, 66, 127]
#19.01.19 19:46:53 (-0800)  main  Unrecognized message: [176, 66, 0]
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
        self._queue = Queue()

    def run(self):
        while True:
            item = self._queue.get()
            if item is None:
                break
            event, note, velocity, t, deltatime = item
            self._record_event(event, note, velocity, t, deltatime)
            self._queue.task_done()

    def arm_public(self):
        self.arm_recording()
        self._armed_public = True
        self._feedback.happy_sound()
        # self._publisher.slack_text("_the next session will be publicized_")
        pass

    def arm_recording(self):
        if self._armed:
            return
        self._armed = True
        self._publisher.slack_text("_will record for research purposes only when someone plays_")

    def disarm_recording(self):
        if not self._armed:
            self._feedback.sad_sound()
            return
        self.stop_recording()
        self._publisher.slack_text("_won't record for now_")
        self._armed = False
        self._feedback.sad_sound()
        self._rearm_timeout = ResettableTimer(RECORDING_REARM_TIMEOUT, self.arm_recording)
        self._rearm_timeout.start()

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
        self._recording_timeout = ResettableTimer(RECORDING_END_TIMEOUT, self.stop_recording)
        self._recording_timeout.start()
        self._last_recorded_event = None
        if self._armed_public:
            self._publisher.slack_text("_just started a recording for public consumption_")

    def record_event(self, event, note, velocity, t, deltatime):
        self._queue.put([event, note, velocity, t, deltatime])

    def _record_event(self, event, note, velocity, t, deltatime):
        if self._rearm_timeout:
            self._rearm_timeout.reset()
        if not self._recording and self._armed:
            self.start_recording(t)
        if self._recording:
            self._recording_timeout.reset()
            if self._last_recorded_event is None:
                self._last_recorded_event = t
            self._miditrack.append(Message(event, note=note, velocity=velocity, time=int(
                second2tick(deltatime, self._midifile.ticks_per_beat, bpm2tempo(DEFAULT_BPM)))))
            self._last_recorded_event = t

    def shutdown(self):
        self.stop_recording()
        self._queue.put(None)

    def toggle(self):
        if self._armed:
            self.disarm_recording()
        else:
            self.arm_recording()
