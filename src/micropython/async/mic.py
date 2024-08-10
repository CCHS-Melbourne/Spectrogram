from ulab import utils
import math
import asyncio
from leds import Leds
from ulab import numpy as np
from machine import Pin, I2S
from time import ticks_us, ticks_diff

# 512 in the FFT 16000/512 ~ 30Hz update.
# DMA buffer should be at least twice, rounded to power of two.
SAMPLE_RATE = 16000 # Hz
SAMPLE_SIZE = 16
SAMPLE_COUNT = 4096

rawsamples = bytearray(SAMPLE_COUNT * SAMPLE_SIZE // 8)
scratchpad = np.zeros(2 * SAMPLE_COUNT) # re-usable RAM for the calculation of the FFT
                                        # avoids memory fragmentation and thus OOM errors

ID = 0
SD = Pin(15)
SCK = Pin(16)
WS = Pin(17)

class Mic():
    def __init__(self):
        self.microphone = I2S(ID, sck=SCK, ws=WS, sd=SD, mode=I2S.RX,
                              bits=SAMPLE_SIZE, format=I2S.MONO, rate=SAMPLE_RATE,
                              ibuf=8096)

    # FIXME: Needs thorough review and optimization, way too slow with 12*3 LEDs as-is
    async def mini_wled(self, samples):
        t0 = ticks_us()

        tfft0 = ticks_us()
        #magnitudes = utils.spectrogram(samples, scratchpad=scratchpad)#, log=True)
        magnitudes = utils.spectrogram(samples)
        tfft1 = ticks_us()
        #print(f'spectrogram:{ticks_diff(tfft1, tfft0):6d} µs')

        fft_ranges = [
            #(0,84),(85,169),(170,254),(255,339),(340,424),(425,509),(510,594),(595,679),(680,764),(765,849),(850,934),(935,1023)
            #(22, 39), (40, 70), (71, 126), (127, 226), (227, 403), (404, 718), (719, 1023) #octave per led
            (19,24),(25,33),(34,44),(45,59),(60,79),(80,106),(107,142),(143,190),(191,254),(255,340),(341,454),(455,607)
            #(1, 2), (3, 4), (5, 7), (8, 11), (12, 16), (17, 23), (24, 33), (34, 46), (47, 62), (47, 52), (53, 62), (63, 70)
        ]

        t1 = ticks_us()

        tsc0 = ticks_us()
        fftCalc=[]
        for f in fft_ranges:
            slice_sum = np.sum(magnitudes[f[0]:f[1]])
            slice_diff = f[1]-f[0]
            normalized_sum = slice_sum/slice_diff
            fftCalc.append(normalized_sum)
        tsc1 = ticks_us()
        #print(f'sum_and_scale:{ticks_diff(tsc1, tsc0):6d} µs')

        #print(f'mini-wled:  {ticks_diff(t1, t0):6d} µs')

        return fftCalc


    async def start(self):
        leds = Leds()

        # mic while True: 237412 µs
        while True:
            # mic sampling:102448 µs
            t0 = ticks_us()
            await asyncio.StreamReader(self.microphone).readinto(rawsamples)
            samples = np.frombuffer(rawsamples, dtype=np.int16) # 150 µs
            t1 = ticks_us()
            #print("mic sampling:", ticks_diff(t1, t0))

            #t2 = ticks_us()
            # calculate channels from samples
            channels = await self.mini_wled(samples) # 19863 µs
            #print(channels)
            #t3 = ticks_us()
            
            # Assuming channels is a numpy array
            leds_array = np.array(channels)
            #scale to 0-255 range, can/should scale up for more hue resolution
            leds_array = (leds_array/np.max(leds_array[:]))*255
            
            # Create masks for different hue ranges
            mask_blue_red = np.where(leds_array <= 170,1,0)
            #print("mask blue red:", mask_blue_red)
            mask_red_yellow = np.where(leds_array > 170,1,0)
            #print("mask red yellow:", mask_red_yellow)
            
            # Define ranges and target mappings
            original_range_blue_red = np.array([0, 170])
            target_range_blue_red = np.array([32768, 65535])
            original_range_red_yellow = np.array([171, 255])
            target_range_red_yellow = np.array([0, 16320])
            
            # Interpolate for hues
            hue_blue_red = np.where(mask_blue_red, np.interp(leds_array, original_range_blue_red, target_range_blue_red),0)
            #print("hue red yellow:", mask_blue_red)
            hue_red_yellow = np.where(mask_red_yellow, np.interp(leds_array, original_range_red_yellow, target_range_red_yellow),0)
            #print("hue red yellow:", mask_red_yellow)
            
            # Combine hue results
            hues = np.where(mask_blue_red, hue_blue_red, hue_red_yellow)
            #print(hues)
            # Calculate value based on LED
            #values = np.where(leds_array != float("-inf"), np.clip(leds_array / 200, 0, 255), 0)
            
            # Prepare indices and valid LEDs
            #indices = np.arange(len(channels))
            
            # Filter out invalid LEDs
            #valid_indices = leds_array != float("-inf")
            
            #t4 = ticks_us()
            # Use async to call show_hsv for valid LEDs
            # 114154 µs
            #for i, hue, value in zip(indices[valid_indices], hues[valid_indices], values[valid_indices]):
                #await leds.show_hsv(i, int(hue), 255, int(value/10))
            for i in range(0,len(leds_array)):
                await leds.show_hsv(i, int(hues[i]), 255, int(leds_array[i]))            
            #t5 = ticks_us()
            #print("mic sampling:", ticks_diff(t1, t0),'led_write loop:',ticks_diff(t5, t4))
