from ulab import utils
import json
import math
import asyncio
from leds import Leds
from ulab import numpy as np
from machine import Pin, I2S
from time import ticks_ms, ticks_diff
from border_calculator import PrecomputedValues
from menu_calculator import PrecomputedMenu

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
        
        self.show_menu_in_mic=False
        self.menu_thing_updating="brightness"
        self.menu_update_required=False
        self.menu_init=True #hopefully just used once a start up.
        
        
        self.max_db_set_point=-40
        self.highest_db_on_record=self.max_db_set_point
        self.lowest_db=-80
        self.db_selection="max_db_set"
        
        # Event required to change this mode
#         self.change_display_mode(0)
        self.mode=self.modes[0]
        
        # Event required to change this value
        self.noise_floor=1000
        
        # Event required to change this value
        self.brightness=20 #[0-255]
        
        # Calculate the defined frequencies of the musical notes
#         self.notes=np.arange(1.,85.)
#         self.note_frequencies=TUNING_A4_HZ*(2**((self.notes-49)/12))
        ##print("note frequencies: ", note_frequencies)

        # Event required to change note_per_led number
        self.number_of_octaves=7
        self.notes_per_led_index=4
        self.notes_per_led_options=[1,2,3,4,6,12]
        self.notes_per_led=self.notes_per_led_options[self.notes_per_led_index]
        self.start_range_index=0 #this is a variable that determines where in a precomputed list of ranges of indexes to start displaying the fft results 
        self.full_window_len=12
        self.window_slice_len=12 #this is for clamping the start note when the octave resolution/notes_per_LED is switched 
        self.max_window_overreach=5 #this limit is determined by how many octaves can be shown at once, which is determined by the fft sampling parameters. Currently 7 octaves. 12Leds-7octaves=5 to pad in worst case
        
        self.notes_per_pix_hue=0
        self.octave_shift_hue=50000
        
        #load the precomupted octave menu and select the dictionary entry that corresponds to the current notes_per_led option
        #create two buffers to avoid async clashes
        self.precomputed_menus=PrecomputedMenu("precomputed_octave_display.json")
        if self.precomputed_menus.load():
            JSON_menu=self.precomputed_menus.get(str(self.notes_per_led))
            self.menu_buffer_a=JSON_menu[self.start_range_index:12]
            self.menu_buffer_b=JSON_menu[self.start_range_index:12]        
        
        #load precomputed values and select the dictionary entry that corresponds to the current notes_per_led option
        #create two buffers to avoid async clashes
        self.precomputed_borders=PrecomputedValues("test_speedup_redo_values.json")
        if self.precomputed_borders.load():
            JSON_boot=self.precomputed_borders.get(str(self.notes_per_led))
            self.fft_ranges_buffer_a=JSON_boot[self.start_range_index:12]
            self.fft_ranges_buffer_b=JSON_boot[self.start_range_index:12]
#             print("FFT_ranges: ", self.fft_ranges_buffer_a)

        #create buffer pointers
        self.active_buffer='a'
        self.menu_to_operate_with=self.menu_buffer_a
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
            #3print("updating")
            #determine the inactive buffer
            inactive_buffer='b' if self.active_buffer=='a' else 'a'
            
            #update inactive buffers
            inactive_menu_buffer=self.precomputed_menus.get(self.next_data_key)
            inactive_fft_buffer_json=self.precomputed_borders.get(self.next_data_key)
            self.full_window_len=len(inactive_fft_buffer_json)
#             print("len full json array: ",len(inactive_fft_buffer_json))
            
            inactive_menu_range=inactive_menu_buffer[self.start_range_index:self.start_range_index+12]
            inactive_fft_buffer_ranges=inactive_fft_buffer_json[self.start_range_index:self.start_range_index+12]
            
            self.window_slice_len=len(inactive_fft_buffer_ranges)
#             print("window_slice_Len: ",self.window_slice_len)
            window_overextension=12-self.window_slice_len
            
            if len(inactive_fft_buffer_ranges)<12: #and window_overextension<self.max_window_overreach:
