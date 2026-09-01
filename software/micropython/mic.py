#Welcome to the spaghetti monolith.

import config
from ulab import utils
import json
import math
import asyncio
from leds import Leds
from audio_sampler import AudioSampler
from fft import Fft
from ulab import numpy as np
from time import ticks_ms, ticks_diff
from utils.closest_tone_calculator import PrecomputedClosestTones
from utils.menu_calculator import PrecomputedMenu

# import gc
# gc.collect()

FREQUENCY_RESOLUTION=config.SAMPLE_RATE/config.SAMPLE_COUNT
TUNING_A4_HZ=440.
BINS_PER_OCTAVE=2

V_ref=8388607 #this value is microphone dependant, for the DFROBOT mic, which is 24-bit I2S audio, that value is apparently 8,388,607 

magnitudes=np.zeros(config.SAMPLE_COUNT, dtype=np.float) #this is the result from the FFT

class Mic():
    def __init__(self,watchdog):
        self.watchdog=watchdog      
        
        self.sampler=AudioSampler()
        
        self.fft=Fft()
        
#         like this?? self.led_renderer=LedRender()
        
        self.menu_bar=MenuBar()
        
#         self.mode="determiner"
        self.mode="intensity"
#         self.mode="synesthesia"
        
        self.status_led_off=False
        self.show_menu_in_mic=False
        self.menu_thing_updating="brightness"
        self.menu_update_required=False
        self.menu_init=True #hopefully just used once a start up.
        
        #converts fft to db
        self.db_scaling=np.zeros(config.NUM_LEDS,dtype=np.float)
        self.max_db_set_point=config.BOOT_MAX_DB
        self.highest_db_on_record=self.max_db_set_point
        self.low_db_set_point=config.BOOT_MIN_DB
        self.db_selection="max_db_set"
        self.last_loudest_reading=-80
        self.auto_low_control=False
        
        # Figure out what tones correspond to what magnitudes out of the fft, with respect to the mic sampling parameters
        self.tones=FREQUENCY_RESOLUTION*np.arange(config.SAMPLE_COUNT/2)
        
        #determines the values that are actually accounted for in display colour scaling
        self.scale_and_clip_db_range=np.array([self.low_db_set_point, self.highest_db_on_record]) #for colouring: values chosen by looking at my spectrogram. I think a value of zero is a shockwave.
        # Preallocated arrays
        #stores result from fft
        self.binned_fft_calc=np.zeros(config.NUM_LEDS,dtype=np.float)
        self.dominant_tones=[0]*config.NUM_LEDS
        self.dominant_notes_rep=np.zeros(config.NUM_LEDS,dtype=np.float)
   
        
        self.fft_mags_array=np.zeros(config.NUM_LEDS,dtype=np.float)
        self.fft_mags_int_list=[0]*config.NUM_LEDS
        
        
        self.noise_floor=1000
        
        self.resolution_sub_mode='notes_per_pix'
        
        #intializing varables here is fine, but their handling and setting should be in the menu.
        self.brightness_sub_mode='scaling'
        self.flat_hue=0
        self.scaling_hue=10000
        
        
        self.brightnesses=config.BRIGHTNESS_OPTIONS
        self.brightness_index=config.BOOT_BRIGHTNESS_INDEX
        self.brightness=self.brightnesses[self.brightness_index] #[0-255]
        
        # Calculate the defined frequencies of the musical notes
