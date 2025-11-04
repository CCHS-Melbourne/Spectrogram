from ulab import utils
import json
import math
import asyncio
from leds import Leds
from ulab import numpy as np
from machine import Pin, I2S
from time import ticks_ms, ticks_diff
from utils.border_calculator import PrecomputedBorders
from utils.nearest_tone_index_calculator import PrecomputedNearestTones
from utils.nearest_tone_index_represents import PrecomputedToneRepresentations
from utils.menu_calculator import PrecomputedMenu

# import gc
# gc.collect()

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
#claude sonnet says this is a big issue #sample_bytearray = samples.tobytes()  # bytearray points to the sample samples array
sample_bytearray=samples.tobytes()
scratchpad = np.zeros(2 * SAMPLE_COUNT) # re-usable RAM for the calculation of the FFT
                                        # avoids memory fragmentation and thus OOM errors

magnitudes=np.zeros(SAMPLE_COUNT, dtype=np.float) #this is the result from the FFT

V_ref=8388607 #this value is microphone dependant, for the DFROBOT mic, which is 24-bit I2S audio, that value is apparently 8,388,607 

ID = 0
SD = Pin(11)
SCK = Pin(10)
WS = Pin(9)


def create_color_lut():
    lut = [] 
    for i in range(256):
        if i <= 170:
            progress = i / 170.0
            r = int(255 * progress)
            g = 0
            b = int(255 * (1 - progress))
        else:
            progress = (i - 171) / 84.0
            r = 255
            g = int(255 * progress)
            b = 0
        lut.append((r, g, b))
    return lut

class Mic():
    def __init__(self,watchdog):
        self.watchdog=watchdog
        
        self.microphone = I2S(ID, sck=SCK, ws=WS, sd=SD, mode=I2S.RX,
                                bits=SAMPLE_SIZE, format=I2S.MONO, rate=SAMPLE_RATE,
                                ibuf=I2S_SAMPLE_BYTES)

        self.mode="intensity"
        
        self.status_led_off=False
        self.show_menu_in_mic=False
        self.menu_thing_updating="brightness"
        self.menu_update_required=False
        self.menu_init=True #hopefully just used once a start up.
        
        #converts fft to db
        self.db_scaling=np.zeros(12,dtype=np.float)
        self.max_db_set_point=-40
        self.highest_db_on_record=self.max_db_set_point
        self.low_db_set_point=-80
        self.db_selection="max_db_set"
        self.last_loudest_reading=-80
        self.auto_low_control=False
        
        #determines the values that are actually accounted for in display colour scaling
        self.scale_and_clip_db_range=np.array([self.low_db_set_point, self.highest_db_on_record]) #for colouring: values chosen by looking at my spectrogram. I think a value of zero is a shockwave.
        # Preallocated arrays
        #stores result from fft
        self.binned_fft_calc=np.zeros(12,dtype=np.float)
        self.dominant_tones=[0]*12
        self.dominant_notes_rep=np.zeros(12,dtype=np.float)
   
        
        self.fft_mags_array=np.zeros(12,dtype=np.float)
        self.fft_mags_int_list=[0]*12
        
        
        self.noise_floor=1000
        
        self.resolution_sub_mode='notes_per_pix'
        
        #intializing varables here is fine, but their handling and setting should be in the menu.
        self.brightness_sub_mode='flat'
        self.flat_hue_b=0
        self.scaling_hue_b=10000
        
        
        self.brightnesses=[2,3,4,5,7,10,20,35,50,90,160,255]
        self.brightness_index=4
        self.brightness=self.brightnesses[self.brightness_index] #[0-255]
        
        # Calculate the defined frequencies of the musical notes
#         self.notes=np.arange(1.,85.)
#         self.note_frequencies=TUNING_A4_HZ*(2**((self.notes-49)/12))
        ##print("note frequencies: ", note_frequencies)

        # Event required to change note_per_led number
        self.number_of_octaves=7
        self.notes_per_led_index=4
        self.notes_per_led_options=[1,2,3,4,6,12]
        self.notes_per_led=self.notes_per_led_options[self.notes_per_led_index]
        self.absolute_note_index=0
        
        self.start_range_index=0 #this is a variable that determines where in a precomputed list of ranges of indexes to start displaying the fft results 
        self.full_window_len=12
        self.window_slice_len=12 #this is for clamping the start note when the octave resolution/notes_per_LED is switched 
        self.max_window_overreach=5 #this limit is determined by how many octaves can be shown at once, which is determined by the fft sampling parameters. Currently 7 octaves. 12Leds-7octaves=5 to pad in worst case
        
        self.notes_per_pix_hue=0
        self.octave_shift_hue=42000 #blue, determined by looking at hue learner.
        
        #load the precomupted octave menu and select the dictionary entry that corresponds to the current notes_per_led option
        #create two buffers to avoid async clashes
        self.precomputed_menus=PrecomputedMenu("utils/precomputed_octave_display.json")
        if self.precomputed_menus.load():
            JSON_menu=self.precomputed_menus.get(str(self.notes_per_led))
            self.menu_buffer_a=JSON_menu[self.start_range_index:12]
            self.menu_buffer_b=JSON_menu[self.start_range_index:12]        
        
        #load precomputed values and select the dictionary entry that corresponds to the current notes_per_led option
        #create two buffers to avoid async clashes
        self.precomputed_borders=PrecomputedBorders("utils/trying for better divisions between A and Asharp.json")
        if self.precomputed_borders.load():
            JSON_boot=self.precomputed_borders.get(str(self.notes_per_led))
            self.fft_ranges_buffer_a=JSON_boot[self.start_range_index:12]
            self.fft_ranges_buffer_b=JSON_boot[self.start_range_index:12]