#                 inactive_fft_buffer_ranges = inactive_fft_buffer_ranges + [[-1,-1]] * window_overextension
                inactive_menu_range += [-1] * (12-len(inactive_fft_buffer_ranges))
                inactive_fft_buffer_ranges += [[-1]] * (12-len(inactive_fft_buffer_ranges))
                
                
#             print("inactive_buffer: ",inactive_fft_buffer_ranges)
            
            if inactive_buffer=='a':
                self.menu_buffer_a=inactive_menu_range
                self.fft_ranges_buffer_a=inactive_fft_buffer_ranges 
            else:
                self.menu_buffer_b=inactive_menu_range
                self.fft_ranges_buffer_b=inactive_fft_buffer_ranges
            #swap buffers 'atomically'
            
            self.active_buffer='b' if self.active_buffer=='a' else 'a'
#             print('active buffer: ',self.active_buffer)
            
            if self.active_buffer=='a': 
                self.menu_to_operate_with=self.menu_buffer_a
                self.fft_ranges_to_operate_with=self.fft_ranges_buffer_a
            else:
                self.menu_to_operate_with=self.menu_buffer_b
                self.fft_ranges_to_operate_with=self.fft_ranges_buffer_b
            
#             print("FFT_ranges_swap: ",self.fft_ranges_to_operate_with)
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
            if f[0]>=0:
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
                        dominant_mag=magnitudes[where_dominant_mag]
                        dominant_tone=self.tones[where_dominant_mag]

                # Crops up if the number of notes in a bin is too few.
                # As in low note_per_bin cases.
                except ZeroDivisionError:
                    #set the output to be the first value in the bin, always the first index, in this case
                    #creates an output with padded zeros.
                    normalized_sum=0
                    dominant_mag = magnitudes[f[0]]
                    dominant_tone = self.tones[f[0]]
            else:
                normalized_sum=0 #can't set these to -1 because they go through a log filter
                dominant_mag=3000
                dominant_tone=0
                
#             fftCalc.append(normalized_sum)
            fftCalc.append(dominant_mag)
            dominants.append(dominant_tone)

        num_led_bins_calculated=self.length_of_leds
#         #print("len of fftCalc in wled",len(fftCalc))
        if len(fftCalc)>num_led_bins_calculated:
            fftCalc=fftCalc[:num_led_bins_calculated:]
            dominants=dominants[:num_led_bins_calculated:]

        return fftCalc,dominants

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
            db_scaling=np.array([20*math.log10(fft_mags_array_raw[index]/V_ref) if value != 0 else self.lowest_db for index, value in enumerate(fft_mags_array_raw) ]) #the magic number -80 in this code is -80db, the lowest value on my phone spectrogram app, but it's typically recommended to be -inf
            ##print(db_scaling)

            # FFTscaling only the fft_mags_array, when quiet, the maximum ambient noise dynamically becomes bright, which is distracting.
            # We need to make noise an ambient low level of intensity
            brightness_range=np.array([0,255]) 
            
            #auto gain control, in theory
            loudest_reading=max(db_scaling)
            if loudest_reading>self.highest_db_on_record:
#                 self.highest_db_on_record=0.8*self.highest_db_on_record+0.2*max(db_scaling)
                self.highest_db_on_record=loudest_reading
                print("highest db recorded: ",self.highest_db_on_record)
#                 print("loud: raising db top. db: ", self.highest_db_on_record)
                time_of_ceiling_raise=ticks_ms()
                spam_reduction_time=ticks_ms()
            elif (loudest_reading<self.highest_db_on_record) and (self.highest_db_on_record>self.max_db_set_point+1): #+1db is cheating the decay on the highest db value.
                time_since_raise=ticks_diff(ticks_ms(),time_of_ceiling_raise)
                if time_since_raise<3000:
                    time_since_last_update=ticks_diff(ticks_ms(),spam_reduction_time)
                    if time_since_last_update>500:#reduce the number of spam checks
                        spam_reduction_time=ticks_ms()
                        print("checking if enough time has passed to lower the AGC")
                elif ticks_diff(ticks_ms(),time_of_ceiling_raise)>3000: #hardcoded delay on the AGC
                    self.highest_db_on_record=0.9*self.highest_db_on_record+0.1*self.max_db_set_point
                    time_since_last_update=ticks_diff(ticks_ms(),spam_reduction_time)
                    if time_since_last_update>500:#reduce the number of spam checks
                        spam_reduction_time=ticks_ms()
                        print("quiet: lowering db top to set point. db: ", self.highest_db_on_record)
            
