import os
import time
from queue import Queue
from tempfile import NamedTemporaryFile
from threading import Thread

from midi2audio import FluidSynth
from mido import MidiFile, MidiTrack, Message, second2tick, bpm2tempo

from resettable_timer import ResettableTimer

DEFAULT_BPM = 120
RECORDING_END_TIMEOUT = 15
RECORDING_REARM_TIMEOUT = 60

SOUNDFONT_PATH = os.environ["SOUNDFONT_PATH"]


class Recorder(Thread):
    def __init__(self, musical_feedback, publisher):
        Thread.__init__(self)
        self._armed = False
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

    def arm_recording(self):
        if self._armed:
            return
        self._armed = True
        self._feedback.happy_sound()
        self._publisher.slack_text("_will record when someone plays_")

    def disarm_recording(self):
        if not self._armed:
            return
        self._publisher.slack_text("_won't record for now_")
        self._armed = False
        self.stop_recording()
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
        self._last_recorded_event = None
        self._publisher.slack_text("_just stopped recording_")
        with NamedTemporaryFile("wb", prefix=file_prefix + "-", suffix='.mid') as midi_output:
            self._midifile.save(file=midi_output)
            midi_output.flush()

            with open(midi_output.name, "rb") as midi_file_handle:
                midi_bytes = midi_file_handle.read()
                self._publisher.slack_upload(file_prefix + ".mid", midi_bytes)
                self._publisher.google_upload(file_prefix + ".mid", "audio/midi", midi_bytes)

            wav_output_name = midi_output.name + ".wav"
            fluidsynth = FluidSynth(SOUNDFONT_PATH)
            fluidsynth.midi_to_audio(midi_output.name, wav_output_name)

            with open(wav_output_name, "rb") as wav_file_handle:
                wav_bytes = wav_file_handle.read()
                self._publisher.slack_upload(file_prefix + ".wav", wav_bytes)
                self._publisher.google_upload(file_prefix + ".wav", "audio/midi", wav_bytes)
            os.remove(wav_output_name)
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
        self._publisher.slack_text("_just started recording_")

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

    # def record_note(self, note, velocity, duration, start_time):
    #     if velocity == 0:
    #         velocity = 100
    #
    #     if self._rearm_timeout:
    #         self._rearm_timeout.reset()
    #     if not self._recording and self._armed:
    #         self.start_recording(start_time)
    #     if self._recording:
    #         self._recording_timeout.reset()
    #         self._midifile.append(Message( 0, 0, note, start_time - self._started_recording, duration, velocity)

    def toggle(self):
        if self._armed:
            self.disarm_recording()
        else:
            self.arm_recording()
