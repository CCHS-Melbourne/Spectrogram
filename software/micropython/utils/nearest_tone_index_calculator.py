#claude gave me this to start with
import json

import math
from ulab import numpy as np

#these parameters determine the resolution of the fft
SAMPLE_RATE = 8000 # Hz
SAMPLE_SIZE = 16
SAMPLE_COUNT = 4096 #8192 #
FREQUENCY_RESOLUTION=SAMPLE_RATE/SAMPLE_COUNT
TUNING_A4_HZ=440.
BINS_PER_OCTAVE=2

class PrecomputedNearestTones:
    def __init__(self, filename):
        self.filename = filename
        self.data = {}
        
        # Calculate the defined frequencies of the musical notes
        #were initialized with 1.,180., maybe important, and yes, it sure was! borked the calculation of the frequencies, amazing
        self.notes=np.arange(1,87+1)# must be a multiple of 12?, this range determines how many notes are stored in memory and are accessed by the spectrogram
        self.note_frequencies=TUNING_A4_HZ*(2**((self.notes-49)/12))
        print("notes:",self.note_frequencies)
        print(len(self.notes))
        
        
        # Calculate the tones measured by the linear fft used presently
        self.tones=FREQUENCY_RESOLUTION*np.arange(SAMPLE_COUNT//2)
        print("tones:",self.tones)
#         print(self.note_frequencies)
        
                
        # For the basic options inside divisions of 12, make a list
        self.notes_per_led_options=[1,2,3,4,6,12]
        self.length_of_leds=13 #actually needs to be number of leds+1, due to how the note border finding/zipping function organizes halfways
        self.start_note=13 #A1, 55Hz
    
    
    def compute_and_save(self, compute_function):
        """
        Compute values using the provided function and save to file
        compute_function should return a dictionary of computed values
        """
        self.data = compute_function(self)
        
        # Save to file
        with open(self.filename, 'w') as f:
            json.dump(self.data, f)
    
    def load(self):
        """Load precomputed values from file"""
        try:
            with open(self.filename, 'r') as f:
                self.data = json.load(f)
            return True
        except OSError:
            print(f"No precomputed values file found at {self.filename}")
            return False
    
    def get(self, key, default=None):
        """Get a value by key"""
        #return self.data.get(key, default)
#         print(self.data.get(key))
        return self.data.get(key)


def computation(self):
    result = {}
    #find the nearest fft tone's index for all desired notes:
    nearest_tone_indexes=find_nearest_fft_tone_indexes(self.tones,self.note_frequencies)
    
    #segment nearest tones per notes_per_led options.  
    #populate json object with a result for each note resolution setting
    for notes_per_led in self.notes_per_led_options:
        result[str(notes_per_led)]=[nearest_tone_indexes[i:i+notes_per_led] for i in range(0,len(self.note_frequencies),notes_per_led)]#segment the calculated above list
        print("list of note indexes for ", notes_per_led," notes per LED: ", result[str(notes_per_led)])

    return result    

#search sorted array for the two indexes that have the theoretical musical note between them. Determine which fft tone is nearest, return the index of that tone.
def find_nearest_fft_tone_indexes(tones, note_frequencies):
    nearest_tone_indexes=[]
    note_index=0
    for i in range(len(tones)-1):
        print("frequency: ",note_frequencies[note_index]," bottom match: ",tones[i]," top match: ", tones[i+1])
        
        if (note_frequencies[note_index]<tones[i]):
            closest_match_index=i
            nearest_tone_indexes.append(closest_match_index)
            print("nearest_match",closest_match_index)
            note_index+=1
            
        elif tones[i]<= note_frequencies[note_index] <=tones[i+1]:
            if ((note_frequencies[note_index]-tones[i]))<(tones[i+1]-note_frequencies[note_index]):
                closest_match_index=i
            elif ((note_frequencies[note_index]-tones[i]))>(tones[i+1]-note_frequencies[note_index]):
                closest_match_index=i+1
            elif (tones[i]==note_frequencies[note_index]):
                closest_match_index=i
            elif (tones[i+1]==note_frequencies[note_index]):
                closest_match_index=i+1
            nearest_tone_indexes.append(closest_match_index)
            print("nearest_match",closest_match_index)
            note_index+=1
        
    print("nearest tone indexes: ",nearest_tone_indexes)
    return nearest_tone_indexes

    
# Create instance and save computed values
storage = PrecomputedNearestTones('utils/binned_indexes_of_tones_nearest_to_musical_notes.json')
storage.compute_and_save(computation)
#####COMMENT OUT WHEN DONE OR WILL HANG AND RERUN WHEN HITTING MAIN#####

# # Later, in another program:
# storage = PrecomputedValues('computed_values.json')
# if storage.load():
#     value = storage.get('50')  # Gets the precomputed value for key '50'
#     print(value)