#                 
            
            summed_magnitude_range=np.array([self.lowest_db, self.highest_db_on_record]) #values chosen by looking at my spectrogram. I think a value of zero is a shockwave.
            
            #scale to 0-255 range, can/should scale up for more hue resolution
            fft_mags_array = np.interp(db_scaling, summed_magnitude_range, brightness_range)
#             print("FFT_mags_array: ", fft_mags_array)
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
            
            
            if self.menu_init==True: #annoying to have a single use line but this is a quick fix.                                
                #init the status pix or it will keep the last menu state
                leds.status_pix[0]=(0,20,0)#the status LED is grb
                await leds.write(3)
                self.menu_init=False
            
            if self.show_menu_in_mic == True:
                if self.menu_thing_updating=="brightness" and self.menu_update_required==True:                       
                    #update onboard LED/mini-menu
#                         leds.show_hsv(3,0,0,0,10)
                    leds.status_pix[0]=(0,20,0)#the status LED is grb
                    await leds.write(3)
                    
                    #print("brightness in mic: ",self.brightness)
                    
                    #print make the first pixel, left to right, show with brightness of the display, in one channel only (e.g. red)
                    await leds.show_hsv(2,11,0,255,int(self.brightness))
                    
                    parts_per_bin=21 #255/12
                    #skip the first pixel, it's already been set.
                    for i in range(1,12):
                        #if the pixel is in range of the brightness value, light it up
                        if  i*parts_per_bin <= self.brightness < (i+1)*parts_per_bin:
                            await leds.show_hsv(2,11-i,0,255,int(self.brightness))    
                        # otherwise, blank out the non needed menu pixels
                        else:
                            await leds.show_hsv(2,11-i,0,0,0)
                            
                    #reset to allow the next update
                    self.menu_update_required=False
                    
                if self.menu_thing_updating=="notes_per_px" and self.menu_update_required==True:
                    #update onboard LED/mini-menu
                    leds.status_pix[0]=(10,20,0)#the status LED is grb
                    await leds.write(3)
            
                    #update fft_ranges if needed
                    self.schedule_update(str(self.notes_per_led))
                    if self.update_queued:
                        await self.process_update()
                                            
                    for i in range(0,12): #blank out LEDs
                        await leds.show_hsv(2,i,0,0,0)
                        #3print(self.menu_to_operate_with)
                        if self.menu_to_operate_with[i]==-1:
                            await leds.show_hsv(2,i,0,0,0)
#                             await leds.show_hsv(2,i,self.notes_per_pix_hue,255,int(self.brightness*0.1))
                        elif self.menu_to_operate_with[i]>=0:
                            await leds.show_hsv(2,i,self.menu_to_operate_with[i],255,self.brightness)
                            
#                     for i in range(0,self.window_slice_len,int(12/self.notes_per_led)): #the division of 12 is required to scale the right way around, six notes per led should show an octave every two leds, not every six
#                         await leds.show_hsv(2,i,900*i,255,self.brightness) #make each octave a different colour
                    self.menu_update_required=False
                    
                if self.menu_thing_updating=="start_range_index" and self.menu_update_required==True:
                    #update onboard LED/mini-menu
                    leds.status_pix[0]=(0,20,10)#the status LED is grb
                    await leds.write(3)
                    
#                     if self.start_range_index>=self.window_slice_len+self.max_window_overreach:
#                         self.start_range_index=self.window_slice_len+self.max_window_overreach
                    
                    #update fft_ranges if needed
                    self.schedule_update(str(self.notes_per_led))
                    if self.update_queued:
                        await self.process_update()
                    
                    #3print("start_range_index_in_mic: ",self.start_range_index)
                    for i in range(0,12): #blank out LEDs
                        await leds.show_hsv(2,i,0,0,0)
                        if self.menu_to_operate_with[i]==-1:
                            await leds.show_hsv(2,i,self.octave_shift_hue,255,int(self.brightness*0.1))
                        elif self.menu_to_operate_with[i]>=0:
                            await leds.show_hsv(2,i,self.menu_to_operate_with[i],255,self.brightness)
                    
                    
