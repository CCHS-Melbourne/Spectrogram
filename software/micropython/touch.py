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
        self.state = False
        self.rv = 0
        self._maxrawval = 0
        
        self.no_touch=50000
        self.no_touch_noise=40000
        self.hard_coded_no_touch=self.no_touch
        self.no_touch_noises=[]
        self.one_touch=65000
        self.hard_coded_touch=self.one_touch
        self.one_touch_noise=40000
        self.no_touch_noises=[]
        
        try:
            print("Initialising touch sensor")
            self._pad = TouchPad(pin)
        except ValueError:
            raise ValueError(pin)  # Let's have a bit of information :)

        #asyncio.run(self.run())

    async def start(self):
        self.state = await self.rawstate()  # Initial state

        while True:
            await self.rawstate()
#             await self._check(await self.rawstate())
            # Ignore state changes until switch has settled. Also avoid hogging CPU.
            # See https://github.com/peterhinch/micropython-async/issues/69
            await asyncio.sleep_ms(self.debounce_ms)

#     async def _check(self, state):
#         if state == self.state:
#             return
#         #State has changed: act on it now.
#         self.state = state
#         if state:  # Button pressed: launch pressed func
#             self.state = False

    async def rawstate(self):
        self.rv = self._pad.read()  # ~220μs
        
        if (self.rv > self.hard_coded_touch):
            self.state=True
        if (self.rv < self.hard_coded_no_touch):
            self.state=False

        #code that intended to follow the unpressed touch value and update the threshold/noise, however, it introduced sticky buttons when buttons were half touched.
#         if (self.rv < (self.no_touch - self.no_touch_noise)):
#             self.no_touch=(self.no_touch*0.85 + self.rv*0.15) #refine the measurement of the average no_touch value
#     
#         if ((self.no_touch - self.no_touch_noise) < self.rv < (self.no_touch + self.no_touch_noise)):
#             self.state=False
#             self.no_touch=(self.no_touch*0.85 + self.rv*0.15) #refine the measurement of the average no_touch value
# 
#         if (self.rv > (self.no_touch + self.no_touch_noise)):
#            self.state=True   
#         
#         if self.rv > self._maxrawval:  # Either initialisation or pad was touched
#             self._maxrawval = (self.rv * self._maxrawval) >> 8 #this computes and sets a value that i think was intended to be a trigger, but works as a maximum detected value.     
#         
        return
        

