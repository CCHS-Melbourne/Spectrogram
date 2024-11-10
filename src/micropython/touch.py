# Inspired by: https://github.com/peterhinch/micropython-async/blob/master/v3/primitives/pushbutton.py
import time
import asyncio

try:
    from machine import TouchPad
except ImportError:
    pass


class Touch:
    thresh = (80 << 8) // 100   # 80%
    debounce_ms = 50

    def __init__(self, pin):
        self._state = False
        self._tf = False
        self._thresh = 0  # Detection threshold
        self._rawval = 0
        # https://github.com/micropython/micropython/issues/13178#issuecomment-2254331069
        time.sleep_ms(500) # Dirty workaround: Let the sensor stabilise on init
        try:
            print("Initialising touch sensor")
            self._pad = TouchPad(pin)
        except ValueError:
            raise ValueError(pin)  # Let's have a bit of information :)

        #asyncio.run(self.run())

    async def start(self):
        self._state = await self.rawstate()  # Initial state

        while True:
            await self._check(await self.rawstate())
            # Ignore state changes until switch has settled. Also avoid hogging CPU.
            # See https://github.com/peterhinch/micropython-async/issues/69
            await asyncio.sleep_ms(self.debounce_ms)

    async def _check(self, state):
        if state == self._state:
            return
        #State has changed: act on it now.
        self._state = state
        if state:  # Button pressed: launch pressed func
            self._state = False

    async def rawstate(self):
        await asyncio.sleep_ms(100) # Dirty workaround: Let the sensor stabilise
        rv = self._pad.read()  # ~220μs
        print(rv)
        if rv > self._rawval:  # Either initialisation or pad was touched
            self._rawval = rv  # when initialised and has now been released
            self._thresh = (rv * self.thresh) >> 8
            return False  # Untouched
        return rv < self._thresh