#             print("FFT_ranges: ", self.fft_ranges_buffer_a)

        #load precomputed values and select the dictionary entry that corresponds to the current notes_per_led option
        #create two buffers to avoid async clashes
        self.precomputed_representation_map=PrecomputedToneRepresentations("utils/binned_indexes_represent_which_musical_tones.json")
        if self.precomputed_representation_map.load():
            JSON_boot=self.precomputed_representation_map.get(str(self.notes_per_led))
            self.representations_map_buffer_a=JSON_boot[self.start_range_index:12]
            self.representations_map_buffer_b=JSON_boot[self.start_range_index:12]
            
        #load precomputed values and select the dictionary entry that corresponds to the current notes_per_led option
        #create two buffers to avoid async clashes
        self.precomputed_closest_tone_indexes=PrecomputedNearestTones("utils/binned_indexes_of_tones_nearest_to_musical_notes.json")
        if self.precomputed_closest_tone_indexes.load():
            JSON_boot=self.precomputed_closest_tone_indexes.get(str(self.notes_per_led))
            self.closest_tones_buffer_a=JSON_boot[self.start_range_index:12]
            self.closest_tones_buffer_b=JSON_boot[self.start_range_index:12]

        #create buffer pointers
        self.active_buffer='a'
        self.menu_to_operate_with=self.menu_buffer_a
        self.fft_ranges_to_operate_with=self.fft_ranges_buffer_a
        self.representations_map_to_operate_with=self.representations_map_buffer_a
        self.closest_tone_indexes_to_operate_with=self.closest_tones_buffer_a
        
        #create update flags
        self.update_queued=False
        self.next_data_key=None        
        
        self.length_of_leds=13 #actually needs to be number of leds+1, due to how the note border finding/zipping function organizes borders
        self.ring_buffer_hues=np.zeros((3,self.length_of_leds-1))
        self.ring_buffer_intensities=np.zeros((3,self.length_of_leds-1))
        self.buff_index=0
        self.ring_buffer_hues_rgb=[[(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)],
                                   [(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)],
                                   [(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)]]
        
        self.scaled_hues=[(0,0,0)]*12
        
        self.ring_buffer_intensities_rgb=[[0,0,0,0,0,0,0,0,0,0,0,0],
                                          [0,0,0,0,0,0,0,0,0,0,0,0],
                                          [0,0,0,0,0,0,0,0,0,0,0,0]]
        
        # Figure out what tones correspond to what magnitudes out of the fft, with respect to the mic sampling parameters
        self.tones=FREQUENCY_RESOLUTION*np.arange(SAMPLE_COUNT/2)
        
        self.intensity_hues=[(0,0,0)]*12
        #replace masks and HSV calcs with LUT
        self.intensity_lut = create_color_lut()
        self.colour_index_range=np.array([0,255])
#         print("intensity_lut",self.intensity_lut)
        
        #set hues for synesthesia mode based on notes picked in RGB in LED_note_hue_picker, translate to HSV values
        self.note_hues=[(255,0,0),(255,30,30),(255,60,0),(255,255,0),(255,255,30),(0,255,0),(80,220,10),(0,155,255),(0,0,255),(50,0,255),(255,0,255),(255,255,255)]
        
    
    async def relocate_start_range_index(self):
        #7 octaves, 12leds/xNotes, 12 Leds 
        self.start_range_index=math.floor(self.absolute_note_index/self.notes_per_led)
        #print("relocated start range index",self.start_range_index)
        
        #self.absolute_note_index+=self.notes_per_led
        #self.absolute_note_index-=self.notes_per_led
        
        #The absolute note index Must always be a multiple of the notes_per_led, i.e. it must be rounded when the resolution is changed
        #self.absolute_note_index=
        
    async def status_led_off(self):
        self.leds.status_pix[0]=(0,0,0)#the status LED is grb
        await self.leds.write(3)
        
    
    def schedule_update(self,str_to_update):
        #queue update
        self.next_data_key=str_to_update
        self.update_queued=True

    async def process_update(self):
        if self.update_queued and self.next_data_key:
            #3print("updating")
            #determine the inactive buffer
            inactive_buffer='b' if self.active_buffer=='a' else 'a'
            
            #update inactive buffers, reading the precomputed dictionary using the requested notes_per_LED 
            inactive_menu_buffer=self.precomputed_menus.get(self.next_data_key)
            inactive_fft_buffer_json=self.precomputed_borders.get(self.next_data_key)
            inactive_representation_buffer=self.precomputed_representation_map.get(self.next_data_key)
            inactive_closest_tone_buffer=self.precomputed_closest_tone_indexes.get(self.next_data_key)
            
            self.full_window_len=len(inactive_fft_buffer_json)
