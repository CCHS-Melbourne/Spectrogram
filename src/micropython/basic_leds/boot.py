from time import sleep_ms
from neopixel import NeoPixel
from machine import Pin
import neopixel

NUM_LEDS = 12
LEDS_PIN = 18

pin = Pin(LEDS_PIN, Pin.OUT)
np = NeoPixel(pin, NUM_LEDS)
for led in range(NUM_LEDS):
        np[led] = (80, 80, 80)

for r in range(255):
        np[r % NUM_LEDS] = (r, 100, r)
        sleep_ms(200)
        np.write()
