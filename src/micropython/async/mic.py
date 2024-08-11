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
        #print(self.borders)
#         note_numbers=
        exponents=(np.arange(1.,77.)-49)/12 #see wikipedia: https://en.wikipedia.org/wiki/Piano_key_frequencies
        #print('exponents: ',exponents)
        self.notes=TUNING_A4_HZ*(2**exponents)
        #print(self.notes)
        self.modes=["Intensity","Synesthesia"]
        self.mode=self.modes[1]
        
        hue_max=65535 #2^16, according to notes in leds.py
        hue_diff=4000
        base_hue=40000
        self.note_hues=np.arange(12.)
        for i in np.arange(len(self.note_hues)):
            self.note_hues[i]=(base_hue+(i*hue_diff))%65535
        print(self.note_hues)
        
        #figure out what tones correspond to what magnitudes out of the fft, with respect to the mic sampling parameters
        self.tones=FREQUENCY_RESOLUTION*np.arange(SAMPLE_COUNT/2)
        print(self.tones)       
        crossovers = []
        # Loop through the fixed interval array, finding the index where that boundary is crossed, storing that index and its corresponding frequency in a tuple, appending to a list
        # this is with respect to the mic sampling parameters, again. 
        for i in range(len(self.tones) - 1):
            for boundary in self.borders:
                if self.tones[i] <= boundary < self.tones[i + 1]:
                    crossovers.append((i, self.tones[i]))
        #print(crossovers)
        self.fft_ranges=[(tup[0],crossovers[i+1][0]-1) for i, tup in enumerate(crossovers[:-1])]
        #print(self.fft_ranges)
                    
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
        dominants=[]
        for f in self.fft_ranges:
            #first block that could be if statemented into a display mode
            slice_sum = np.sum(magnitudes[f[0]:f[1]])
            slice_index_diff = f[1]-f[0]
            normalized_sum = slice_sum/slice_index_diff
            fftCalc.append(normalized_sum)
            #second block that could be if statemented into a display mode
            dominant_mag=np.argmax(magnitudes[f[0]:f[1]])+f[0] #find out where the max magnitude in the slice is, then add the starting index of the slice, or you'll get veeeery odd frequency curves.
            dominant_tone=self.tones[dominant_mag]
            #print("dom mag index",dominant_mag,"tone :",dominant_tone)
            dominants.append(dominant_tone)
        tsc1 = ticks_us()
        #print(f'sum_and_scale:{ticks_diff(tsc1, tsc0):6d} µs')

        #print(f'mini-wled:  {ticks_diff(t1, t0):6d} µs')

        return fftCalc,dominants


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
            channels,dominants = await self.mini_wled(samples) # 19863 µs
            #print('dominants: ', dominants)
#             t3 = ticks_us()
            
            # Assuming channels is a numpy array
            leds_bin_sum = np.array(channels)
            #if scaling only the leds_bin_sum, when quiet, the maximum ambient noise dynamically becomes bright, which is distracting, need to make noise an ambient low level of intensity
            brightness_range=np.array([0,255])
            summed_magnitude_range=np.array([0, 50000])
            #scale to 0-255 range, can/should scale up for more hue resolution
            leds_bin_sum = np.interp(leds_bin_sum, summed_magnitude_range, brightness_range)
            
            if self.mode=="Intensity":            
                # Create masks for different hue ranges
                mask_blue_red = np.where(leds_bin_sum <= 170,1,0)
                #print("mask blue red:", mask_blue_red)
                mask_red_yellow = np.where(leds_bin_sum > 170,1,0)
                #print("mask red yellow:", mask_red_yellow)
                
                # Define ranges and target mappings
                original_range_blue_red = np.array([0, 170])
                target_range_blue_red = np.array([32768, 65535])
                original_range_red_yellow = np.array([171, 255])
                target_range_red_yellow = np.array([0, 16320])
                
                # Interpolate for hues
                hue_blue_red = np.where(mask_blue_red, np.interp(leds_bin_sum, original_range_blue_red, target_range_blue_red),0)
                #print("hue red yellow:", mask_blue_red)
                hue_red_yellow = np.where(mask_red_yellow, np.interp(leds_bin_sum, original_range_red_yellow, target_range_red_yellow),0)
                #print("hue red yellow:", mask_red_yellow)
                
                # Combine hue results
                intensity_hues = np.where(mask_blue_red, hue_blue_red, hue_red_yellow)
                #print('intensity hues',intensity_hues)
                
    #             t4 = ticks_us()
                # Use async to call show_hsv for valid LEDs
                # 114154 µs
                #for i, hue, value in zip(indices[valid_indices], intensity_hues[valid_indices], values[valid_indices]):
                    #await leds.show_hsv(i, int(hue), 255, int(value/10))
                for i in range(0,len(leds_bin_sum)):
                    await leds.show_hsv(i, int(intensity_hues[i]), 255, int(leds_bin_sum[i]))            
    #             t5 = ticks_us()
    
            if self.mode=="Synesthesia":
                dominants_array=np.array(dominants)
                dominants_notes=np.arange(len(dominants_array))
                current_hues=np.arange(0.,len(dominants_array))#This line stumped me for an hour, it initializes as unit16, which causes the note calculation to overflow. Causing negative numbers, causing green spikes of full brightness
                for i in range(len(dominants_array)):
                    note=int(12.*np.log2(dominants_array[i]/440.)+49.)#see wikipedia: https://en.wikipedia.org/wiki/Piano_key_frequencies
                    #print('note: ',note)
                    if note<0:
                        note=0
                    dominants_notes[i]=note%12
                    current_hues[i]=self.note_hues[note%12]
#                 print("dominants_notes:",dominants_notes)
                print("current hues:",current_hues)
                
                for i in range(0,len(leds_bin_sum)):
                    await leds.show_hsv(i, int(current_hues[i]), 255, int(leds_bin_sum[i])) 
    
#             print("mic sampling:", ticks_diff(t1, t0),"fft calc and bin sum",ticks_diff(t3,t2),'led_write loop:',ticks_diff(t5, t4))
