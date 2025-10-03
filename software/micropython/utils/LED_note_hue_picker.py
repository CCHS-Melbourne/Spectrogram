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
#				a			a#			b			c			c#			d			d#		e			f			f#			g			g#
picked_hues=[(255,0,0),(255,30,30),(255,60,0),(255,255,0),(255,255,30),(0,255,0),(80,220,10),(0,155,255),(0,0,255),(50,0,255),(255,0,255),(255,255,255)]
brightness=0.1

scaled_hues=[tuple(int(x*brightness) for x in t) for t in picked_hues]
print(scaled_hues)

for i in range(len(picked_hues)):
    leds0[i] = scaled_hues[i]
    leds1[i] = scaled_hues[i]
    leds2[i] = scaled_hues[i]

leds0.write()
leds1.write()
leds2.write()

