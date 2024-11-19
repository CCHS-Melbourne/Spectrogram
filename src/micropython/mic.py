from ulab import utils
import math
import asyncio
from leds import Leds
from ulab import numpy as np
from machine import Pin, I2S
from time import ticks_ms, ticks_diff

# 512 in the FFT 16000/512 ~ 30Hz update.
# DMA buffer should be at least twice, rounded to power of two.
SAMPLE_RATE = 8000 # Hz
SAMPLE_SIZE = 16
SAMPLE_COUNT = 4096
FREQUENCY_RESOLUTION=SAMPLE_RATE/SAMPLE_COUNT
TUNING_A4_HZ=440.
BINS_PER_OCTAVE=2

# Size of the I2S DMA buffer, the smaller this is then the
# faster each loop iteration can update the LEDs
I2S_SAMPLE_COUNT = 512

I2S_SAMPLE_BYTES = I2S_SAMPLE_COUNT * SAMPLE_SIZE // 8

# Code below assumes the I2S buffer size is an exact multiple of the sample count
assert(SAMPLE_COUNT % I2S_SAMPLE_COUNT == 0)

# Tuning:
#
# - The smaller SAMPLE_COUNT is then the more quickly responsive the LEDs will
#   be. Limit will be a minimum buffer size before the FFT results don't work
#   (TODO: calculate this?)
#
# - The smaller I2S_SAMPLE_COUNT then the higher the update rate for the LEDs so
#   they'll look less jittery. Limit will be a minimum where the CPU can't
#   keep up (because need to perform FFT on full SAMPLE_COUNT for each iteration.)

samples = np.zeros(SAMPLE_COUNT, dtype=np.int16)
sample_bytearray = samples.tobytes()  # bytearray points to the sample samples array
scratchpad = np.zeros(2 * SAMPLE_COUNT) # re-usable RAM for the calculation of the FFT
                                        # avoids memory fragmentation and thus OOM errors

ID = 0
SD = Pin(7)
SCK = Pin(8)
WS = Pin(9)

class Mic():
    def __init__(self):
        self.microphone = I2S(ID, sck=SCK, ws=WS, sd=SD, mode=I2S.RX,
                                bits=SAMPLE_SIZE, format=I2S.MONO, rate=SAMPLE_RATE,
                                ibuf=I2S_SAMPLE_BYTES)

        self.modes=["Intensity","Synesthesia"]

        # Event required to change this mode
        self.change_display_mode(0)

        # Event required to change this value
        self.noise_floor=1000
        
        # Event required to change this value
        self.brightness=0.2 #[0-1]
        
        # Calculate the defined frequencies of the musical notes
        notes=np.arange(1.,85.)
        note_frequencies=TUNING_A4_HZ*(2**((notes-49)/12))
        #print("note frequencies: ", note_frequencies)

        # Event required to change note_per_led number
        notes_per_led=4  #[1,2,3,4,6,12]

        self.length_of_leds=13 #actually needs to be number of leds+1, due to how the note border finding/zipping function organizes borders
        self.ring_buffer_hues=np.zeros((3,self.length_of_leds-1))
        self.ring_buffer_intensities=np.zeros((3,self.length_of_leds-1))
        self.buff_index=0

        # Array splice the notes according to the user defined values
        # Event required to change note at start of array slice

        start_note=15

        # This creates a border exactly on a note. What is needed is a border halfway between one note and the next.
        # I have frequencies, I need to know what note is at the border, index the next note, and take the middle
        #borders=note_frequencies[start_note::notes_per_led]

        borders=np.zeros(self.length_of_leds)
        for i in range(self.length_of_leds):
            start_=note_frequencies[start_note+(i*notes_per_led)]
            next_=note_frequencies[start_note+(i*notes_per_led)+1]
            border_location=start_+(next_-start_)/2
            borders[i]=border_location

        # Figure out what tones correspond to what magnitudes out of the fft, with respect to the mic sampling parameters
        self.tones=FREQUENCY_RESOLUTION*np.arange(SAMPLE_COUNT/2)
        self.calculate_fft_bin_boundaries(borders)

        # Set the colours of notes in synaesthesia mode
        hue_max=65535 #2^16, according to docs in leds.py
        hue_diff=5000
        base_hue=40000
        self.note_hues=np.arange(12.)
        for i in np.arange(len(self.note_hues)):
            self.note_hues[i]=(base_hue+(i*hue_diff))%65535

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
        self.fft_ranges=[(tup[0],crossovers[i+1][0]) for i, tup in enumerate(crossovers[:-1])]
        #print(self.fft_ranges)

    def change_display_mode(self,mode):
        self.mode=self.modes[mode]

    def change_noise_floor():
        pass

    async def mini_wled(self, samples):
        #magnitudes = utils.spectrogram(samples, scratchpad=scratchpad)#, log=True)
        #magnitudes = utils.spectrogram(samples, scratchpad=scratchpad)
        magnitudes = utils.spectrogram(samples)
        #print("mags",magnitudes)
        
        fftCalc=[]
        dominants=[]

        for f in self.fft_ranges:
            # First block that could be if statemented into a display mode
            slice_sum = np.sum(magnitudes[f[0]:f[1]])
            slice_index_diff = f[1]-f[0]
            try:
                normalized_sum = slice_sum/slice_index_diff
                if normalized_sum < self.noise_floor:
                    normalized_sum=0
                    dominant_mag = magnitudes[f[0]] # Not ideal but doesn't matter, as the tone will be set to zero brightness
                    dominant_tone = self.tones[f[0]]
                # Second block that could be if statemented into a display mode
                else:
                    # Find out where the max magnitude in the slice is, then add the starting index of the slice,
                    # or you'll get veeeery odd frequency curves.
                    where_dominant_mag=np.argmax(magnitudes[f[0]:f[1]])+f[0] 
                    dominant_tone=self.tones[where_dominant_mag]

            # Crops up if the number of notes in a bin is too few.
            # As in low note_per_bin cases.
            except ZeroDivisionError:
                if normalized_sum < self.noise_floor:
                    normalized_sum=0
                    dominant_mag = magnitudes[f[0]]
                    dominant_tone = self.tones[f[0]]
                else:
                    normalized_sum = slice_sum
                    dominant_mag = magnitudes[f[0]]
                    dominant_tone = self.tones[f[0]]

            fftCalc.append(normalized_sum)
            dominants.append(dominant_tone)

        num_led_bins_calculated=self.length_of_leds