#             print("len full json array: ",len(inactive_fft_buffer_json))
            
            inactive_menu_range=inactive_menu_buffer[self.start_range_index:self.start_range_index+12]
            inactive_fft_buffer_ranges=inactive_fft_buffer_json[self.start_range_index:self.start_range_index+12]
            inactive_representations=inactive_representation_buffer[self.start_range_index:self.start_range_index+12]
            insactive_closest_tones=inactive_closest_tone_buffer[self.start_range_index:self.start_range_index+12]
            
            self.window_slice_len=len(inactive_fft_buffer_ranges)
#             print("window_slice_Len: ",self.window_slice_len)
            window_overextension=12-self.window_slice_len
            
            if len(inactive_fft_buffer_ranges)<12: #and window_overextension<self.max_window_overreach:
#                 inactive_fft_buffer_ranges = inactive_fft_buffer_ranges + [[-1,-1]] * window_overextension
                inactive_menu_range += [-1] * (12-len(inactive_fft_buffer_ranges))
                inactive_fft_buffer_ranges += [[-1]] * (12-len(inactive_fft_buffer_ranges))#this must be an array slice, or else the summation stuff later crashes!
                inactive_representations += [[-1]] * (12-len(inactive_fft_buffer_ranges))
                insactive_closest_tones += [[-1]] * (12-len(inactive_fft_buffer_ranges))
                
#             print("inactive_buffer: ",inactive_fft_buffer_ranges)
            
            if inactive_buffer=='a':
                self.menu_buffer_a=inactive_menu_range
                self.fft_ranges_buffer_a=inactive_fft_buffer_ranges
                self.representations_map_buffer_a=inactive_representations
                self.closest_tones_buffer_a=insactive_closest_tones
            else:
                self.menu_buffer_b=inactive_menu_range
                self.fft_ranges_buffer_b=inactive_fft_buffer_ranges
                self.representations_map_buffer_b=inactive_representations
                self.closest_tones_buffer_b=insactive_closest_tones
            #swap buffers 'atomically'
            
            self.active_buffer='b' if self.active_buffer=='a' else 'a'
#             print('active buffer: ',self.active_buffer)
            
            if self.active_buffer=='a': 
                self.menu_to_operate_with=self.menu_buffer_a
                self.fft_ranges_to_operate_with=self.fft_ranges_buffer_a
                self.representations_map_to_operate_with=self.representations_map_buffer_a
                self.closest_tone_indexes_to_operate_with=self.closest_tones_buffer_a
            else:
                self.menu_to_operate_with=self.menu_buffer_b
                self.fft_ranges_to_operate_with=self.fft_ranges_buffer_b
                self.representations_map_to_operate_with=self.representations_map_buffer_b
                self.closest_tone_indexes_to_operate_with=self.closest_tones_buffer_b
            
#             print("FFT_ranges_swap: ",self.fft_ranges_to_operate_with)
            #deactivate the update flags
            self.update_queued=False
            self.next_data_key=None
            

#             await uasyncio.sleep_ms(0)  # Yield to other tasks
            

    async def fft_and_bin(self, samples):
        #magnitudes = utils.spectrogram(samples, scratchpad=scratchpad)#, log=True) #scratchpad worsens overall performance.
        
        #This is the fft, speed determined by the size of the samples, which must be a length of a power of two.
        t_spectro_isolate_0=ticks_ms()
        #magnitudes =
        magnitudes=utils.spectrogram(samples)
        t_spectro_isolate_1=ticks_ms()
        
        #print("FFT_testing_isolated: ", ticks_diff(t_spectro_isolate_1, t_spectro_isolate_0))
#         with open('fft_diagnosis.txt', 'a') as f:
#             for item in magnitudes:
#                 f.write(str(item) + ', ')
#             f.write('\n')       
        
        t_fft_bins0=ticks_ms()
#         print(f"after fft: {gc.mem_free()}")  
        
        slice_sums=[]
#         print(self.fft_ranges_to_operate_with)
        #ranges_to_operate_with is a buffer containing precomputed boundaries for the notes_per_pixel bins of interest, the buffer is updated with menuing.
        for index, f in enumerate(self.fft_ranges_to_operate_with):
