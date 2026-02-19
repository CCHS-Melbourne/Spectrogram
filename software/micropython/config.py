TEST='test'

FLIP_DISPLAY=True #NOT IMPLIMENTED, LOL #True: high freqencies on left, low on the right - False: vice versa

#presets:
size='s' #(s,m,l,c) #small 7px, medium 12px, large 18/24px, c=custom, go wild
color_blind=False #True/False

if size=='s':
    NUM_LEDS = 7
    #'Resolution'=notes_per_LED: [1,2,3,4,6,12]
    BOOT_RESOLUTION_INDEX=5
    
    BOOT_BRIGHTNESS_INDEX=2
    BRIGHTNESS_OPTIONS=[2,6,16,32,64,128,255] #this is semi-independent of the menu width, to make it line up, have the same number of entries as the menu size. If you go outside the menu size, the top brightness pixel isn't displayed.
    #two hours of manual fitting by eye and this was the screamingly obvious final outcome: for 7 pixels=[4,8,16,32,64,128,255] I modified the low blues to get that "blue LED not on anymore" vibe
    #[2,7,28,64,113,177,255] for 7 pixels, calculated as a square relationship increase in brightness (doesn't look good though lol)
    
    
if size=='m':
    #goal: make this arbitrarily small/long & accurately reflected in setting. No funny +1 business.
    NUM_LEDS = 12 #50 #actually needs to be number of leds+1# ugly work around for array out of bound error caused by ring buffer in mic.py(??)
    #'Resolution'=notes_per_LED: [1,2,3,4,6,12]
    BOOT_RESOLUTION_INDEX=4
    BOOT_BRIGHTNESS_INDEX=4
    BRIGHTNESS_OPTIONS=[1,2,3,4,5,9,16,27,48,83,146,255]
    #for 12 pixels, i guessed/input:[2,3,4,5,7,10,20,35,50,90,160,255]. The above is a modified fitted curve: 1.75^index, normalized to 255




#configure touch thresholds:
UNPRESSED_CAPACITIVE_READING=80000
PRESSED_CAPACITIVE_READING=90000
#print out the touch levels and compare to the below thresholds. 
PRINT_TOUCH_READING=False

#these are the hues the maker selected for the 12 notes of an octave, you can change them :)
import colour_lut_builder as clb  
if color_blind==True:
    #viridis for replacing intensity for color blind folks:
    INTENSITY_COLOR_LUT=clb.generalised_color_lut([(0,0,0),(0,0,255),(0,255,0),(255,255,0)],[0,63,191,255],256,1)
    #plasma note scheme 
    SYN_NOTE_HUES=clb.generalised_color_lut([(0,0,255),(255,0,0),(255,255,0),(255,255,255)],[0,63,211,255],256,22)
    
    #Bunch of tests: you can go crazy trying to pick colours, particularly when you can't 'see' them.
    #scheme build call for plasma synesthesia
    #plasma0: missing the white top end, which will allow better determination
    #clb.generalised_color_lut([(0,0,255),(255,0,0),(255,255,0)],[0,170,255],256,20)
    #plasma1: missing the white top end, which will allow better determination. White further fits in with the perceptual brightness angle of these colour schemes
    #clb.generalised_color_lut([(0,0,255),(255,0,0),(255,255,0),(255,255,255)],[0,63,191,255],256,20)
    #plasma2: yellows not distinct: moving stops. Yellow ususally a small end band
    #clb.generalised_color_lut([(0,0,255),(255,0,0),(255,255,0),(255,255,255)],[0,63,211,255],256,22)
    #plasma3 adding green denuemont to white, to move closer to blue/a cyclical clour scheme
    #clb.generalised_color_lut([(0,0,255),(255,0,0),(255,255,0),(255,255,255),(0,255,0)],[0,60,120,180,255],256,22)
    #plasma4 still messing 
    #clb.generalised_color_lut([(0,0,255),(255,0,0),(255,255,0),(255,255,255),(0,255,0),(0,255,255)],[0,60,120,150,200,255],256,22)
    #plasma5: just adding sharps manually. 256/7=36.57
    #clb.generalised_color_lut([(0,0,255),(255,0,0),(255,255,0),(255,255,255)],[0,63,211,255],256,36)
    #which yeilds: [(0, 0, 255), (145, 0, 109), (255, 15, 0), (255, 77, 0), (255, 139, 0), (255, 201, 0), (255, 255, 28), (255, 255, 237)]

else:
    #plama scheme
    INTENSITY_COLOR_LUT=clb.generalised_color_lut([(0,0,255),(255,0,0),(255,255,0)],[0,170,255],256,1)
    #rainbow note scheme - manually selected
    SYN_NOTE_HUES=[(255,0,0),(255,30,30),(255,60,0),(255,255,0),(255,255,30),(0,255,0),(80,220,10),(0,155,255),(0,0,255),(50,0,255),(255,0,255),(255,255,255)]

DEV_STATUS_LED_PIN=21

#pipedream
HALVED_MIRRORED_SPECTRUM=False
MIRROR_START_INDEX=NUM_LEDS/2

#Colour selections:


#this can be used to change the direction of the waterfall. Depends on one's prefered viewing angle Normally pin0=6,pin1=8,pin2=7
LEDS_PIN0 = 6
LEDS_PIN1 = 8
LEDS_PIN2 = 7

ID = 0 #I2S identity
#mic pins
SD = 11
SCK = 10
WS = 9

#Boot visualisation settings/options:

#integer multiples of 10: logic/resolution is set in menu.py
BOOT_MAX_DB=-40
BOOT_MIN_DB=-80


#menu display stuff
MENU_LED_OFFSET=0 #useful for (e.g.) 18 or 24 wide menus that only want 12 pixel wide displays
MENU_SIZE=NUM_LEDS-MENU_LED_OFFSET-1 #or face crash #counting from zero... LEDS are indexed from 0... #ideally should be tied to LEDS-1
MENU_SCALE=1 #not used?? useful for crunching down the menu's size (1 pixel=?, 6pixels=0.5, 12pixels=1



DB_RANGE=120
DB_STEP_SIZE=5#[10db, 5db, 1db]
from math import ceil
DB_SETTINGS_PER_BIN=s if (s := ceil((DB_RANGE/DB_STEP_SIZE)/NUM_LEDS)) <= NUM_LEDS else None #walrus operator, lol
DB_COARSE_STEP_SIZE=DB_STEP_SIZE*DB_SETTINGS_PER_BIN

DB_ACTIVE_BRIGHTNESS_BUMP=100 #indicate active status with brightness, not colour

print("DB_SETTINGS_PER_BIN",DB_SETTINGS_PER_BIN)
#helpful if the stepsize is a muliple of the settings_per_bin. Or just use //
if DB_SETTINGS_PER_BIN>1:
    if color_blind==True:
        DB_INDICATOR_COLORS=clb.generalised_color_lut([(255,255,000),(000,255,000),],[0,255],256,256//(DB_SETTINGS_PER_BIN-1)) #-1 is for coarser steps to get full range mapped #shades of yellow/green
    else:
        DB_INDICATOR_COLORS=clb.generalised_color_lut([(255,255,000),(000,255,000),],[0,255],256,256//(DB_SETTINGS_PER_BIN-1)) #-1 is for coarser steps to get full range mapped #shades of yellow/green    
    print(DB_INDICATOR_COLORS)
else:
    if color_blind==True:
        DB_INDICATOR_COLORS=[(255,000,000)] #active=red - stands out from blue.
        pass
    else:
        DB_INDICATOR_COLORS=[(000,255,000)] #active=green
        

