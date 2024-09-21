import neopixel
from machine import Pin
from time import sleep

# Set up the NeoPixel strip
pin = Pin(10, Pin.OUT)  # Change to your NeoPixel pin
num_leds = 36           # Change to the number of LEDs in your strip
np = neopixel.NeoPixel(pin, num_leds)

# Function to fill the strip with a single color
def fill(color):
    for i in range(num_leds):
        np[i] = color
    np.write()

# Function for a color chase effect
def color_chase(color, delay=0.1):
    for i in range(num_leds):
        np[i] = color
        np.write()
        sleep(delay)
#     fill((0, 0, 0))  # Turn off LEDs at the end

def color_fade(delay=0.1):
    for i in range(num_leds):
        np[i] = (0,0,0)
        np.write()
        sleep(delay)

def scale_brightness(color, brightness):
    return tuple(int(c * brightness) for c in color)

# Function for rainbow effect
def wheel(pos):
    # Generate rainbow colors across 0-255 positions.
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)

def rainbow_cycle(wait=0.01):
    for j in range(255):
        for i in range(num_leds):
            rc_index = (i * 256 // num_leds) + j
            np[i] = scale_brightness(wheel(rc_index & 255),0.25)
        np.write()
        sleep(wait)

# Demo reel
while True:
    fill((50, 0, 0))   # Red
    sleep(1)
    fill((0, 50, 0))   # Green
    sleep(1)
    fill((0, 0, 50))   # Blue
    sleep(1)
    color_fade()
    color_chase((40, 40, 0))  # Yellow color chase
    color_fade()
    sleep(1)
    rainbow_cycle()
    rainbow_cycle()
    rainbow_cycle()# Rainbow cycle effect
    sleep(1)
