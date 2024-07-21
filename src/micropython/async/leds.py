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

    async def light(self, led_nr, values):
        self.neopix[led_nr] = values
        await asyncio.sleep_ms(50)
        self.neopix.write()

    async def dance(self):
        await self.blink()

    async def show_hsv(self, hue, sat, val):
        rgb = await self.colorHSV(hue, sat, val)
        self.neopix[0] = rgb
        self.neopix.write()

    async def colorHSV(self, hue, sat, val):
        """
        Converts HSV color to rgb tuple and returns it.
        The logic is almost the same as in Adafruit NeoPixel library:
        https://github.com/adafruit/Adafruit_NeoPixel so all the credits for that
        go directly to them (license: https://github.com/adafruit/Adafruit_NeoPixel/blob/master/COPYING)

        :param hue: Hue component. Should be on interval 0..65535
        :param sat: Saturation component. Should be on interval 0..255
        :param val: Value component. Should be on interval 0..255
        :return: (r, g, b) tuple
        """

        print("HSV value: ", hue, sat, val)

        if hue >= 65536:
            hue %= 65536

        hue = (hue * 1530 + 32768) // 65536
        if hue < 510:
            b = 0
            if hue < 255:
                r = 255
                g = hue
            else:
                r = 510 - hue
                g = 255
        elif hue < 1020:
            r = 0
            if hue < 765:
                g = 255
                b = hue - 510
            else:
                g = 1020 - hue
                b = 255
        elif hue < 1530:
            g = 0
            if hue < 1275:
                r = hue - 1020
                b = 255
            else:
                r = 255
                b = 1530 - hue
        else:
            r = 255
            g = 0
            b = 0

        v1 = 1 + val
        s1 = 1 + sat
        s2 = 255 - sat

        r = ((((r * s1) >> 8) + s2) * v1) >> 8
        g = ((((g * s1) >> 8) + s2) * v1) >> 8
        b = ((((b * s1) >> 8) + s2) * v1) >> 8

        print("RGB value: ", r, g, b)

        return (r, g, b)