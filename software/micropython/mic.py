from ulab import utils
import json
import math
import asyncio
from leds import Leds
from ulab import numpy as np
from machine import Pin, I2S
from time import ticks_ms, ticks_diff
from border_calculator import PrecomputedValues

# 512 in the FFT 16000/512 ~ 30Hz update.
# DMA buffer should be at least twice, rounded to power of two.
SAMPLE_RATE = 8000 # Hz
SAMPLE_SIZE = 16
SAMPLE_COUNT = 4096 #8192 #
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
SD = Pin(11)
SCK = Pin(9)
WS = Pin(10)

class Mic():
    def __init__(self):
        self.microphone = I2S(ID, sck=SCK, ws=WS, sd=SD, mode=I2S.RX,
                                bits=SAMPLE_SIZE, format=I2S.MONO, rate=SAMPLE_RATE,
                                ibuf=I2S_SAMPLE_BYTES)

        self.modes=["Intensity","Synesthesia"]
        self.menu_pix=[[],[],[],[],[],[],[],[],[],[],[],[]]#12 values to fill.
        
        self.show_menu_in_mic=True
        self.menu_thing_updating="brightness"
        self.menu_update_required=True
        
        self.max_db_set_point=-40
        self.highest_db=-40
        self.lowest_db=-80
        
        self.start_note=0
        
        
        # Event required to change this mode
#         self.change_display_mode(0)
        self.mode=self.modes[0]
        
        # Event required to change this value
        self.noise_floor=1000
        
        # Event required to change this value
        self.brightness=20 #[0-255]
        
        # Calculate the defined frequencies of the musical notes
        self.notes=np.arange(1.,85.)
        self.note_frequencies=TUNING_A4_HZ*(2**((self.notes-49)/12))
        ##print("note frequencies: ", note_frequencies)

        # Event required to change note_per_led number
        self.notes_per_led_index=3
        self.notes_per_led_options=[1,2,3,4,6,12]
        self.notes_per_led=self.notes_per_led_options[self.notes_per_led_index]
        
        #load precomputed values and select the dictionary entry that corresponds to the current notes_per_led option
        #create two buffers to avoid async clashes
        self.precomputed_borders=PrecomputedValues("test_speedup_redo_values.json")
        if self.precomputed_borders.load():
            JSON_boot=self.precomputed_borders.get(str(self.notes_per_led))
            self.fft_ranges_buffer_a=JSON_boot[self.start_note:12]
            self.fft_ranges_buffer_b=JSON_boot[self.start_note:12]
#             print("FFT_ranges: ", self.fft_ranges_buffer_a)
        #create buffer pointers
        self.active_buffer='a'
        self.fft_ranges_to_operate_with=self.fft_ranges_buffer_a
        #create update flags
        self.update_queued=False
        self.next_data_key=None        
        
        self.length_of_leds=13 #actually needs to be number of leds+1, due to how the note border finding/zipping function organizes borders
        self.ring_buffer_hues=np.zeros((3,self.length_of_leds-1))
        self.ring_buffer_intensities=np.zeros((3,self.length_of_leds-1))
        self.buff_index=0

        # Figure out what tones correspond to what magnitudes out of the fft, with respect to the mic sampling parameters
        self.tones=FREQUENCY_RESOLUTION*np.arange(SAMPLE_COUNT/2)

        # Set the colours of notes in synaesthesia mode
        hue_max=65535 #2^16, according to docs in leds.py
        hue_diff=5000
        base_hue=40000
        self.note_hues=np.arange(12.)
        for i in np.arange(len(self.note_hues)):
            self.note_hues[i]=(base_hue+(i*hue_diff))%65535

    def schedule_update(self,str_to_update):
        #queue update
        self.next_data_key=str_to_update
        self.update_queued=True

    async def process_update(self):
        if self.update_queued and self.next_data_key:
            print("updating")
            #determine the inactive buffer
            inactive_buffer='b' if self.active_buffer=='a' else 'a'
            
            #update inactive buffer
            inactive_buffer_JSON= self.precomputed_borders.get(self.next_data_key)
            print("full json array: ",inactive_buffer_JSON)
            inactive_buffer_ranges=inactive_buffer_JSON[self.start_note:self.start_note+12]
            if len(inactive_buffer_ranges)<12:
                inactive_buffer_ranges = inactive_buffer_ranges + [[0,1]] * (12-len(inactive_buffer_ranges))
            print("inactive_buffer: ",inactive_buffer)
            
            if inactive_buffer=='a':
                self.fft_ranges_buffer_a=inactive_buffer_ranges 
            else:
                self.fft_ranges_buffer_b=inactive_buffer_ranges
            #swap buffers 'atomically'
            
            self.active_buffer='b' if self.active_buffer=='a' else 'a'
            print('active buffer: ',self.active_buffer)
            
            if self.active_buffer=='a': 
                self.fft_ranges_to_operate_with=self.fft_ranges_buffer_a
            else:
                self.fft_ranges_to_operate_with=self.fft_ranges_buffer_b
            
            print("FFT_ranges_swap: ",self.fft_ranges_to_operate_with)
            #deactivate the update flags
            self.update_queued=False
            self.next_data_key=None
            
