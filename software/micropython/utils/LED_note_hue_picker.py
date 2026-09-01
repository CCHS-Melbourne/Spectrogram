import neopixel
from machine import Pin
from time import sleep
from leds import Leds

# Set up the NeoPixel on pin 15 with 8 LEDs (adjust pin and number of LEDs)
pin0 = Pin(6, Pin.OUT)
pin1 = Pin(8, Pin.OUT)
pin2 = Pin(7, Pin.OUT)

num_leds = 36
leds0 = neopixel.NeoPixel(pin0, num_leds)   
leds1 = neopixel.NeoPixel(pin1, num_leds)   
leds2 = neopixel.NeoPixel(pin2, num_leds)   



#testing Asharp peach[(255,0,0),(255,30,30),(255,60,0),(255,255,0),(80,255,0),(0,255,0),(0,255,30),(0,155,255),(0,0,255),(50,0,255),(255,0,255),(255,0,255),]
#not a bad spectrum[(255,30,30),(255,0,0),(255,60,0),(255,255,0),(80,255,0),(0,255,0),(0,255,30),(0,155,255),(0,0,255),(50,0,255),(255,0,255),(255,0,255),]
#					a			a#				b			c			c#				d			d#				e			f				f#			g				g#
#rainbow syn hues
# picked_hues=[(255,000,000),(255,030,030),(255,060,00),(255,255,000),(255,255,030),(000,255,000),(080,220,010),(000,155,255),(000,000,255),(050,000,255),(255,000,255),(255,255,255)]

#plasma syn hues
#calculated with the clb.generalised_color_LUT then manually adding sharps, then just full manual, sigh
#bump for brightness of sharp/flat notes

#full manual#picked_hues=[(0,0,255),(0,155,255),(050,000,255), (255,015,080), (255,000,000), (255,077,000), (255,201,000), (255,255,028), (255,255,237)]
brightness=0.4

scaled_hues=[tuple(int(x*brightness) for x in t) for t in picked_hues]
print(scaled_hues)

for i in range(len(picked_hues)):
    leds0[i] = scaled_hues[i]
    leds1[i] = scaled_hues[i]
    leds2[i] = scaled_hues[i]

leds0.write()
leds1.write()
leds2.write()

