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

        self.modes=["Intensity","Synesthesia"]
        
        #event required to change this mode
        self.change_display_mode(1)
        
        #event required to change this value
        self.noise_floor=100
        
        #calculate the defined frequencies of the musical notes         
        notes=np.arange(1.,85.)
        note_frequencies=TUNING_A4_HZ*(2**((notes-49)/12))
        #print("note frequencies: ", note_frequencies)
        
        #event required to change note_per_led number
        notes_per_led=2  #[1,2,3,4,6,12]
        
        #array splice the notes according to the user defined values
        #event required to change note at start of array slice 
        start_note=12
        borders=note_frequencies[start_note::notes_per_led]
        borders=borders[start_note:start_note+13:]
        #print(len(borders))
        
        #figure out what tones correspond to what magnitudes out of the fft, with respect to the mic sampling parameters
        self.tones=FREQUENCY_RESOLUTION*np.arange(SAMPLE_COUNT/2)
        #print(self.tones)       
        self.calculate_fft_bin_boundaries(borders)
        
#         self.set_hues()
        hue_max=65535 #2^16, according to docs in leds.py
        hue_diff=5000
        base_hue=40000
        self.note_hues=np.arange(12.)
        for i in np.arange(len(self.note_hues)):
            self.note_hues[i]=(base_hue+(i*hue_diff))%65535
        #print(self.note_hues)      
    
    def calculate_LED_note_borders():
        pass
    
    def calculate_fft_bin_boundaries(self, borders):    
        crossovers = []
        # Loop through the fixed note interval array, finding the index where that boundary is crossed, storing that index and its corresponding frequency in a tuple, appending to a list
        # this is with respect to the mic sampling parameters, again. 
        for i in range(len(self.tones) - 1):
            for boundary in borders:
                if self.tones[i] <= boundary < self.tones[i + 1]:
                    crossovers.append((i, self.tones[i]))
        #print(crossovers)
        self.fft_ranges=[(tup[0],crossovers[i+1][0]-15) for i, tup in enumerate(crossovers[:-1])]
        print(self.fft_ranges)
    
    def change_display_mode(self,mode):
        self.mode=self.modes[mode]
        
    def change_noise_floor():
        pass
    
    # FIXME: Needs thorough review and optimization, way too slow with 12*3 LEDs as-is
    async def mini_wled(self, samples):
        #magnitudes = utils.spectrogram(samples, scratchpad=scratchpad)#, log=True) #Roooooooman, this log looks like it could have been very handy
        magnitudes = utils.spectrogram(samples)
        #print(self.tones[125:127])
        
        fftCalc=[]
        dominants=[]
        for f in self.fft_ranges:
            #first block that could be if statemented into a display mode
            slice_sum = np.sum(magnitudes[f[0]:f[1]])
            slice_index_diff = f[1]-f[0]
            try:
                normalized_sum = slice_sum/slice_index_diff
                if normalized_sum < self.noise_floor:
                    normalized_sum=0
                    dominant_mag = magnitudes[f[0]] #not ideal but doesn't matter, as the tone will be set to zero brightness
                    dominant_tone = self.tones[f[0]]
                #second block that could be if statemented into a display mode
                else:
                    where_dominant_mag=np.argmax(magnitudes[f[0]:f[1]])+f[0] #find out where the max magnitude in the slice is, then add the starting index of the slice, or you'll get veeeery odd frequency curves.
                    dominant_tone=self.tones[where_dominant_mag]

            except ZeroDivisionError: #which crops up if the number of notes in a bin is too few, as in low note_per_bin cases
                if normalized_sum < self.noise_floor:
                    normalized_sum=0
                    dominant_mag = magnitudes[f[0]]
                    dominant_tone = self.tones[f][0]

                else:
                    normalized_sum = slice_sum
                    dominant_mag = magnitudes[f[0]]
                    dominant_tone = self.tones[f[0]]

            fftCalc.append(normalized_sum)
            
            #print("dom mag index",dominant_mag,"tone :",dominant_tone)
            dominants.append(dominant_tone)
            
        
        num_led_bins_calculated=12#don;t think this is needed anymore, due to calculations around fft bins above
        if len(fftCalc)>num_led_bins_calculated:
            fftCalc=fftCalc[:num_led_bins_calculated:]
            dominants=dominants[:num_led_bins_calculated:]
        
        print(fftCalc)
#         print(dominants)
        return fftCalc,dominants


    async def start(self):
        leds = Leds()
        while True:
#             t0 = ticks_us()
            await asyncio.StreamReader(self.microphone).readinto(rawsamples)
            samples = np.frombuffer(rawsamples, dtype=np.int16) # 150 µs
#             t1 = ticks_us()
                        
#             t2 = ticks_us()
            # calculate fft_mag from samples
            fft_mags,dominants = await self.mini_wled(samples) # 19863 µs
#             t3 = ticks_us()
            
            
            
            # Assuming fft_mags is a numpy array
            fft_mags_array = np.array(fft_mags)
            #if scaling only the fft_mags_array, when quiet, the maximum ambient noise dynamically becomes bright, which is distracting, need to make noise an ambient low level of intensity
            brightness_range=np.array([0,255])
            summed_magnitude_range=np.array([0, 50000])
            #scale to 0-255 range, can/should scale up for more hue resolution
            fft_mags_array = np.interp(fft_mags_array, summed_magnitude_range, brightness_range)
            
            #apply cosmetics to values calculated above 
            if self.mode=="Intensity":            
                # Create masks for different hue ranges
                mask_blue_red = np.where(fft_mags_array <= 170,1,0)
                #print("mask blue red:", mask_blue_red)
                mask_red_yellow = np.where(fft_mags_array > 170,1,0)
                #print("mask red yellow:", mask_red_yellow)
                
                # Define ranges and target mappings
                original_range_blue_red = np.array([0, 170])
                target_range_blue_red = np.array([32768, 65535])
                original_range_red_yellow = np.array([171, 255])
                target_range_red_yellow = np.array([0, 16320])
                
                # Interpolate for hues
                hue_blue_red = np.where(mask_blue_red, np.interp(fft_mags_array, original_range_blue_red, target_range_blue_red),0)
                #print("hue red yellow:", mask_blue_red)
                hue_red_yellow = np.where(mask_red_yellow, np.interp(fft_mags_array, original_range_red_yellow, target_range_red_yellow),0)
                #print("hue red yellow:", mask_red_yellow)
                
                # Combine hue results
                intensity_hues = np.where(mask_blue_red, hue_blue_red, hue_red_yellow)
                #print('intensity hues',intensity_hues)
                
    #             t4 = ticks_us()
                # Use async to call show_hsv for valid LEDs
                # 114154 µs
                #for i, hue, value in zip(indices[valid_indices], intensity_hues[valid_indices], values[valid_indices]):
                    #await leds.show_hsv(i, int(hue), 255, int(value/10))
                for i in range(0,len(fft_mags_array)):
                    await leds.show_hsv(i, int(intensity_hues[i]), 255, int(fft_mags_array[i]))            
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
#                 print("current hues:",current_hues)
                
                for i in range(0,len(fft_mags_array)):
                    #await leds.show_hsv(i, 0, 0, 0) #the actual issue seems to be coming from the fft
                    await leds.show_hsv(i, int(current_hues[i]), 255, int(fft_mags_array[i])) 
    
#             print("mic sampling:", ticks_diff(t1, t0),"fft calc and bin sum",ticks_diff(t3,t2),'led_write loop:',ticks_diff(t5, t4))