#             await uasyncio.sleep_ms(0)  # Yield to other tasks
            

    async def mini_wled(self, samples):
        #magnitudes = utils.spectrogram(samples, scratchpad=scratchpad)#, log=True)
        #magnitudes = utils.spectrogram(samples, scratchpad=scratchpad)
        magnitudes = utils.spectrogram(samples)
#         #print("mags",magnitudes)
        
        fftCalc=[]
        dominants=[]

        for f in self.fft_ranges_to_operate_with:
            # First block that could be if statemented into a display mode
#             print(self.fft_ranges_to_operate_with)
            slice_sum = np.sum(magnitudes[f[0]:f[1]])
            slice_index_diff = f[1]-f[0]
            try:
                normalized_sum = slice_sum/slice_index_diff
                if normalized_sum < self.noise_floor:
                    normalized_sum=0
                    #set the dominant mag to be the first magnitude in the array slice, if they are all lower than the noise threshold.
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
                #set the output to be the first value in the bin, always the first index, in this case
                #creates an output with padded zeros.
                normalized_sum=0
                dominant_mag = magnitudes[f[0]]
                dominant_tone = self.tones[f[0]]

            fftCalc.append(normalized_sum)
            dominants.append(dominant_tone)

        num_led_bins_calculated=self.length_of_leds
#         #print("len of fftCalc in wled",len(fftCalc))
        if len(fftCalc)>num_led_bins_calculated:
            fftCalc=fftCalc[:num_led_bins_calculated:]
            dominants=dominants[:num_led_bins_calculated:]

        return fftCalc,dominants

#     async def update_fft_ranges(self):
#         self.fft_ranges=self.precomputed_borders.get(str(self.notes_per_led))[self.start_note:12]
#         print("FFT_ranges: ", self.fft_ranges)

    async def start(self):
        leds = Leds()
        flag = asyncio.ThreadSafeFlag()

        # Define the callback for the IRQ that sets the flag
        def irq_handler(noop):
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
#             if t_mic_sample:
#                 #print("sample processing  : ", ticks_diff(t_awaiting, t_mic_sample), "ms")

            await flag.wait()

            t_mic_sample = ticks_ms()
            # this number should be non-zero, so the other coros can run. but if it's large
            # then can probably tune the buffer sizes to get more responsiveness
