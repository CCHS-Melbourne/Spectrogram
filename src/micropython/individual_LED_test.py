import neopixel
from machine import Pin
from time import sleep

# Set up the NeoPixel on pin 15 with 8 LEDs (adjust pin and number of LEDs)
pin = Pin(10, Pin.OUT)
num_leds = 36
np = neopixel.NeoPixel(pin, num_leds)   

np[1] = (0,0,40)
np.write()