#         print("len of fftCalc in wled",len(fftCalc))
        if len(fftCalc)>num_led_bins_calculated:
            fftCalc=fftCalc[:num_led_bins_calculated:]
            dominants=dominants[:num_led_bins_calculated:]

        return fftCalc,dominants


    async def start(self):
        leds = Leds()
        flag = asyncio.ThreadSafeFlag()

        # Define the callback for the IRQ that sets the flag
        def irq_handler(noop):
            print("MIC IRQ!")
            flag.set()

        # Attach the IRQ handler
        self.microphone.irq(irq_handler)


        sample_view = memoryview(sample_bytearray)  # save an allocation by reusing this
        n_slice = 0

        # Discard initial garbage, also need to do an initial read so IRQ starts triggering
        self.microphone.readinto(sample_bytearray)

        t_mic_sample = None
        while True:
            t_awaiting = ticks_ms()
            if t_mic_sample:
                print("sample processing: ", ticks_diff(t_awaiting, t_mic_sample), "ms")

            await flag.wait()

            t_mic_sample = ticks_ms()
            # this number should be non-zero, so the other coros can run. but if it's large
            # then can probably tune the buffer sizes to get more responsiveness
            print("time spent awaiting: ", ticks_diff(t_mic_sample, t_awaiting), "ms")

            t0 = ticks_ms()

            # Set up a slice into I2S_SAMPLE_COUNT samples of the 'samples'
            # array, viewed as an unstructured bytearray
            start_idx = n_slice * I2S_SAMPLE_BYTES
            end_idx = start_idx + I2S_SAMPLE_BYTES
            read_slice = sample_view[start_idx:end_idx]

            # Read I2S samples into just this slice of bytes
            num_read = self.microphone.readinto(read_slice) # 1ms !

            assert(num_read == I2S_SAMPLE_BYTES)  # if not true then need to be a bit more tricky about measuring slices

            # Increment for the next rolling chunk of samples
            n_slice += 1
            if n_slice * I2S_SAMPLE_COUNT == SAMPLE_COUNT:
                n_slice = 0

            # Perform FFT over the entire 'samples' buffer, not just the small I2S_SAMPLE_COUNT chunk of it

            t1 = ticks_ms()
            #print("mic sampling:  ", ticks_diff(t1, t0) , "ms")

            # calculate fft_mag from samples
            fft_mags,dominants = await self.mini_wled(samples)
            t2 = ticks_ms()
            #print("wled function:", ticks_diff(t2, t1), "ms") # 40ms

            # Assuming fft_mags is a numpy array
            fft_mags_array_raw = np.array(fft_mags)
            V_ref=8388607 #this value is microphone dependant, for the DFROBOT mic, which is 24-bit I2S audio, that value is apparently 8,388,607 
            db_scaling=np.array([20*math.log10(fft_mags_array_raw[index]/V_ref) if value != 0 else -80 for index, value in enumerate(fft_mags_array_raw) ]) #the magic number -80 in this code is -80db, the lowest value on my phone spectrogram app, but it's typically recommended to be -inf
            #print(db_scaling)

            # FFTscaling only the fft_mags_array, when quiet, the maximum ambient noise dynamically becomes bright, which is distracting.
            # We need to make noise an ambient low level of intensity
            brightness_range=np.array([0,255])
            highest_db=-40
            summed_magnitude_range=np.array([-80, highest_db]) #values chosen by looking at my spectrogram. I think a value of zero is a shockwave.
            
            #scale to 0-255 range, can/should scale up for more hue resolution
            fft_mags_array = np.interp(db_scaling, summed_magnitude_range, brightness_range)
            #(fft_mags_array)
            
            # Apply cosmetics to values calculated above
            if self.mode=="Intensity":
                # Create masks for different hue ranges
                mask_blue_red = np.where(fft_mags_array <= 170,1,0)
                mask_red_yellow = np.where(fft_mags_array > 170,1,0)

                # Define ranges and target mappings
                original_range_blue_red = np.array([0, 170])
                target_range_blue_red = np.array([32768, 65535])
                original_range_red_yellow = np.array([171, 255])
                target_range_red_yellow = np.array([0, 16320])

                # Interpolate for hues
                hue_blue_red = np.where(mask_blue_red, np.interp(fft_mags_array, original_range_blue_red, target_range_blue_red),0)
                hue_red_yellow = np.where(mask_red_yellow, np.interp(fft_mags_array, original_range_red_yellow, target_range_red_yellow),0)

                # Combine hue results
                intensity_hues = np.where(mask_blue_red, hue_blue_red, hue_red_yellow)

                # Use async to call show_hsv for valid LEDs
                for i in range(0,len(fft_mags_array)):