#             print(self.fft_ranges_to_operate_with)
            if f[0]>=0: #check if the bin has not been errored out with -1, e.g.: if the menu or bins are shorter than the display.
                 
                #total energy of sound is more important than an average. Not sure what this will do to my log conversion.
                slice_sum = np.sum(magnitudes[f[0]:f[1]])
                slice_sums.append(slice_sum)
                slice_index_diff = f[1]-f[0]
                try:
                    normalized_sum = slice_sum/slice_index_diff
                    ###This sort of thing is needed for microtone representation.
                    ## Find out where the max magnitude in the slice is, then add the starting index of the slice,
                    ## or you'll get veeeery odd frequency curves.
                    where_dominant_mag=np.argmax(magnitudes[f[0]:f[1]])+f[0] 
                    dominant_mag=magnitudes[where_dominant_mag]
                    dominant_tone=self.tones[where_dominant_mag]
                    
                    
#                     if normalized_sum<self.noise_floor:
#                         normalized_sum=0
#                         #set the dominant mag to be the first magnitude in the array slice, if they are all lower than the noise threshold.
#                         dominant_mag = magnitudes[f[0]] # Not ideal but doesn't matter, as the tone will be set to zero brightness
#                         dominant_tone = self.tones[f[0]]
#                         dominant_note_rep = self.representations_map_to_operate_with[index][0]
                        
                    #if there is a low signal in the bin: set everything in it low.
#                     if slice_sum < self.noise_floor:
#                         #print("below noise floor")
#                         display_value=0
#                         #set the dominant mag to be the first closes_tone to a 'real note's magnitude in the array slice, if they are all lower than the noise threshold.
#                         dominant_mag = magnitudes[self.closest_tone_indexes_to_operate_with[index][0]] # Show the regularity of octave colours, which is cool. 
#                         #this should be the first closest /tone/ not the first halfway frequency
#                         dominant_tone = self.tones[self.closest_tone_indexes_to_operate_with[index][0]]
#                         dominant_note_rep = self.representations_map_to_operate_with[index][0]
#                     # 
#                     else:
                        #check the tones located in each bin for their magnitude, record the index of the most intense 'real note' #TODO: non microtonal.
                        #closest_tone_indexes_to_operate_with is a buffer containing notes_per_pixel binned indexes of fft tones nearest to 'real notes', the buffer is updated with menuing.
                        #the bin to check lines up with the enum fft range (precomputed) above
#                         max_index=0
#                         dominant_mag=0
#                         closest_tone_list=self.closest_tone_indexes_to_operate_with[index]
#                         #print("closest tone list: ", closest_tone_list)
#                         #print("len closest tone list: ", len(closest_tone_list))
#                         for i in range(len(closest_tone_list)):
#                             #print('i:',i)
#                             closest_tone_index=closest_tone_list[i]
#                             #print('closest tone: ', closest_tone_list[i])
#                             check_mag=magnitudes[closest_tone_index]
#                             if check_mag > dominant_mag:
#                                 max_index=i
#                                 dominant_mag=check_mag
#                         dominant_tone = self.tones[closest_tone_list[max_index]]
#                         
#                         #precomputed note representation 1-87, A1-B7, fetched, attached to a corresponding list of notes for each pixel
#                         dominant_note_rep = self.representations_map_to_operate_with[index][max_index]        
                            
                        


                    
                # Crops up if the number of notes in a bin is too few.
                # As in low note_per_bin cases.
                except Exception as e:
                    print("Exception: ",e)
                    #set the output to be the first value in the bin, always the first index, in this case
                    #creates an output with padded zeros.
                    display_value=0
                    #set the dominant mag to be the first closes_tone to a 'real note's magnitude in the array slice, if they are all lower than the noise threshold.
                    dominant_mag = 0
                    #this should be the first closest /tone/ not the first halfway frequency
                    dominant_tone = 0
#                     dominant_note_rep = 0
                    

            else:
#                 print("bin errored out with -1")
                normalized_sum=0 #can't set these to -1 because they go through a log filter
                dominant_mag=0
                dominant_tone=0
                dominant_note_rep=0
                

            self.binned_fft_calc[index]=dominant_mag
            self.dominant_tones[index]=dominant_tone
#             self.dominant_notes_rep[index]=dominant_note_rep 
#         print(slice_sums)
#         print("binned_fft_calc:",self.binned_fft_calc)
#         print("dominant_tones:",self.dominant_tones)
#         print("dominant_notes_rep:",self.dominant_notes_rep)
        
        t_fft_bins1=ticks_ms()
#         print("fft_util:",ticks_diff(t_spectro_isolate_1,t_spectro_isolate_0), "binning_fft:",ticks_diff(t_fft_bins1,t_fft_bins0))
#         print(f"after binning: {gc.mem_free()}")
        
        return

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
            self.watchdog.heartbeat('Mic, FFT,and Colour')
            t_awaiting = ticks_ms()

            await flag.wait()
            
