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

class PrecomputedValues:
    def __init__(self, filename):
        self.filename = filename
        self.data = {}
        
        # Calculate the defined frequencies of the musical notes
        #were initialized with 1.,180., maybe important, and yes, it sure was! borked the calculation of the frequencies, amazing
        self.notes=np.arange(0.,108.)# must be a multiple of 12, this range determines how many notes are stored in memory and are accessed by the spectrogram
        self.note_frequencies=TUNING_A4_HZ*(2**((self.notes-49)/12))
#         print(self.note_frequencies)
        
        # Calculate the tones measured by the linear fft used presently
        self.tones=FREQUENCY_RESOLUTION*np.arange(SAMPLE_COUNT/2)
        
        # For the basic options inside divisions of 12, make a list
        self.notes_per_led_options=[1,2,3,4,6,12]
        self.length_of_leds=13 #actually needs to be number of leds+1, due to how the note border finding/zipping function organizes borders
        self.start_note=15
    
    
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

# Example usage
def example_computation():
    """Example function to compute some values"""
    result = {}
    # Compute some expensive calculations
    for i in range(100):
        result[str(i)] = i * i
    return result


def computation(self):
    result = {}
    #populate json object with a result for each note resolution setting
    for notes_per_pix in self.notes_per_led_options:
        result[str(notes_per_pix)]=calculate_led_note_borders(self, notes_per_pix)
    return result    

def calculate_led_note_borders(self, notes_per_led):
    # This creates a border exactly on a note. What is needed is a border halfway between one note and the next.
    # I have frequencies, I need to know what note is at the border, index the next note, and take the middle
    #borders=note_frequencies[start_note::notes_per_led]

    #borders=np.zeros(self.length_of_leds) #creates 13 buckets to operate on, which is incorrect, I need all possible buckets at what ever resolution is set
    borders=np.zeros(int(len(self.notes)/notes_per_led))
    print("number of borders in ", notes_per_led, "is: ", len(borders))
    for i in range(len(borders)):
        try:
            #by quirk of indexing, the start index is below the one of actual interest, e.g. G#0 is '0', not A0
            start_=self.note_frequencies[i*notes_per_led]
            next_=self.note_frequencies[(i*notes_per_led)+1]
            border_freq=start_+(next_-start_)/2
            borders[i]=border_freq
        except Exception as e:
            print("Exception: ", e, "for index:", i)
            break
        
    result_fft_bins=calculate_fft_bin_boundaries(self, borders)
    return result_fft_bins
#     return borders #uncomment this and comment out above, to see what the frequency halfway between two notes is, e.g. between G# and A 

def calculate_fft_bin_boundaries(self, borders):
    crossovers = []
    # Loop through the fixed note interval array, finding the index where that boundary is crossed, storing that index and its corresponding frequency in a tuple, appending to a list
    # this is with respect to the mic sampling parameters, again. 
    for i in range(len(self.tones) - 1):
        for boundary in borders:
            if self.tones[i] <= boundary < self.tones[i + 1]:
                crossovers.append((i, self.tones[i]))
    ##print(crossovers)
    self.fft_ranges=[(tup[0],crossovers[i+1][0]-1) for i, tup in enumerate(crossovers[:-1])]  #subtract -1 from the second item in the tuple avoid doubling up values at the seams
    print(self.fft_ranges)
    print(type(self.fft_ranges))
    return(self.fft_ranges)


# Create instance and save computed values
# storage = PrecomputedValues('test_speedup_redo_values.json')
# storage.compute_and_save(computation)
#####COMMENT OUT WHEN DONE OR WILL HANG AND RERUN WHEN HITTING MAIN#####

# # Later, in another program:
# storage = PrecomputedValues('computed_values.json')
# if storage.load():
#     value = storage.get('50')  # Gets the precomputed value for key '50'
#     print(value)