#                     for i in range(0,self.window_slice_len,int(12/self.notes_per_led)): #the division of 12 is required to scale the right way around, six notes per led should show an octave every two leds, not every six
#                         
                        ###need to have an array for each resolution, which is sliced for each update of the start_range_index, and displayed. That instead of calculating from a for loop
                        ###the result will lool like:
                        #def compute_octave_display:
                            #octave_display=np.zeros(self.full_window_len)
                            #for i in range(0,self.full_window_len,int(12/self.notes_per_led)) #the division of 12 is required to scale the right way around, six notes per led should show an octave every two leds, not every six
                                ##calculate hue
                                #octave_display[i]=800*i
                        
                        
                        #for i in range(0,12):
                            #await leds.show_hsv(2,i,octave_display_slice[i],255,self.brightness) #make each octave a different colour
                        
#                         await leds.show_hsv(2,i,800*i,255,self.brightness) #make each octave a different colour
                        #override LED to show the menu mode (which actually gets overwritten pretty quickly by the fft)
#                         await leds.show_hsv(1,self.selector_index,24000,255,self.brightness) #make each octave a different colour
#                         await leds.write(1)
                    self.menu_update_required=False
                    
                    
                if self.menu_thing_updating=="highest_db" and self.menu_update_required==True:
                    #update onboard LED/mini-menu
                    leds.status_pix[0]=(20,0,0)#the status LED is grb
                    await leds.write(3)
                    
                    #print("loudest reading: ", loudest_reading)
                    db_per_bin=-10 #-120 to 0 decibels makes a nice 10 decible scale bar
                    #for loop looks odd, because again it's decibels, and because I flipped it to be left to right
                    for i in range(12,0,-1):
                        #conditions will look odd here because the values to work with are in decibels, which are -ve
                        if i*db_per_bin <= loudest_reading:
                            #draw loudest measured decibel signal, from -120 to 0
                            await leds.show_hsv(2,i-1,self.octave_shift_hue,255,int(self.brightness))#annoying indicies, minus one is to line up with pixels  
                        else:    
                            #blank out leds
                            await leds.show_hsv(2,i-1,0,0,0)  
                    
                        #draw level top first, so that it does not overide the highest db pixel indicator, in the case the highest value is greater than the high db but less than the next pixel
                        if (self.highest_db_on_record>self.max_db_set_point):
#                             if (i*db_per_bin <= loudest_reading < (i-1)*db_per_bin):
#                                 await leds.show_hsv(2,i-1,5000,255,int(self.brightness))
                            if (i*db_per_bin <= self.highest_db_on_record < (i-1)*db_per_bin):
                                await leds.show_hsv(2,i-1,5000,255,int(self.brightness))
                        
                        #draw lowest db setting
                        if i*db_per_bin==self.lowest_db:
                            if self.db_selection=='min_db_set':
                                await leds.show_hsv(2,i-1,20000,255,int(self.brightness))
                            else:
                                await leds.show_hsv(2,i-1,0,255,int(self.brightness))
                        #draw highest db setting
                        if i*db_per_bin==self.max_db_set_point:
                            if self.db_selection=='max_db_set':
                                await leds.show_hsv(2,i-1,20000,255,int(self.brightness))
                            else:
                                await leds.show_hsv(2,i-1,0,255,int(self.brightness))
                    #draw update the menu?
#                     await leds.write(2)
                        
                    
                    #This determines if the menue keep updating or is a one and done?
#                     self.menu_update_required=False
                    
                if self.menu_thing_updating=="hue_select" and self.menu_update_required==True:
                    #update onboard LED/mini-menu
                    leds.status_pix[0]=(0,0,20)#the status LED is grb
                    await leds.write(3)
                    
                    for i in range(0,12):
                        await leds.show_hsv(2,i,0,0,0)
                        
                    
#                 if self.menu_thing_updating=="ect" and self.menu_update_required==True:
#                     #update onboard LED/mini-menu
#                     leds.status_pix[0]=(0,0,20)#the status LED is grb
#                     await leds.write(3)
#                 

        