#         self.notes=np.arange(1.,85.)
#         self.note_frequencies=TUNING_A4_HZ*(2**((self.notes-49)/12))
        ##print("note frequencies: ", note_frequencies)

        # Event required to change note_per_led number
        self.number_of_octaves=7
        self.notes_per_led_index=config.BOOT_RESOLUTION_INDEX
        self.notes_per_led_options=[1,2,3,4,6,12]
        self.notes_per_led=self.notes_per_led_options[self.notes_per_led_index]
        self.absolute_note_index=0
        
        self.start_range_index=0 #this is a variable that determines where in a precomputed list of ranges of indexes to start displaying the fft results 
        self.full_window_len=12
        self.window_slice_len=12 #this is for clamping the start note when the octave resolution/notes_per_LED is switched 
        self.max_window_overreach=5 #this limit is determined by how many octaves can be shown at once, which is determined by the fft sampling parameters. Currently 7 octaves. 12Leds-7octaves=5 to pad in worst case
        
        self.notes_per_pix_hue=0
        self.octave_shift_hue=42000 #blue, determined by looking at hue learner.
        
        
        #Auto gain control time flags
        self.time_of_ceiling_raise=0
        self.time_since_raise=0
        self.spam_reduction_time=0
        self.time_since_last_update=0       
        
        
        #load the precomupted octave menu and select the dictionary entry that corresponds to the current notes_per_led option
        #create two buffers to avoid async clashes
        self.precomputed_menus=PrecomputedMenu("utils/precomputed_octave_display.json")
        if self.precomputed_menus.load():
            JSON_menu=self.precomputed_menus.get(str(self.notes_per_led))
            self.menu_buffer_a=JSON_menu[self.start_range_index:config.NUM_LEDS]
            self.menu_buffer_b=JSON_menu[self.start_range_index:config.NUM_LEDS]        
        
        
        #load the precomupted octave menu and select the dictionary entry that corresponds to the current notes_per_led option
        #create two buffers to avoid async clashes
        self.precomputed_closest_tones=PrecomputedClosestTones("utils/closest_tones.json")
        if self.precomputed_closest_tones.load():
            JSON_close_tones=self.precomputed_closest_tones.get(str(self.notes_per_led))
            self.closest_tones_buffer_a=JSON_close_tones[self.start_range_index:config.NUM_LEDS]
            self.closest_tones_buffer_b=JSON_close_tones[self.start_range_index:config.NUM_LEDS] 
        
            #retrive and store the bins for each individual note for use in chroma key generation, trim out start to get to 'a' [28,29], see FFT spreadsheet
            C65dot41Hz_index=15 #determined by fft parameters
            self.indiv_note_bins=self.precomputed_closest_tones.get('1')[C65dot41Hz_index:]
            print("Start_bin indexes:", self.indiv_note_bins) #must line up with note A for chromatic aggretation to assign tone intensity values to correct notes
            print("Tone corresponding to first index in that bin.", self.tones[self.indiv_note_bins[0][0]])
            
   
   
   
   
   
            
        ###_determiner
        #rotate to have C first.
        self.notes=['c','c#','d','e♭','e','f','f#','g','a♭','a','b♭','b',]
        self.root_position=[0,1,2,3,4,5,6,7,8,9,10,11]
        self.frame_filtered_chroma_key=np.zeros(12)
        self.top_N_notes=4 
#         self.modes={'Ionian':[1,0,1,0,1,1,0,1,0,1,0,1]}    
        self.modes={'Ionian':[6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88], #Krumhansl's empirically derived weights #Sonnet 4.6    
                    'Aeolian': [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17] # Claude sonnet 4.6: minor profile C-first (rotate: la=A is index 9, so shift left by 9)
        }
        
        
        
        self.frame_scores_for_mode_and_root={"Ionian":np.zeros((12)),"Aeolian":np.zeros((12))}
        self.column_scores={}
        
        self.history_frame_length=80
        self.history_buffer_ion = np.zeros((self.history_frame_length,12))
        self.history_buffer_aeo = np.zeros((self.history_frame_length,12))
        self.history_buffers = {'Ionian': self.history_buffer_ion,'Aeolian': self.history_buffer_aeo}
        self.history_buffer_pointer = 0

        with open('utils/three_x_three_font.json', 'r') as f:
            self.font = json.load(f)






        ###_BUFFERS_###
        #create buffer pointers
        self.active_buffer='a'
        self.menu_to_operate_with=self.menu_buffer_a
        self.closest_tone_indexes_to_operate_with=self.closest_tones_buffer_a
        
        #create update flags
        self.update_queued=False
        self.next_data_key=None        
        
        
        
        
        
        #led value handling stuff
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
        
        self.intensity_hues=[(0,0,0)]*12
        #replace masks and HSV calcs with LUT
#         self.intensity_lut = create_color_lut()
        self.intensity_lut = config.INTENSITY_COLOR_LUT
        
        self.colour_index_range=np.array([0,255])