#             print(f"Before I2S: {gc.mem_free()}")
            t_mic_sample = ticks_ms()
            # this number should be non-zero, so the other coros can run. but if it's large
            # then can probably tune the buffer sizes to get more responsiveness
#             print("time spent awaiting: ", ticks_diff(t_mic_sample, t_awaiting)) #0-17ms
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
                samples[:]=np.frombuffer(sample_bytearray,dtype=np.int16)
#             print(f"after I2S: {gc.mem_free()}")  
                
            t1=ticks_ms()
            # Perform FFT over the entire 'samples' buffer, not just the small I2S_SAMPLE_COUNT chunk of it
            # calculate fft_mag from samples
            tfft1=ticks_ms()
            #fft_mags,dominants,reps =
            await self.fft_and_bin(samples)
            tfft2=ticks_ms()        

            mask = self.binned_fft_calc != 0 #set to 0 if some conditions are met in the fft_and_bin
            self.db_scaling[mask] = 20 * np.log10(self.binned_fft_calc[mask] / V_ref)
            self.db_scaling[~mask] = self.low_db_set_point                  
#             print(self.db_scaling)
            
#             tfft3=ticks_ms()
#             print("FFT_testing_scratchpad: ", ticks_diff(tfft2, tfft1))
            
            # FFTscaling only the fft_mags_array, when quiet, the maximum ambient noise dynamically becomes bright, which is distracting.
            # We need to make noise an ambient low level of intensity
             
            
#             print(f"after scaling to db range: {gc.mem_free()}")
            
            #auto gain control
            self.last_loudest_reading=max(self.db_scaling)
            if self.last_loudest_reading>self.highest_db_on_record:
#                 self.highest_db_on_record=0.8*self.highest_db_on_record+0.2*max(db_scaling)
                self.highest_db_on_record=self.last_loudest_reading
                
                print("highest db recorded: ",self.highest_db_on_record)
#                 print("loud: raising db top. db: ", self.highest_db_on_record)
                time_of_ceiling_raise=ticks_ms()
                spam_reduction_time=ticks_ms()
                
            elif (self.last_loudest_reading<self.highest_db_on_record) and (self.highest_db_on_record>self.max_db_set_point+1): #+1db is cheating the decay on the highest db value.
                time_since_raise=ticks_diff(ticks_ms(),time_of_ceiling_raise)
                
                if time_since_raise<3000:
                    time_since_last_update=ticks_diff(ticks_ms(),spam_reduction_time)
                    if time_since_last_update>500:#reduce the number of spam checks
                        spam_reduction_time=ticks_ms()
#                         print("checking if enough time has passed to lower the AGC")

                elif ticks_diff(ticks_ms(),time_of_ceiling_raise)>3000: #hardcoded delay on the AGC
                    self.highest_db_on_record=0.9*self.highest_db_on_record+0.1*self.max_db_set_point
                    
                    time_since_last_update=ticks_diff(ticks_ms(),spam_reduction_time)
                    if time_since_last_update>500:#reduce the number of spam checks
                        spam_reduction_time=ticks_ms()
#                         print("quiet: lowering db top to set point. db: ", self.highest_db_on_record)
            
#             print(f"after setting db range: {gc.mem_free()}")
            
            #make sure to rescale the upper end of the db array that informs the colour map range in the below interp function
            self.scale_and_clip_db_range[1]=max(self.max_db_set_point,self.highest_db_on_record)
            
            #scale to 0-255 range, can/should scale up for more hue resolution
            #
            self.fft_mags_array = np.interp(self.db_scaling, self.scale_and_clip_db_range, self.colour_index_range)
#             print("FFT_mags_array: ", self.fft_mags_array)
            
#             print(f"after scaling fft to db range: {gc.mem_free()}")
            
#             print("FFT_mags_int_list: ", fft_mags_int_list)
            tfft3=ticks_ms()
#             print("FFT: ", ticks_diff(tfft2, tfft1)) #42-77     
            
            # Apply cosmetics to values calculated above
            tint1=ticks_ms()
            if self.mode=="intensity":
                for i in range(len(self.fft_mags_array)):
                    if self.db_scaling[i]>self.low_db_set_point:
                        if self.brightness_sub_mode=='flat':
                            self.scaled_hues[i]=(
                                (self.intensity_lut[round(self.fft_mags_array[i])][0]*self.brightness)//255,
                                (self.intensity_lut[round(self.fft_mags_array[i])][1]*self.brightness)//255,
                                (self.intensity_lut[round(self.fft_mags_array[i])][2]*self.brightness)//255
                                )
                    
                        if self.brightness_sub_mode=="scaling":
                            self.scaled_hues[i]=(
                                int(self.intensity_lut[round(self.fft_mags_array[i])][0]*self.brightness*(self.fft_mags_array[i]/255))//255,
                                int(self.intensity_lut[round(self.fft_mags_array[i])][1]*self.brightness*(self.fft_mags_array[i]/255))//255,
                                int(self.intensity_lut[round(self.fft_mags_array[i])][2]*self.brightness*(self.fft_mags_array[i]/255))//255
                                )
                    
                    else:
                        self.scaled_hues[i]=(0,0,0)
                    
                for i in range(len(self.fft_mags_array)):
