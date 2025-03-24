#claude gave me this to start with
import json
from border_calculator import PrecomputedValues

class PrecomputedMenu:
    def __init__(self, filename):
        self.filename = filename
        self.data = {}
        
        self.notes_per_led_options=[1,2,3,4,6,12]
        #get the corresponsing lengths of the corresponding FFT resolution windows
        self.precomputed_borders=PrecomputedValues("test_speedup_redo_values.json")
        self.precomputed_borders.load()
        self.fft_bin_lengths={}
        
        ###this could also just be a json file
        for option in self.notes_per_led_options:
            precomputed_JSON=self.precomputed_borders.get(str(option))
            full_window_len=len(precomputed_JSON)
#             print("notes_per_led option: ", option ,"len full json array: ",len(precomputed_JSON))
            self.fft_bin_lengths[str(option)]=full_window_len
#         print("FFT_bin_lengths: ",self.fft_bin_lengths)
        self.octave_hue_step=900
    
    
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
    #populate json object with a result for each note resolution setting
    for option in self.notes_per_led_options:
        option_len=self.fft_bin_lengths[str(option)]
        result[str(option)]=compute_octave_display(self, option, option_len)
    return result    

def compute_octave_display(self, notes_per_led, menu_length):
    octave_display=[]
    j=0 #need an index decoupled from the loop, or the hue colours change depending on octave resolution
    for i in range(0,menu_length):
        ##calculate hue
        if i%(int(12/notes_per_led))==0:  #the division of 12 is required to scale the right way around, six notes per led should show an octave every two leds, not every six
            octave_display.append(self.octave_hue_step*j)
            j+=1
        else:
            octave_display.append(-1)
    return octave_display

########################################################################
###Run to create JSON file***
# Create instance and save computed values
# storage = PrecomputedMenu('precomputed_octave_display.json')
# storage.compute_and_save(computation)
#####COMMENT OUT WHEN DONE OR WILL HANG AND RERUN WHEN HITTING MAIN#####

# # Later, in another program:
# storage = PrecomputedValues('computed_values.json')
# if storage.load():
#     value = storage.get('50')  # Gets the precomputed value for key '50'
#     print(value)