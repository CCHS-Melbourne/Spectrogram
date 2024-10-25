import neopixel
from machine import Pin
from time import sleep

# Set up the NeoPixel on pin 15 with 8 LEDs (adjust pin and number of LEDs)
pin = Pin(10, Pin.OUT)
num_leds = 36
np = neopixel.NeoPixel(pin, num_leds)

# Function to light up all LEDs in red
def set_all_leds(color):
    for i in range(num_leds):
        np[i] = color
    np.write()

while True:
    set_all_leds((55, 0, 0))  # Set all LEDs to red (R, G, B)
    sleep(1)
    set_all_leds((0, 0, 0))    # Turn off all LEDs
    sleep(1)