#             #print("time spent awaiting: ", ticks_diff(t_mic_sample, t_awaiting), "ms")
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
#             t1 = ticks_ms()
            # calculate fft_mag from samples
            fft_mags,dominants = await self.mini_wled(samples)
            t2 = ticks_ms()
            ##print("wled function:", ticks_diff(t2, t1), "ms") # 40ms
            

            
            

            # Assuming fft_mags is a numpy array
            fft_mags_array_raw = np.array(fft_mags)
            V_ref=8388607 #this value is microphone dependant, for the DFROBOT mic, which is 24-bit I2S audio, that value is apparently 8,388,607 
            db_scaling=np.array([20*math.log10(fft_mags_array_raw[index]/V_ref) if value != 0 else -80 for index, value in enumerate(fft_mags_array_raw) ]) #the magic number -80 in this code is -80db, the lowest value on my phone spectrogram app, but it's typically recommended to be -inf
            ##print(db_scaling)

            # FFTscaling only the fft_mags_array, when quiet, the maximum ambient noise dynamically becomes bright, which is distracting.
            # We need to make noise an ambient low level of intensity
            brightness_range=np.array([0,255]) 
            
            #auto gain control, in theory
            if max(db_scaling)>self.highest_db:
                self.highest_db=0.8*self.highest_db+0.2*max(db_scaling)
#                 print("loud: raising db top. db: ", self.highest_db)
            elif max(db_scaling)<=self.highest_db:
                self.highest_db=0.8*self.highest_db+0.2*self.max_db_set_point
#                 print("quiet: lowering db top to set point. db: ", self.highest_db)
            
            summed_magnitude_range=np.array([self.lowest_db, self.highest_db]) #values chosen by looking at my spectrogram. I think a value of zero is a shockwave.
            
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
                
                # scale brightness of magnitudes following their hue calculation
                fft_mags_array*=(self.brightness/255)

                # Use async to call show_hsv for valid LEDs
                for i in range(0,len(fft_mags_array)):
#                     self.channel1hues[i][self.bufferIndex+1%3]=hue 
                    await leds.show_hsv(0, i, int(intensity_hues[i]), 255, int(fft_mags_array[i]))#the FFT magnitude array brightness is already set by the range mapping functions above 
                    
                    #sorry about the -1s in the first terms, those are due to the length_of_leds being reduced by other array calculations/border conditions 
                    #the negative modulo terms in the second and fourth terms, however, are needed to get the ring buffer to work. 
                    await leds.show_hsv(1, i, int(self.ring_buffer_hues[(self.buff_index-2)%-3][i]), 255, int((self.ring_buffer_intensities[(self.buff_index-2)%-3][i])))
                    if self.show_menu_in_mic == False:
                        await leds.show_hsv(2, i, int(self.ring_buffer_hues[(self.buff_index-1)%-3][i]), 255, int((self.ring_buffer_intensities[(self.buff_index-1)%-3][i])))
                            

                self.ring_buffer_hues[(self.buff_index-1)%-3]=intensity_hues
                self.ring_buffer_intensities[(self.buff_index-1)%-3]=fft_mags_array
                self.buff_index-=1
                self.buff_index%=-3
                await leds.write(0) 
                await leds.write(1)
                await leds.write(2)
                    
            t3 = ticks_ms()
            if self.mode=="Synesthesia":
                # scale brightness of magnitudes following their hue calculation
                #this line is repeated above inside the intesities mode, but there it has to be after some hue calculatations
                fft_mags_array*=(self.brightness/255)
                
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
                    await leds.show_hsv(0, i, int(current_hues[i]), 255, int(fft_mags_array[i]))
                    await leds.show_hsv(1, i, int(self.ring_buffer_hues[(self.buff_index-2)%-3][i]), 255, int(self.ring_buffer_intensities[(self.buff_index-2)%-3][i]))
                    if self.show_menu_in_mic == False:
                        await leds.show_hsv(2, i, int(self.ring_buffer_hues[(self.buff_index-1)%-3][i]), 255, int(self.ring_buffer_intensities[(self.buff_index-1)%-3][i]))
                            

                self.ring_buffer_hues[(self.buff_index-1)%-3]=current_hues
                self.ring_buffer_intensities[(self.buff_index-1)%-3]=fft_mags_array
                self.buff_index-=1
                self.buff_index%=-3
                
                await leds.write(0)
                await leds.write(1)
                await leds.write(2)
            ##print("synesthesia :    ", ticks_diff(t3, t2), "ms") # 2ms !
            
                
            if self.show_menu_in_mic == True:
                if self.menu_thing_updating=="brightness" and self.menu_update_required==True:                       
                    #update onboard LED/mini-menu