#         print("intensity_lut",self.intensity_lut)
        
        #set hues for synesthesia mode based on notes picked in RGB in LED_note_hue_picker, translate to HSV values
        self.note_hues=config.SYN_NOTE_HUES
       
       
       
       
       
       
        
    
    async def relocate_start_range_index(self):
        #7 octaves, 12leds/xNotes, 12 Leds 
        self.start_range_index=math.floor(self.absolute_note_index/self.notes_per_led)
        #print("relocated start range index",self.start_range_index)
        
        #self.absolute_note_index+=self.notes_per_led
        #self.absolute_note_index-=self.notes_per_led
        
        #The absolute note index Must always be a multiple of the notes_per_led, i.e. it must be rounded when the resolution is changed
        #self.absolute_note_index=







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
            inactive_closest_tone_buffer=self.precomputed_closest_tones.get(self.next_data_key)
            
            self.full_window_len=len(inactive_closest_tone_buffer)
#             print("len full json array: ",len(inactive_fft_buffer_json))
            
            inactive_menu_range=inactive_menu_buffer[self.start_range_index:self.start_range_index+config.NUM_LEDS]
            inactive_closest_tones_range=inactive_closest_tone_buffer[self.start_range_index:self.start_range_index+config.NUM_LEDS]
            
            self.window_slice_len=len(inactive_closest_tones_range)
#             print("window_slice_Len: ",self.window_slice_len)
            window_overextension=config.NUM_LEDS-self.window_slice_len
            
            if len(inactive_menu_buffer)<config.NUM_LEDS: #and window_overextension<self.max_window_overreach:
#                 inactive_fft_buffer_ranges = inactive_fft_buffer_ranges + [[-1,-1]] * window_overextension
                inactive_menu_range += [-1] * (config.NUM_LEDS-len(inactive_fft_buffer_ranges))
                inactive_closest_tones_range += [[-1]] * (config.NUM_LEDS-len(inactive_fft_buffer_ranges))#this must be an array slice, or else the summation stuff later crashes!
                
#             print("inactive_buffer: ",inactive_fft_buffer_ranges)
            
            if inactive_buffer=='a':
                self.menu_buffer_a=inactive_menu_range
                self.closest_tones_buffer_a=inactive_closest_tones_range
            else:
                self.menu_buffer_b=inactive_menu_range
                self.closest_tones_buffer_b=inactive_closest_tones_range
            #swap buffers 'atomically'
            
            self.active_buffer='b' if self.active_buffer=='a' else 'a'
#             print('active buffer: ',self.active_buffer)
            
            if self.active_buffer=='a': 
                self.menu_to_operate_with=self.menu_buffer_a
                self.closest_tone_indexes_to_operate_with=self.closest_tones_buffer_a
            else:
                self.menu_to_operate_with=self.menu_buffer_b
                self.closest_tone_indexes_to_operate_with=self.closest_tones_buffer_b
            
#             print("FFT_closest_tones_swap: ",self.closest_tone_indexes_to_operate_with)
            #deactivate the update flags
            self.update_queued=False
            self.next_data_key=None
            

#             await uasyncio.sleep_ms(0)  # Yield to other tasks

    async def bin_fft(self, magnitudes):
        
        t_chroma0=ticks_ms()
        if self.mode=="determiner":
#             print("building chromakey")
            frame_chroma_key=np.zeros(12)
            
            #have to reverence the first list inside the indiv_note_bins, as it is the lowest set of note lists, unlike
            #other note per pixel settings, there is only one entry per sub list for "1" note per pixel
            for index, note in enumerate(self.indiv_note_bins):
                #scale/wight lower notes so they contribute more to the harmonic determination
                weight=300 if index < 24 else 1000
                #add new signal from fft for each bin
                #hardcoded wrap around for 12 notes in western music
                frame_chroma_key[index%12] += (magnitudes[note[0]]/weight) 
            
#             print(list(frame_chroma_key))
            
            threshold=np.sort(frame_chroma_key)[-self.top_N_notes]
            filtered_chroma_key=np.array([v if v>=threshold else 0.0 for v in frame_chroma_key])
            
#             print("frame_key:", list(frame_chroma_key))
#             print("sorted_key:", list(np.sort(frame_chroma_key)))
#             print("filtered_key:", list(filtered_chroma_key))
            
            self.frame_filtered_chroma_key=filtered_chroma_key
#             print("chromakey:",self.chroma_key)
            t_chroma1=ticks_ms()
