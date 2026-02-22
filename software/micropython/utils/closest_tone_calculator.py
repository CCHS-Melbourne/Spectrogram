#this is okay for finding the bins that correspond to a frequency range, but parsing the full bin has issues with bleeding of signal,
#so I am pivoting to a closest tones calculator.
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

class PrecomputedClosestTones:
    def __init__(self, filename):
        self.filename = filename
        self.data = {}
        
        # Calculate the defined frequencies of the musical notes
        #were initialized with 1.,180., maybe important, and yes, it sure was! borked the calculation of the frequencies, amazing
        #start at G#0...
        self.notes=np.arange(0.,87.+1.)# must be a multiple of 12, this range determines how many notes are stored in memory and are accessed by the spectrogram
        self.note_frequencies=TUNING_A4_HZ*(2**((self.notes-49)/12))
#         print(self.note_frequencies)
        
        # Calculate the tones measured by the linear fft used presently
        self.tones=FREQUENCY_RESOLUTION*np.arange(SAMPLE_COUNT/2)
        print(self.tones)
        
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
    
    #init list for storing results
    closest_tones = []
    
    #for each note, find its closest match, and don't loop from the start each time, even if that is fine for precompute
    #skip G0 in favour of A0, so you can see what in the fft tones is closest to the actual frequency
    note_index=1
    tone_index=1
    frequencies_to_match=self.note_frequencies[note_index]
#         print("frequency to match",self.note_frequencies[tone_index])
    
    while tone_index<(len(self.tones)//2)-1 and note_index<len(self.note_frequencies):
        #check if a tone in the tone list is nearest to the actual frequency
        LowHalf=(self.tones[tone_index-1]+self.tones[tone_index])/2
        HighHalf=(self.tones[tone_index]+self.tones[tone_index+1])/2
        interest=self.note_frequencies[note_index]
#             print("Frequency to locate closest tone for:",interest)
        
#             print("low: ", self.tones[tone_index-1], "lowhalf: ", LowHalf, "middle: ", self.tones[tone_index], "highhalf: ", HighHalf, "high", self.tones[tone_index+1])
                   
        if LowHalf <= interest <= HighHalf:
            #found the closest tone for the note of interest
            closest_tones.append(tone_index)
            note_index+=1
            tone_index+=1
        elif interest>LowHalf:
            #tones are below the frequency of interest
            tone_index+=1
        else:
            #the tones are higher than the note, there is no good match for the note in this set of adjacent tones, advance the notes
            note_index+=1
        
    #populate json object with a result for each note resolution setting
    for notes_per_led in self.notes_per_led_options:
        bins=[]
        for i in range(0,len(closest_tones),notes_per_led):
            chunk=closest_tones[i:i+notes_per_led]
            bins.append(chunk)
        result[str(notes_per_led)]=bins          
                    
        print("list of closest tone indexes for ", notes_per_led," notes per LED: ", result[str(notes_per_led)])
        print('\n')
        
    return result
#     
#         for note in self.notes:
#             
#         
#         
#         
#         
#         closest_tones[str(notes_per_led)]=[[crossover_indexes[i],crossover_indexes[i+notes_per_led]] for i in range(0,len(crossover_indexes)-notes_per_led,notes_per_led)]#segment the calculated above list
#         
#         
#         print("list of closes tone indexes for ", notes_per_led," notes per LED: ", closest_tones[str(notes_per_led)])
#         print('\n')
#     return result


#####COMMENT OUT WHEN DONE OR WILL HANG AND RERUN WHEN HITTING MAIN#####
# Create instance and save computed values
# storage = PrecomputedClosestTones('utils/closest_tones.json')
# storage.compute_and_save(computation)
########################################################################

# # Later, in another program:
# storage = PrecomputedValues('computed_values.json')
# if storage.load():
#     value = storage.get('50')  # Gets the precomputed value for key '50'
#     print(value)