#                     self.intensity_hues[i]=self.intensity_lut[round(self.fft_mags_array[i])]
                    await leds.show_rgb(0,i,self.scaled_hues[i])
                    await leds.show_rgb(1,i,self.ring_buffer_hues_rgb[(self.buff_index)][i])
                    if self.show_menu_in_mic == False:
                        await leds.show_rgb(2,i,self.ring_buffer_hues_rgb[(self.buff_index-1)%-3][i])
#                 
                tint2=ticks_ms()    
#                 print(self.ring_buffer_hues_rgb)
#                 print(self.ring_buffer_intensities_rgb)
                self.buff_index = (self.buff_index + 1) % 3
                await leds.write(0) 
                await leds.write(1)
                await leds.write(2)
                
                # Second pass: update ring buffer AFTER displaying
                for i in range(len(self.fft_mags_array)):
                    self.ring_buffer_hues_rgb[self.buff_index][i] = self.scaled_hues[i]
#                     self.ring_buffer_intensities_rgb[self.buff_index][i] = round(self.fft_mags_array[i])
                
                
#                 print(f"after writing LEDs and ring buffers: {gc.mem_free()}")
                
            tint3=ticks_ms()
#             print("Intensity: ", ticks_diff(tint2, tint1)) #9-10
            
            
            tsyn1 = ticks_ms()
            if self.mode=="synesthesia":
#                 #use precomputed note representation to determine what hue to assign
#                 represented_notes=[(rep-1)%12 for rep in self.dominant_notes_rep]
# #                 print(dominants_notes)
#                 dominants_hues=[self.note_hues[rep] for rep in represented_notes]
# #                 print("hues from note assign: ", represented_notes)
#                 scaled_hues=tuple(((r*brightness)//255,(g*brightness)//255,(b*brightness)//255) for (r,g,b),brightness in zip(dominants_hues,fft_mags_int_list))
# #                 print("scaled_hues: ",scaled_hues)
#                 print("new frame")
#                 print(self.dominant_tones)
                for i in range(len(self.dominant_tones)):
                    
                    if self.db_scaling[i]<self.low_db_set_point:
                        self.scaled_hues[i]=(0,0,0)