#             print("ticks_chroma:",ticks_diff(t_chroma1,t_chroma0))
            
        
        
        if self.mode=="intensity" or self.mode=="synesthesia":
                
            #ranges_to_operate_with is a buffer containing precomputed boundaries for the notes_per_pixel bins of interest, the buffer is updated with menuing.
            #this has been updated to reflect the amplitude of specific tones that closely match musical notes,
            #hopefully simplifying bleed and enabling better chord detection
            
            for index, f in enumerate(self.closest_tone_indexes_to_operate_with):
    #             print(self.closest_tone_indexes_to_operate_with)
                if f[0]>=0: #check if the bin has not been errored out with -1, e.g.: if the menu or bins are shorter than the display.
                    
                    
                    #amplitude of max tone in bin
                    dominant_mag = np.max(magnitudes[f[0]:f[-1]])
                    ## Find out where the max magnitude in the slice is, then add the starting index of the slice,
                    ## or you'll get veeeery odd frequency curves.
                    where_dominant_mag=np.argmax(magnitudes[f[0]:f[-1]])+f[0]
                    dominant_tone=self.tones[where_dominant_mag]
                        

                else:
    #                 print("bin errored out with -1")
                    normalized_sum=0 #can't set these to -1 because they go through a log filter
                    dominant_mag=0
                    dominant_tone=0
                    dominant_note_rep=0
                
                              

                self.binned_fft_calc[index]=dominant_mag
                self.dominant_tones[index]=dominant_tone
                
                mask = self.binned_fft_calc != 0 #set to 0 if some conditions are met in the fft_and_bin
                self.db_scaling[mask] = 20 * np.log10(self.binned_fft_calc[mask] / V_ref)
                self.db_scaling[~mask] = self.low_db_set_point                  
#             print(self.db_scaling)
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


        t_mic_sample = None
        while True:
            self.watchdog.heartbeat('Mic, FFT,and Colour')
            t_awaiting = ticks_ms()

            samples = await self.sampler.sample()
            magnitudes = await self.fft.crunch(samples)
                
            await self.bin_fft(magnitudes)

            
            #auto gain control
            self.last_loudest_reading=max(self.db_scaling)
            
            #if there is a peak, log it and start a gain lowering timer
            if self.last_loudest_reading>self.highest_db_on_record:
#                 self.highest_db_on_record=0.8*self.highest_db_on_record+0.2*max(db_scaling)
                self.highest_db_on_record=self.last_loudest_reading
                
                print("highest db recorded: ",self.highest_db_on_record)
#                 print("loud: raising db top. db: ", self.highest_db_on_record)
                self.time_of_ceiling_raise=ticks_ms()
                self.spam_reduction_time=ticks_ms()
            
            #if the last loudest sound is below the set max, then do checks on whether to lower the agc
            elif (self.last_loudest_reading<self.highest_db_on_record) and (self.highest_db_on_record>self.max_db_set_point+1): #+1db is cheating the decay on the highest db value.
                try:
                    self.time_since_raise=ticks_diff(ticks_ms(),self.time_of_ceiling_raise)
                except:
                    self.time_since_raise=3000
                    print("timing issue")
                
                if self.time_since_raise<3000:
                    self.time_since_last_update=ticks_diff(ticks_ms(),self.spam_reduction_time)
                    if self.time_since_last_update>500:#reduce the number of spam checks
                        self.spam_reduction_time=ticks_ms()