#                     self.channel1hues[i][self.bufferIndex+1%3]=hue 
                    await leds.show_hsv(i, int(intensity_hues[i]), 255, int((fft_mags_array[i])*self.brightness))
                    #sorry about the -1s in the first terms, those are due to the length_of_leds being reduced by other array calculations/border conditions 
                    #the negative modulo terms in the second and fourth terms, however, are needed to get the ring buffer to work. 
                    await leds.show_hsv(i+self.length_of_leds-1, int(self.ring_buffer_hues[(self.buff_index-2)%-3][i]), 255, int((self.ring_buffer_intensities[(self.buff_index-2)%-3][i])*self.brightness))
                    await leds.show_hsv(i+self.length_of_leds*2-2, int(self.ring_buffer_hues[(self.buff_index-1)%-3][i]), 255, int((self.ring_buffer_intensities[(self.buff_index-1)%-3][i])*self.brightness))
#                 print("length of buffer",len(self.ring_buffer_hues[(self.buff_index-1)%-3]))
#                 print("length of fft_mags",len(fft_mags_array))
                self.ring_buffer_hues[(self.buff_index-1)%-3]=intensity_hues
                self.ring_buffer_intensities[(self.buff_index-1)%-3]=fft_mags_array
                self.buff_index-=1
                self.buff_index%=-3
                await leds.write() #Is this a performance gain? Only write LEDs when all of the data points have been updated. This replaces the neopix.write() in the leds.py show_hsv function, which peforms the write opertation for each pixel
            
                    
###See line 50, need to have a 'buffer' for intensities and for magnitudes,  
#                     await leds.show_hsv(i*2, int(intensity_hues[i]), 255, int(fft_mags_array[i]))
#                     await leds.show_hsv(i*3, int(intensity_hues[i]), 255, int(fft_mags_array[i]))
#    
#                 self.bufferIndex+=1
#                 self.bufferIndex%=3 #update ring buffer index

            t3 = ticks_ms()
            if self.mode=="Synesthesia":
                dominants_array=np.array(dominants)
                dominants_notes=np.arange(len(dominants_array))
                # This line stumped me for an hour: it initializes as unit16, which causes the note calculation to overflow.
                # Causing negative numbers, causing green spikes of full brightness (FIXME)
                current_hues=np.arange(0.,len(dominants_array))

                for i in range(len(dominants_array)):
                    # See wikipedia: https://en.wikipedia.org/wiki/Piano_key_frequencies
                    note=int(12.*np.log2(dominants_array[i]/440.)+49.)
                    if note<0:
                        note=0
                    dominants_notes[i]=note%12
                    current_hues[i]=self.note_hues[note%12]

                for i in range(0,len(fft_mags_array)):
                    await leds.show_hsv(i, int(current_hues[i]), 255, int(fft_mags_array[i]))

            #print("synesthesia :    ", ticks_diff(t3, t2), "ms") # 2ms !
