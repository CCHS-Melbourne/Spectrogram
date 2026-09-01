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

class PrecomputedBorders:
    def __init__(self, filename):
        self.filename = filename
        self.data = {}
        
        # Calculate the defined frequencies of the musical notes
        #were initialized with 1.,180., maybe important, and yes, it sure was! borked the calculation of the frequencies, amazing
        self.notes=np.arange(1.,87.+1.)# must be a multiple of 12, this range determines how many notes are stored in memory and are accessed by the spectrogram
        self.note_frequencies=TUNING_A4_HZ*(2**((self.notes-49)/12))
#         print(self.note_frequencies)
        
        # Calculate the tones measured by the linear fft used presently
        self.tones=FREQUENCY_RESOLUTION*np.arange(SAMPLE_COUNT/2)
        
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
    
    #find the halfway cross overs , making sure all bins are longer than 1 (not [14,14]), because of how np.sum ommits the last index, and does this: np.sum(values[14:14])=0
    halfways=calculate_led_note_halfways(self)
    
    #crossover_indexes = find_upper_fft_tone_indexes(self.tones,halfways)
    crossover_indexes = [14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25, 26, 28, 29, 31, 33, 35, 37, 39, 42, 44, 47, 49, 52, 55, 58, 62, 66, 69, 74, 78, 83, 87, 93, 98, 104, 110, 116, 123, 131, 138, 147, 155, 165, 174, 185, 196, 207, 219, 232, 246, 261, 276, 293, 310, 329, 348, 369, 391, 414, 438, 464, 492, 521, 552, 585, 620, 657, 696, 737, 781, 827, 876, 928, 984, 1042, 1104, 1170, 1239, 1313, 1391, 1473, 1561, 1654, 1752, 1856, 1967]
    
    #TODO: fix for the specific case of 3 notes per pix. Just added it manually.
    #populate json object with a result for each note resolution setting
    for notes_per_led in self.notes_per_led_options:
        result[str(notes_per_led)]=[[crossover_indexes[i],crossover_indexes[i+notes_per_led]] for i in range(0,len(crossover_indexes)-notes_per_led,notes_per_led)]#segment the calculated above list
        
        # Add the last bin with all remaining elements (thank you sonnet 4.5)
        last_start = (len(crossover_indexes) // notes_per_led) * notes_per_led
        print("last start:", last_start)
        if last_start < len(crossover_indexes):
            print('definitely scooped that last bit')
            result[str(notes_per_led)].append([crossover_indexes[last_start], crossover_indexes[-1]])
        
        print("list of halfway tone indexes for ", notes_per_led," notes per LED: ", result[str(notes_per_led)])
        print('\n')
    return result

def calculate_led_note_halfways(self):
    # This creates a border exactly on a note. What is needed is a border halfway between one note and the next.
    # I have frequencies, I need to know what note is at the border, index the next note, and take the middle

    halfways=np.zeros(len(self.notes)-1)
    
    for i in range(len(halfways)):
        try:
            start_=self.note_frequencies[i]
            next_=self.note_frequencies[i+1]
            
            #find the frequency halfway between the two notes on the border
            border_freq=(start_+next_)/2
            halfways[i]=border_freq
        except Exception as e:
            print("Exception: ", e, "for index:", i)
            break

    return halfways

#search sorted array for the two indexes that have the theoretical halfway points for musical notes. Determine which fft tone is nearest, return the index of that tone.
def find_upper_fft_tone_indexes(tones, note_frequencies):
    upper_tone_indexes=[]
    note_index=0
    for i in range(len(tones)-1):
        try:
            print("frequency: ",note_frequencies[note_index]," bottom match: ",tones[i]," top match: ", tones[i+1])
        except Exception as e:
            print(e)
            break
        
        if (note_frequencies[note_index]<tones[i]):
            upper_match_index=i
            nearest_tone_indexes.append(upper_match_index)
            print("nearest_match",upper_match_index)
            note_index+=1
            
        elif tones[i]<= note_frequencies[note_index] <=tones[i+1]:
            if ((note_frequencies[note_index]-tones[i]))<(tones[i+1]-note_frequencies[note_index]):
                upper_match_index=i+1
            elif ((note_frequencies[note_index]-tones[i]))>(tones[i+1]-note_frequencies[note_index]):
                upper_match_index=i+1
            elif (tones[i]==note_frequencies[note_index]):
                upper_match_index=i+1
            elif (tones[i+1]==note_frequencies[note_index]):
                upper_match_index=i+1
            upper_tone_indexes.append(upper_match_index)
            print("upper_match",upper_match_index)
            note_index+=1
        
    print("upper tone indexes: ",upper_tone_indexes)
    return upper_tone_indexes



# Create instance and save computed values
# storage = PrecomputedBorders('utils/trying for better divisions between A and Asharp.json')
# storage.compute_and_save(computation)
#####COMMENT OUT WHEN DONE OR WILL HANG AND RERUN WHEN HITTING MAIN#####

# # Later, in another program:
# storage = PrecomputedValues('computed_values.json')
# if storage.load():
#     value = storage.get('50')  # Gets the precomputed value for key '50'
#     print(value)