#                         print("checking if enough time has passed to lower the AGC")

                elif ticks_diff(ticks_ms(),self.time_of_ceiling_raise)>=3000: #hardcoded delay on the AGC
                    self.highest_db_on_record=0.9*self.highest_db_on_record+0.1*self.max_db_set_point
                    
                    self.time_since_last_update=ticks_diff(ticks_ms(),self.spam_reduction_time)
                    if self.time_since_last_update>500:#reduce the number of spam checks
                        self.spam_reduction_time=ticks_ms()
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
            
              
            
            
            t_determiner0=ticks_ms()
            #some code may repeat in here for the sake of cleaness. There are alot of print statements for debug
            
            if self.mode=="determiner":
                #to keep consistent pattern, make a dict for the summed buffer that is later used to find the dominant match
                summed_frame_buffer_score={}
                
                #score each possible set against the chromakey generated in the fft_and_bin,
                for mode in self.modes:
                    #mutate in place to clear the scores
                    scores = self.frame_scores_for_mode_and_root[mode]
                    for i in range(len(scores)):
                        scores[i] = 0.
                        
                    for index,root_note in enumerate(self.notes):
                        #sonnet 4.6's idea
                        #for each root, score the appearance of notes
                        for i in range(12):
    #                         if mask[i]==1: current_scale[i]=notes[(i + root_position[index]) % 12] 
                            
                            #Turn the filtered key into a score for each root for each mode
                            krumhansl_weight=self.modes[mode][(i - self.root_position[index]) % 12]
                            chroma_key_weight=self.frame_filtered_chroma_key[i]
                            self.frame_scores_for_mode_and_root[mode][index] += krumhansl_weight*chroma_key_weight 
                    
                    #add weighted keys into history buffer
                    self.history_buffers[mode][self.history_buffer_pointer]=self.frame_scores_for_mode_and_root[mode]
                    #update history buffer index/pointer
                    self.history_buffer_pointer+=1
                    self.history_buffer_pointer%=self.history_frame_length
                
                #print summed buffer along column for best fit of keys, should show best match filling buffer for sustained chord
                    summed_frame_buffer_score['Ionian']=np.sum(self.history_buffers['Ionian'],axis=0)
                    summed_frame_buffer_score['Aeolian']=np.sum(self.history_buffers['Aeolian'],axis=0)
#                 args = []
#                 for note, key in zip(self.notes, list(a)):
#                     args += [note, key]
#                 print(*args)
                
                
                #take the top (two?) framescore and display, parsing to see if a "flat/sharp"symbol is required.
                num_top_results_to_display=2
                top_indices = {}
                max_score=0
                top_mode='Ionian'
                top_note_string='a'
                for mode in self.modes:
                    top_indices[mode]=[]
                    temp_scores=list(summed_frame_buffer_score[mode])
                    for _ in range(num_top_results_to_display):
                        best=np.argmax(temp_scores)
                        top_indices[mode].append(best)
                        temp_scores[best]=-1
                    
                    max_index=top_indices[mode][0]
                    mode_max=summed_frame_buffer_score[mode][max_index]
                    if mode_max > max_score:
                        max_score = mode_max
                        top_note_string=self.notes[max_index]
                        top_mode=mode
                    
                    
                #some zipping for printing/checking
                args=[]
                for mode in self.modes:
                    for i in top_indices[mode]:
                        args+=[mode, self.notes[i], summed_frame_buffer_score[mode][i]]
                print(*args)
#                 print("best guess (major only for now):", self.notes[np.argmax(summed_frame_buffer_score)])
#                 print(list(summed_frame_buffer_score))

                
                #find top of tops
                #display top, with some fading in the future
#                 #build Led info strings
#                 top_top={}
#                 top_indices
#                 top=self.notes[top_indices[0]]
                
                accent= '#' if '#' in top_note_string else '♭' if '♭' in top_note_string else '-'
                #strip out the accent, as otherwise there is a key error (I didn't just write in sharps and flats in the font \
                #as I found it cleaner to have 3x3,1x3,and3x3 for the different info bits
                top=top_note_string[0]
                
                _0=self.font[top][0]+self.font[accent][0]+self.font[top_mode][0]
                _1=self.font[top][1]+self.font[accent][1]+self.font[top_mode][1]
                _2=self.font[top][2]+self.font[accent][2]+self.font[top_mode][2]
