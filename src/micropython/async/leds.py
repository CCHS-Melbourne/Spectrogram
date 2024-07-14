import asyncio
from random import randint
from neopixel import NeoPixel
from machine import Pin

NUM_LEDS = 1
LEDS_PIN = 38

class Leds():
    def __init__(self):
        gpio = Pin(LEDS_PIN, Pin.OUT)
        self.neopix = NeoPixel(gpio, NUM_LEDS)

    def __iter__(self):
        pass

    async def blink(self):
        for round in range(1000):
            self.neopix[0] = (randint(1,255), randint(1,255), randint(1,255))
            await asyncio.sleep_ms(50)
            self.neopix[0] = (randint(1,255), randint(1,255), randint(1,255))
            await asyncio.sleep_ms(50)
            self.neopix.write()

    async def dance(self):
        await self.blink()