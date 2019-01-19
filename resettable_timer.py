from threading import Thread, Event


def ResettableTimer(*args, **kwargs):
    return _ResettableTimer(*args, **kwargs)


class _ResettableTimer(Thread):
    def __init__(self, interval, fn, args=[], kwargs={}):
        Thread.__init__(self)
        self._interval = interval
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._finished = Event()
        self._reset = True

    def cancel(self):
        self._finished.set()

    def run(self):
        while self._reset:
            self._reset = False
            self._finished.wait(self._interval)

        if not self._finished.isSet():
            self._fn(*self._args, **self._kwargs)
        self._finished.set()

    def reset(self, interval=None):
        if interval:
            self._interval = interval
        self._reset = True
        self._finished.set()
        self._finished.clear()