#                 print(_0)
                
                #have to translate font into rgb values, assign once per display element/section
                note_col=tuple(c*self.brightness//255 for c in (255,0,0))
                accent_col=tuple(c*self.brightness//255 for c in (0,255,0))
                mode_col=tuple(c*self.brightness//255 for c in (0,0,255))
                
                comp=[_0,_1,_2]
                
                
                for i,bits in enumerate(comp):
                     comp[i] = [note_col if b else (0,0,0) for b in bits[0:3]] + \
                           [accent_col if b else (0,0,0) for b in bits[3:4]] + \
                           [mode_col if b else (0,0,0) for b in bits[4:7]]
#                 print(comp)
                
                #write to LEDs
                for i in range(config.NUM_LEDS):
                    await leds.show_rgb(0,i,comp[0][i])
                    await leds.show_rgb(1,i,comp[1][i])
                    await leds.show_rgb(2,i,comp[2][i])
                
                await leds.write(0) 
                await leds.write(1)
                await leds.write(2)
                                                                               
                
            t_determiner1=ticks_ms()
            
            
            
            
            
            
            
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
            
            
            
            
            
            self.led_render.show_menu(self)
            
            
            tmenu1=ticks_ms()
            if self.menu_init==True: #annoying to have a single use line but this is a quick fix.                                
                #init the status pix or it will keep the last power-off menu state
                leds.status_pix[0]=(0,20,0)#the status LED is grb
                await leds.write(3)
                self.menu_init=False
            
            if self.show_menu_in_mic == True:
                #self.mode_renderer.render() #this is possible, but the current monolith is not broken, and the prospect of passing back flags was giving me a headache, so I ditched it.
                #The actual target is making the menu scale and offset according to a config.
                
                if self.menu_thing_updating=="brightness" and self.menu_update_required==True:                       
                    self.status_led_off=False
                    
                    #print("brightness in mic: ",self.brightness)
                    #clear menu
                    await leds.fill(2,(0,0,0))
                    
                    #print make the first pixel, left to right, show with brightness of the display, in one channel only (e.g. red)
                    if self.brightness_sub_mode=='flat':
                        #update onboard LED/mini-menu
                        leds.status_pix[0]=(0,20,0)#the status LED is grb
                        await leds.write(3)
                        await leds.show_hsv(2,config.MENU_SIZE+config.MENU_LED_OFFSET,self.flat_hue,255,int(self.brightness))
                    else:
                        #update onboard LED/mini-menu
                        leds.status_pix[0]=(15,20,0)#the status LED is grb
                        await leds.write(3)
                        await leds.show_hsv(2,config.MENU_SIZE+config.MENU_LED_OFFSET,self.scaling_hue,255,int(self.brightness))

                    #skip the first pixel, it's already been set.
                    for i in range(1,config.MENU_SIZE+1): #+1 because range drops last pixel
                        #if the pixel is at the brightness index
                        if i==self.brightness_index:
                            if self.brightness_sub_mode=='flat':
                                await leds.show_hsv(2,config.MENU_SIZE+config.MENU_LED_OFFSET-i,self.flat_hue,255,int(self.brightness)) #-i arrangement is to make the menu work left to right
                            else:
                                await leds.show_hsv(2,config.MENU_SIZE+config.MENU_LED_OFFSET-i,self.scaling_hue,255,int(self.brightness))
                                
                        # otherwise, blank out the non needed menu pixels
                        elif i==config.MENU_SIZE:
                            pass
                        else:
                            await leds.show_hsv(2,config.MENU_SIZE+config.MENU_LED_OFFSET-i,0,0,0)
                            
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
                                                
                        for i in range(0,config.NUM_LEDS): #blank out LEDs
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
                        for i in range(0,config.NUM_LEDS): #blank out LEDs
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
                    #-120 to 0 decibels makes a nice 10 decible scale bar
                    #db_settings_per_bin=
                    
                    #for loop looks odd, because again it's decibels, and because I flipped it to be left to right. -1 to ensure 0 index is included
                    for i in range(config.MENU_SIZE,-1,-1):
                        #conditions will look odd here because the values to work with are in decibels, which are -ve
                        #-1 required to move positive step size into -120 to 0 range.
                        
                        #blue, shows traditional 'eq' meter like effect
                        if -1*i*config.DB_COARSE_STEP_SIZE <= self.last_loudest_reading:
                            #draw loudest measured decibel signal, from -120 to 0
                            await leds.show_hsv(2,i,self.octave_shift_hue,255,int(self.brightness*0.5))  
                        else:    
                            #blank out leds
                            await leds.show_hsv(2,i,0,0,0)  
                    
                        #draw the peak first in orange ish - so that it does not overide the highest db setting pixel indicator, in the case the highest value is greater than the high db but less than the next pixel
                        if (self.highest_db_on_record>self.max_db_set_point):
#                             if (i*db_per_bin <= loudest_reading < (i-1)*db_per_bin):
#                                 await leds.show_hsv(2,i-1,5000,255,int(self.brightness))
                            #
                            if (-1*i*config.DB_COARSE_STEP_SIZE <= self.highest_db_on_record < -1*(i-1)*config.DB_COARSE_STEP_SIZE):
                                await leds.show_hsv(2,i,5000,255,int(self.brightness*0.5)) 
                        
                        #more complex for a crunched display
                        #derivation explained:
                        # rem = set_db_value/(resolution_or_step_size*db_settings_per_bin)
                        rem_low=(self.low_db_set_point%(config.DB_SETTINGS_PER_BIN*config.DB_STEP_SIZE))
#                         print('rem0',rem0)
                        rem_high=(self.max_db_set_point%(config.DB_SETTINGS_PER_BIN*config.DB_STEP_SIZE))
#                         print('rem1',rem1)
                        # step_size/rem: compute integer multiple that the remainder makes with respect to the size of a bin.
                        if rem_low!=0:
                            sub_val_low=rem_low//config.DB_STEP_SIZE
                        else:
                            sub_val_low=0
#                         print('sub_val0',sub_val0)
                        
                        if rem_high!=0:
                            sub_val_high=rem_high//config.DB_STEP_SIZE
                        else:
                            sub_val_high=0    
#                         print('sub_val1',sub_val1)
                        
                        if self.db_selection=='min_db_set':
                            active_color=config.DB_INDICATOR_COLORS[sub_val_low]
                            inactive_color=config.DB_INDICATOR_COLORS[sub_val_high]
                        else:
                            active_color=config.DB_INDICATOR_COLORS[sub_val_high]
                            inactive_color=config.DB_INDICATOR_COLORS[sub_val_low]
                        
                        
                        #Set/scale indicator acording to brightness
                        #and handle which is the marked the active/inactive LEDS
                        active_rgb=(
                            ((active_color[0]*self.brightness)+config.DB_ACTIVE_BRIGHTNESS_BUMP)//255,
                            ((active_color[1]*self.brightness)+config.DB_ACTIVE_BRIGHTNESS_BUMP)//255,
                            ((active_color[2]*self.brightness)+config.DB_ACTIVE_BRIGHTNESS_BUMP)//255,)
                        inactive_rgb=(
                            ((inactive_color[0]*self.brightness)//3)//255,
                            ((inactive_color[1]*self.brightness)//3)//255,
                            ((inactive_color[2]*self.brightness)//3)//255)
                    
                    
                        #draw lowest db setting
                        if (-1*i*config.DB_COARSE_STEP_SIZE <= self.low_db_set_point < -1*(i-1)*config.DB_COARSE_STEP_SIZE):                                
                            if self.db_selection=='min_db_set':
                                await leds.show_rgb(2,i,active_rgb)
                            else:
                                await leds.show_rgb(2,i,inactive_rgb)
                        
                        #draw highest db setting
                        if (-1*i*config.DB_COARSE_STEP_SIZE <= self.max_db_set_point < -1*(i-1)*config.DB_COARSE_STEP_SIZE):
                            #check if there are sub_values in the db setting (sensitive setting)
                            if self.db_selection=='max_db_set':
                               await leds.show_rgb(2,i,active_rgb)
                            else:
                                await leds.show_rgb(2,i,inactive_rgb)
                                
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
              
#             if self.mode=="determiner":
#                 print("total (ms)", total_ms, "mic_sample",ticks_diff(t1,t0), "fft_and_bin: ", ticks_diff(tfft2, tfft1), "determiner: ", ticks_diff(t_determiner1, t_determiner0), "fps:", 1000//total_ms, "delay:", wait_time)
              
#             if self.mode=="Synesthesia":
#                 print("total (ms)", total_ms, "mic_sample",ticks_diff(t1,t0), "fft_and_bin: ", ticks_diff(tfft2, tfft1), "synesthesia: ", ticks_diff(tsyn2, tsyn1), "fps:", 1000//total_ms, "delay:", wait_time)
#             else:
#                 print("total (ms)", total_ms, "mic_sample",ticks_diff(t1,t0), "fft_and_bin: ", ticks_diff(tfft2, tfft1), "Intensity update 0 and buff: ", ticks_diff(tint2, tint1),"Intensity write LEDs: ", ticks_diff(tint3, tint2), "fps:", 1000//total_ms, "delay:", wait_time)
#         