#                         print(0)
                    else:
                        if self.dominant_tones[i]>0: #the menu pan sets 'outside of range' pixels to -1
                            self.dominant_notes_rep[i]=12.*np.log2(self.dominant_tones[i]/440.)+49.
                            note=round(self.dominant_notes_rep[i]-1)%12 #the -1 is to go from notes starting at 1 for A0 to starting at 0 for the hue index
                        else:
                            note=0
                        
                        #this works to present 'flat' notes: no scaling of brightness with the intensity of the note
                        if self.brightness_sub_mode=='flat':
                            self.scaled_hues[i]=(
                                (self.note_hues[note][0]*self.brightness)//255,
                                (self.note_hues[note][1]*self.brightness)//255,
                                (self.note_hues[note][2]*self.brightness)//255)
                        
                        #uncomment this if you want 'bright' notes: notes that scale with their played intensity. Cap to the lowest brightness that differentiates hues.
                        if self.brightness_sub_mode=='scaling':
                            self.scaled_hues[i]=(
                                int(self.note_hues[note][0]*(self.brightness*(self.fft_mags_array[i]/255)))//255,
                                int(self.note_hues[note][1]*(self.brightness*(self.fft_mags_array[i]/255)))//255,
                                int(self.note_hues[note][2]*(self.brightness*(self.fft_mags_array[i]/255)))//255)
#                             print(self.scaled_hues[i])

                        #too fancy for own good: microtone representation- a colour interperlation for where the dominant frequency in a bin is on the colour scale
#                         note_frac=note%1
#                         lower_index=int(note)%12 #12 is the length of the hues I have chosen
#                         upper_index=(lower_index+1)%12
#                         lower_r,lower_g,lower_b=self.note_hues[lower_index]
#                         upper_r,upper_g,upper_b=self.note_hues[upper_index]
#                     
#                         self.scaled_hues[i]=(
#                             (int(lower_r+note_frac*(upper_r-lower_r))*self.brightness)//255,    
#                             (int(lower_g+note_frac*(upper_g-lower_g))*self.brightness)//255,
#                             (int(lower_b+note_frac*(upper_b-lower_b))*self.brightness)//255,
#                         )
                 
                
                for i in range(len(self.dominant_notes_rep)):
                    await leds.show_rgb(0,i,self.scaled_hues[i])
                    await leds.show_rgb(1,i,self.ring_buffer_hues_rgb[(self.buff_index)][i])
                    if self.show_menu_in_mic == False:
                        await leds.show_rgb(2,i,self.ring_buffer_hues_rgb[(self.buff_index-1)%-3][i])
                
                self.buff_index = (self.buff_index + 1) % 3
                await leds.write(0)
                await leds.write(1)
                await leds.write(2)
                
                # Second pass: update ring buffer AFTER displaying
                for i in range(len(self.dominant_notes_rep)):
                    self.ring_buffer_hues_rgb[self.buff_index][i] = self.scaled_hues[i]
#                     self.ring_buffer_intensities_rgb[self.buff_index][i] = round(self.fft_mags_array[i])
                
#             print(self.dominant_notes_rep)   
            tsyn2=ticks_ms()
#             print("synesthesia: ", ticks_diff(tsyn2, tsyn1)) #11-13
            
#             print(f"after colouring: {gc.mem_free()}")
            
            
            
            
            tmenu1=ticks_ms()
            if self.menu_init==True: #annoying to have a single use line but this is a quick fix.                                
                #init the status pix or it will keep the last power-off menu state
                leds.status_pix[0]=(0,20,0)#the status LED is grb
                await leds.write(3)
                self.menu_init=False
            
            if self.show_menu_in_mic == True:
                if self.menu_thing_updating=="brightness" and self.menu_update_required==True:                       
                    self.status_led_off=False
                    
                    #print("brightness in mic: ",self.brightness)
                    
                    #print make the first pixel, left to right, show with brightness of the display, in one channel only (e.g. red)
                    if self.brightness_sub_mode=='flat':
                        #update onboard LED/mini-menu
                        leds.status_pix[0]=(0,20,0)#the status LED is grb
                        await leds.write(3)
                        await leds.show_hsv(2,11,self.flat_hue_b,255,int(self.brightness))
                    else:
                        #update onboard LED/mini-menu
                        leds.status_pix[0]=(15,20,0)#the status LED is grb
                        await leds.write(3)
                        await leds.show_hsv(2,11,self.scaling_hue_b,255,int(self.brightness))

                    #skip the first pixel, it's already been set.
                    for i in range(1,12):
                        #if the pixel is at the brightness index
                        if i==self.brightness_index:
                            if self.brightness_sub_mode=='flat':
                                await leds.show_hsv(2,11-i,self.flat_hue_b,255,int(self.brightness))
                            else:
                                await leds.show_hsv(2,11-i,self.scaling_hue_b,255,int(self.brightness))
                                
                        # otherwise, blank out the non needed menu pixels
                        else:
                            await leds.show_hsv(2,11-i,0,0,0)
                            
                    #reset to allow the next update
                    self.menu_update_required=False
                    
                if self.menu_thing_updating=="resolution" and self.menu_update_required==True:
                    if self.resolution_sub_mode=="notes_per_pix" and self.menu_update_required==True:
                        self.status_led_off=False
                        
                        #update onboard LED/mini-menu
                        leds.status_pix[0]=(5,30,0)#the status LED is grb
                        await leds.write(3)
                
                        #update fft_ranges if needed
                        self.schedule_update(str(self.notes_per_led))
                        if self.update_queued:
                            await self.process_update()
                                                
                        for i in range(0,12): #blank out LEDs
                            await leds.show_hsv(2,i,0,0,0)
                            #3print(self.menu_to_operate_with)
                            try:
                                if self.menu_to_operate_with[i]==-1:
                                    await leds.show_hsv(2,i,0,0,0)
    #                             await leds.show_hsv(2,i,self.notes_per_pix_hue,255,int(self.brightness*0.1))
                                elif self.menu_to_operate_with[i]>=0:
                                    await leds.show_hsv(2,i,self.menu_to_operate_with[i],255,self.brightness)
                            except:
                                await leds.show_hsv(2,i,0,0,0)
                                
    #                     for i in range(0,self.window_slice_len,int(12/self.notes_per_led)): #the division of 12 is required to scale the right way around, six notes per led should show an octave every two leds, not every six
    #                         await leds.show_hsv(2,i,900*i,255,self.brightness) #make each octave a different colour
                        self.menu_update_required=False
                        
                    if self.resolution_sub_mode=="panning" and self.menu_update_required==True:
                        self.status_led_off=False
                        
                        #update onboard LED/mini-menu
                        leds.status_pix[0]=(0,0,20)#the status LED is grb, blue is distinct, the purple turns to red through the flex.
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
                            if self.menu_to_operate_with[i]>=0:
                                await leds.show_hsv(2,i,self.menu_to_operate_with[i]+self.octave_shift_hue,255,self.brightness)
                        

                        self.menu_update_required=False
                    
                    
                if self.menu_thing_updating=="highest_db" and self.menu_update_required==True:
                    self.status_led_off=False
                    
                    #update onboard LED/mini-menu
                    leds.status_pix[0]=(20,0,0)#the status LED is grb
                    await leds.write(3)
                    
                    #print("loudest reading: ", loudest_reading)
                    db_per_bin=-10 #-120 to 0 decibels makes a nice 10 decible scale bar
                    #for loop looks odd, because again it's decibels, and because I flipped it to be left to right. -1 to ensure 0 index is included
                    for i in range(11,-1,-1):
                        #conditions will look odd here because the values to work with are in decibels, which are -ve
                        if i*db_per_bin <= self.last_loudest_reading:
                            #draw loudest measured decibel signal, from -120 to 0
                            await leds.show_hsv(2,i,self.octave_shift_hue,255,int(self.brightness*0.5))#annoying indicies, minus one is to line up with pixels  
                        else:    
                            #blank out leds
                            await leds.show_hsv(2,i,0,0,0)  
                    
                        #draw level top first, so that it does not overide the highest db pixel indicator, in the case the highest value is greater than the high db but less than the next pixel
                        if (self.highest_db_on_record>self.max_db_set_point):
#                             if (i*db_per_bin <= loudest_reading < (i-1)*db_per_bin):
#                                 await leds.show_hsv(2,i-1,5000,255,int(self.brightness))
                            if (i*db_per_bin <= self.highest_db_on_record < (i-1)*db_per_bin):
                                await leds.show_hsv(2,i,5000,255,int(self.brightness*0.5))
                        
                        #draw lowest db setting if in intensity mode
                        if i*db_per_bin==self.low_db_set_point: #and self.auto_low_control==False:
                            if self.db_selection=='min_db_set':
                                await leds.show_hsv(2,i,20000,255,int(self.brightness*0.5))#green is bright as
                            else:
                                await leds.show_hsv(2,i,0,255,int(self.brightness*0.5))                                
                                
#                         #draw lowest db setting, auto scaled, if in synesthesia mode
#                         if i*db_per_bin==self.low_db_set_point and self.auto_low_control==True:
#                             if self.db_selection=='min_db_set':
#                                 await leds.show_hsv(2,i-1,20000,255,int(self.brightness*0.5))#green is bright as
#                             else:
#                                 await leds.show_hsv(2,i-1,0,255,int(self.brightness*0.5))
                        
                        #draw highest db setting
                        if i*db_per_bin==self.max_db_set_point:
                            if self.db_selection=='max_db_set':
                                await leds.show_hsv(2,i,20000,255,int(self.brightness*0.5))#green is  bright as
                            else:
                                await leds.show_hsv(2,i,0,255,int(self.brightness*0.5))
                                
            if self.status_led_off==True:
                #update onboard LED/mini-menu
                leds.status_pix[0]=(0,0,0)#the status LED is grb
                await leds.write(3)
                            
                #draw update the menu?
#                     await leds.write(2)
                    
                    
                    #This determines if the menue keep updating or is a one and done?
#                     self.menu_update_required=False
                    
#                 if self.menu_thing_updating=="hue_select" and self.menu_update_required==True:
#                     #update onboard LED/mini-menu
#                     leds.status_pix[0]=(0,0,20)#the status LED is grb
#                     await leds.write(3)
#                     
#                     for i in range(0,12):
#                         await leds.show_hsv(2,i,0,0,0)
                        
            tmenu2=ticks_ms()
            total_ms=ticks_diff(tmenu2,t_awaiting)
#             print(f"after menuing: {gc.mem_free()}")
            
            #Smooth to a consistent fps, which looks nicer, imo.
            fps=15
            frame_time=1000//fps
            if total_ms < frame_time:
                wait_time=frame_time-total_ms
#                 leds.status_pix[0]=(0,0,0)#the status LED is grb
#                 await leds.write(3)
            else:
                wait_time=0
#                 leds.status_pix[0]=(50,50,50)#the status LED is grb
#                 await leds.write(3)
            await asyncio.sleep_ms(wait_time) #yeild control. #this one line appears to have made the program substantially more responsive in the menu side of things.
                
#             if self.mode=="Synesthesia":
#                 print("total (ms)", total_ms, "mic_sample",ticks_diff(t1,t0), "fft_and_bin: ", ticks_diff(tfft2, tfft1), "synesthesia: ", ticks_diff(tsyn2, tsyn1), "fps:", 1000//total_ms, "delay:", wait_time)
#             else:
#                 print("total (ms)", total_ms, "mic_sample",ticks_diff(t1,t0), "fft_and_bin: ", ticks_diff(tfft2, tfft1), "Intensity update 0 and buff: ", ticks_diff(tint2, tint1),"Intensity write LEDs: ", ticks_diff(tint3, tint2), "fps:", 1000//total_ms, "delay:", wait_time)
#         
