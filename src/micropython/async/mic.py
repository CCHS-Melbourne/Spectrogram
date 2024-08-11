from ulab import utils
import math
import asyncio
from leds import Leds
from ulab import numpy as np
from machine import Pin, I2S
from time import ticks_us, ticks_diff

# 512 in the FFT 16000/512 ~ 30Hz update.
# DMA buffer should be at least twice, rounded to power of two.
SAMPLE_RATE = 8000 # Hz
SAMPLE_SIZE = 16
SAMPLE_COUNT = 4096
FREQUENCY_RESOLUTION=SAMPLE_RATE/SAMPLE_COUNT
TUNING_A4_HZ=440.
BINS_PER_OCTAVE=2


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
        
        #Figure out what the frequencies of each A notes in each octave is
        octaves_covered=np.array([1,2,3,4,5,6,7])
        root_octave=4
        #borders are defined as the A frequency in each octave
        self.borders=TUNING_A4_HZ*(2**(octaves_covered-root_octave))
        print(self.borders)
        
        #figure out what tones correspond to what magnitudes out of the fft, with respect to the mic sampling parameters
        self.tones=FREQUENCY_RESOLUTION*np.arange(SAMPLE_COUNT/2)
        #print(self.tones)
        
        crossovers = []

        # Loop through the fixed interval array, finding the index where that boundary is crossed, storing that index and its corresponding frequency in a tuple, appending to a list
        # this is with respect to the mic sampling parameters, again. 
        for i in range(len(self.tones) - 1):
            for boundary in self.borders:
                if self.tones[i] <= boundary < self.tones[i + 1]:
                    crossovers.append((i, self.tones[i]))
        print(crossovers)
        self.fft_ranges=[(tup[0],crossovers[i+1][0]-1) for i, tup in enumerate(crossovers[:-1])]
        print(self.fft_ranges)
                    
    # FIXME: Needs thorough review and optimization, way too slow with 12*3 LEDs as-is
    async def mini_wled(self, samples):
        t0 = ticks_us()

        tfft0 = ticks_us()
        #magnitudes = utils.spectrogram(samples, scratchpad=scratchpad)#, log=True)
        magnitudes = utils.spectrogram(samples)
        tfft1 = ticks_us()
        #print(f'spectrogram:{ticks_diff(tfft1, tfft0):6d} µs')
        

#         fft_ranges = [
#             #define a set of sum ranges where the borders of the bin are the octave frequencies of the note 'A'
#             
#             
#             #(0,84),(85,169),(170,254),(255,339),(340,424),(425,509),(510,594),(595,679),(680,764),(765,849),(850,934),(935,1023)
#             #(22, 39), (40, 70), (71, 126), (127, 226), (227, 403), (404, 718), (719, 1023) #octave per led
#             (19,24),(25,33),(34,44),(45,59),(60,79),(80,106),(107,142),(143,190),(191,254),(255,340),(341,454),(455,607)
#             #(1, 2), (3, 4), (5, 7), (8, 11), (12, 16), (17, 23), (24, 33), (34, 46), (47, 62), (47, 52), (53, 62), (63, 70)
#         ]

        t1 = ticks_us()

        tsc0 = ticks_us()
        fftCalc=[]
        for f in self.fft_ranges:
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
#             t0 = ticks_us()
            await asyncio.StreamReader(self.microphone).readinto(rawsamples)
            samples = np.frombuffer(rawsamples, dtype=np.int16) # 150 µs
#             t1 = ticks_us()
            #print("mic sampling:", ticks_diff(t1, t0))

#             t2 = ticks_us()
            # calculate channels from samples
            channels = await self.mini_wled(samples) # 19863 µs
            #print(channels)
#             t3 = ticks_us()
            
            # Assuming channels is a numpy array
            leds_array = np.array(channels)
            #if scaling only the leds_array, when quiet, the maximum ambient noise dynamically becomes bright, which is distracting, need to make noise an ambient low level of intensity
            brightness_range=np.array([0,255])
            summed_magnitude_range=np.array([0, 50000])
            #scale to 0-255 range, can/should scale up for more hue resolution
            leds_array = np.interp(leds_array, summed_magnitude_range, brightness_range)
            
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
             
#             t4 = ticks_us()
            # Use async to call show_hsv for valid LEDs
            # 114154 µs
            #for i, hue, value in zip(indices[valid_indices], hues[valid_indices], values[valid_indices]):
                #await leds.show_hsv(i, int(hue), 255, int(value/10))
            for i in range(0,len(leds_array)):
                await leds.show_hsv(i, int(hues[i]), 255, int(leds_array[i]))            
#             t5 = ticks_us()
#             print("mic sampling:", ticks_diff(t1, t0),"fft calc and bin sum",ticks_diff(t3,t2),'led_write loop:',ticks_diff(t5, t4))