#                         leds.show_hsv(3,0,0,0,10)
                    leds.status_pix[0]=(10,10,10)#the status LED is grb
                    await leds.write(3)
                    
                    #print("brightness in mic: ",self.brightness)
                    print(self.brightness)
                    parts_per_bin=42
                    for i in range(0,6):
                        #if the brightness is outright greater than the number of parts cumulative to that LED, just give it 'full' brightness e.g.: 21/21
                        if self.brightness>=((i+1)*parts_per_bin) or i==0:
#                                 print("full brightness")
                            await leds.show_hsv(2,i,0,0,int(self.brightness/2))
                            await leds.show_hsv(2,11-i,0,0,int(self.brightness/2))
                            
                        #if the brightness value is located inside the range of one LED, fill it with a fractional brightness adjusted by the overall brightness e.g.: 5/21
                        elif (((i+1)*parts_per_bin)>self.brightness>i*parts_per_bin):
#                                 print("fractional brightness")
                            await leds.show_hsv(2,i,0,0,int(((self.brightness-(i*parts_per_bin))/parts_per_bin)*(self.brightness/2)))
                            await leds.show_hsv(2,11-i,0,0,int(((self.brightness-(i*parts_per_bin))/parts_per_bin)*(self.brightness/2)))

                        #blank out the non needed menu pixels
                        else:
#                                 print("blanking out")
                            await leds.show_hsv(2,i,0,0,0)
                            await leds.show_hsv(2,11-i,0,0,0) 
                    self.menu_update_required=False
                    
                if self.menu_thing_updating=="notes_per_px" and self.menu_update_required==True:
                    #update onboard LED/mini-menu
                    leds.status_pix[0]=(0,20,0)#the status LED is grb
                    await leds.write(3)

                    #update fft_ranges if needed
                    self.schedule_update(str(self.notes_per_led))
                    if self.update_queued:
                        await self.process_update()
                                            
                    for i in range(0,12):
                        await leds.show_hsv(2,i,0,0,0)
                    for i in range(0,12,int(12/self.notes_per_led)): #the division of 12 is required to scale the right way around, six notes per led should show an octave every two leds, not every six
                        await leds.show_hsv(2,i,255,255,self.brightness)
                    self.menu_update_required=False
                    
                if self.menu_thing_updating=="start_note" and self.menu_update_required==True:
                    #update onboard LED/mini-menu
                    leds.status_pix[0]=(20,20,0)#the status LED is grb
                    await leds.write(3)
                    
                    #update fft_ranges if needed
                    self.schedule_update(str(self.notes_per_led))
                    if self.update_queued:
                        await self.process_update()
                    
                    for index,pix in enumerate(self.menu_pix):
                        await leds.show_hsv(2,index,self.menu_pix[index][0],255,self.brightness)
                    self.menu_update_required=False
                    
                if self.menu_thing_updating=="highest_db" and self.menu_update_required==True:
                    #update onboard LED/mini-menu
                    leds.status_pix[0]=(20,0,0)#the status LED is grb
                    await leds.write(3)
                    
                    for index,pix in enumerate(self.menu_pix):
                        await leds.show_hsv(2,index,self.menu_pix[index][0],255,self.brightness)
                    self.menu_update_required=False
                    
                if self.menu_thing_updating=="hue_select" and self.menu_update_required==True:
                    #update onboard LED/mini-menu
                    leds.status_pix[0]=(20,0,20)#the status LED is grb
                    await leds.write(3)
                    
                if self.menu_thing_updating=="ect" and self.menu_update_required==True:
                    #update onboard LED/mini-menu
                    leds.status_pix[0]=(0,0,20)#the status LED is grb
                    await leds.write(3)
                

        
