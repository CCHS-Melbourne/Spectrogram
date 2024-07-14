import time
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

    def blink(self):
        for round in range(100):
            self.neopix[0] = (80, 80, 80)
            time.sleep(0.5)
            self.neopix[0] = (200, 200, 200)
            time.sleep(0.5)
            self.neopix.write()
        
    def dance(self):
        self.blink()