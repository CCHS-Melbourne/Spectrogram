import asyncio
from time import ticks_ms, ticks_diff

class Menu:
    def __init__(self, mic):
        self.state_changed=False
        self.menu_pix=[[],[],[],[],[],[],[],[],[],[],[],[]]#12 values to fill.
        
        self.main_modes=["Intensity","Synesthesia"]
        self.main_mode_index=0
        self.sub_modes=[['brightness','LEDs_per_px','start_note','decibel_ceiling','hue_select'],['brightness','LEDs_per_px','start_note','decibel_ceiling','hue_select']]
        self.sub_mode_index=0
        self.sub_sub_modes=[['max_db_set','min_db_set'],['max_db_set','min_db_set']]
        self.sub_mode_index=0
        
        self.mic=mic
        self.touches = []
        self.rvs = [0,0,0]
        self.states = [False,False,False]
        self.no_touch = [0,0,0]
        self.no_touch_noise = [0,0,0]
        self.one_touch = [0,0,0]
        self.one_touch_noise = [0,0,0]
        
        self.first_press=True
        self.start_time=ticks_ms()
        
        
        #self.windowflip=1 #reduce number of lines by plotting a sawtooth for the thresholds
            
    def add_touch(self, touch):
        self.touches.append(touch)
        #3print("Added touch.")
#         print("Added touch:", touch.id(self))

#     async def start(self):
#         while True:
#             state=self.touches[0].state
#             print(state)
#             await asyncio.sleep_ms(1000)
    
    def update_main_mode(self):
        self.main_mode_index+=1
        self.main_mode_index%=len(self.main_modes)
        self.sub_mode_index=0
                        
    async def update_value(self, direction):
        if self.sub_modes[self.main_mode_index][self.sub_mode_index]=="brightness":
            current_time=ticks_ms()
            button_held=ticks_diff(current_time,self.start_time,)
            print('button held (ms): ',button_held)
            if button_held <= 1500:
                brightness_step=1
            elif 1500 < button_held <= 3000:
                brightness_step=5
            elif 3000 < button_held <= 4500:
                brightness_step=10
            elif 4500 < button_held:
                brightness_step=20
            print('Brightness step: ',brightness_step)
            
            if direction=="+":
                self.mic.brightness+=brightness_step
                self.mic.menu_update_required=True
                if self.mic.brightness>255:
                    self.mic.brightness=255
            if direction=="-":
                self.mic.brightness-=brightness_step
                self.mic.menu_update_required=True
                if self.mic.brightness<0:
                    self.mic.brightness=0
            
            if direction=="u":
                self.mic.show_menu_in_mic=True
                self.mic.menu_update_required=True
                self.mic.menu_thing_updating="brightness"
                
            #3print("Brightness in menu: ", self.mic.brightness)
        
        elif self.sub_modes[self.main_mode_index][self.sub_mode_index]=="LEDs_per_px":
            
            if direction=="+":
                self.mic.show_menu_in_mic=True
                self.mic.menu_update_required=True
                if self.mic.notes_per_led_index<len(self.mic.notes_per_led_options)-1:
                    self.mic.notes_per_led_index+=1
                    self.mic.notes_per_led=self.mic.notes_per_led_options[self.mic.notes_per_led_index]
                    #3print("Notes per LED: ", self.mic.notes_per_led)
                    
            elif direction=="-":
                self.mic.show_menu_in_mic=True
                self.mic.menu_update_required=True
                if self.mic.notes_per_led_index>=1:
                    self.mic.notes_per_led_index-=1
                    self.mic.notes_per_led=self.mic.notes_per_led_options[self.mic.notes_per_led_index]
                    #3print("Notes per LED: ", self.mic.notes_per_led)

            elif direction=="u":
                #3print("Notes per LED: ", self.mic.notes_per_led)
                self.mic.show_menu_in_mic=True
                self.mic.menu_update_required=True
                self.mic.menu_thing_updating="notes_per_px"            
            return
        
        elif self.sub_modes[self.main_mode_index][self.sub_mode_index]=="start_note":            
            if direction=="+":
                self.mic.start_range_index+=1
                
                if self.mic.start_range_index>=self.mic.full_window_len-self.mic.number_of_octaves: #this check is important for when changing resolutions, adjusting so the user isn't left in a dead spot
                    self.mic.start_range_index=self.mic.full_window_len-self.mic.number_of_octaves
                self.mic.menu_update_required=True

            elif direction=="-":
                self.mic.start_range_index-=1                
                
                if self.mic.start_range_index<=0:
                    self.mic.start_range_index=0
#                 if self.mic.start_range_index<=-self.mic.max_window_overreach:
#                     self.mic.start_range_index=-self.mic.max_window_overreach
                self.mic.menu_update_required=True
                       
            elif direction=="u":
                #tell the menu that an update is required, needed or it will draw every frame.
                self.mic.menu_update_required=True
                #set the menu update required by the mic LED updater
                self.mic.menu_thing_updating="start_range_index"
                            
            #3print("Start range index: ", self.mic.start_range_index)
            return
        
        #Need to make these one general call.
        elif self.sub_modes[self.main_mode_index][self.sub_mode_index]=="decibel_ceiling":
            #3print("tried to change decibel ceiling")
            
            if direction=="+":
                #tell the menu that an update is required, needed or it will draw every frame.
                self.mic.menu_update_required=True
                #set the menu update required by the mic LED updater
                self.mic.menu_thing_updating="highest_db"
                
                if self.mic.max_db_set_point<=-20:
                    self.mic.max_db_set_point+=10
                    print("increased max db range to: ", self.mic.max_db_set_point)
                elif self.mic.max_db_set_point>=-20:
                    print("can't increase maxDB, if this is a concern to your visualization quest, you need to get hearing protection")
                    
            if direction=="-":
                #tell the menu that an update is required, needed or it will draw every frame.
                self.mic.menu_update_required=True
                #set the menu update required by the mic LED updater
                self.mic.menu_thing_updating="highest_db"
                
                if self.mic.max_db_set_point>self.mic.lowest_db+20:
                    self.mic.max_db_set_point-=10
                    print("decreased max db range to: ", self.mic.max_db_set_point)
                elif self.mic.max_db_set_point<=self.mic.lowest_db+20:
                    print("can't decrease below/near to the lowest db, won't decrease range further, you'll lose all resolution")
            
            
            elif direction=="u":
                #tell the menu that an update is required, needed or it will draw every frame.
                self.mic.menu_update_required=True
                #set the menu update required by the mic LED updater
                self.mic.menu_thing_updating="highest_db"
                
                
            return
        
        if self.sub_modes[self.main_mode_index][self.sub_mode_index]=="hue_select":
           
            if direction=="u":
                #3print("Hue select: ")
                #tell the menu that an update is required, needed or it will draw every frame.
                self.mic.menu_update_required=True
                #set the menu update required by the mic LED updater
                self.mic.menu_thing_updating="hue_select"
                #calculate the colours for the given mode, based on some music logic and desired settings
                for index,pix in enumerate(self.menu_pix):
                    self.menu_pix[index]=[24*3*255,255,20]#hue=(yellow in 255 scale)*255(becuase the hue is from 0-65536), saturation full, brightness low
                #pass the mic the image of the menu for the given mode
                self.mic.menu_pix=self.menu_pix
            return
            
    def change_submode(self,direction):
        if direction=="+":
            self.sub_mode_index+=1
            self.sub_mode_index%=len(self.sub_modes[self.main_mode_index])
        elif direction=="-":
            self.sub_mode_index-=1
            self.sub_mode_index%=len(self.sub_modes[self.main_mode_index])
        
        self.sub_mode=self.sub_modes[self.main_mode_index][self.sub_mode_index]
        #3print("Current sub-mode: ",self.sub_mode)
        
    
    async def update_menu(self):
            #check each button combination and perform an action accordingly
            if (self.states==[True,True,True] and self.state_changed!=True):
                #3print("Changing main mode")
                
                self.update_main_mode()
                self.mic.mode=self.main_modes[self.main_mode_index]
                
                #3print("main mode: ", self.main_modes[self.main_mode_index])
                self.state_changed=True
            
            if (self.states==[True,False,False] and self.state_changed!=True):
                #3print("Going up")
                await self.update_value("+")
                if self.first_press==True:
                    self.start_time=ticks_ms()
                    self.first_press=False
                
            if (self.states==[False,True,False] and self.state_changed!=True):
                #3print("Going down")
                await self.update_value("-")
                if self.first_press==True:
                    self.start_time=ticks_ms()
                    self.first_press=False
                
            if (self.states==[True,False,True] and self.state_changed!=True):
                #3print("Next submode")
                self.change_submode("+")
                await self.update_value("u")
                
            if (self.states==[False,True,True] and self.state_changed!=True):
                #3print("Previous submode")
                self.change_submode("-")
                await self.update_value("u")
            
            #Thought about adding more user control to the decibel levels, decided against, one level of menues too far. Just need a better AGC.
#             if (self.states==[False,True,False] and self.state_changed!=True):
#                 self.change_sub_submode()
            
            #toggle the menu on and off
            if (self.states==[True,True,False] and self.state_changed!=True):
                if self.mic.show_menu_in_mic==False:
                    self.mic.show_menu_in_mic=True
                    self.mic.menu_update_required=True  
                elif self.mic.show_menu_in_mic==True:
                    self.mic.show_menu_in_mic=False
                    
                #3print("Menu toggled: ", self.mic.show_menu_in_mic)                 
                    
            if (self.states==[False,False,False]):
                self.state_changed=False
                self.first_press=True
                self.start_time=ticks_ms()
    
    async def start(self):
        while True:
            for index,touch in enumerate(self.touches):                    
                
                self.states[index]=touch.state
                self.rvs[index]=touch.rv
                print("rv0", self.rvs[0], "rv1", self.rvs[1], "rv2", self.rvs[2])
                
#                 self.states[index]=touch.state
#                 self.rvs[index]=touch.rv
#                 self.states[index]=touch.state
#                 self.no_touch[index]=touch.no_touch
#                 self.no_touch_noise[index]=touch.no_touch_noise
#                 self.one_touch[index]=touch.one_touch
#                 self.one_touch_noise[index]=touch.one_touch_noise
#                 
                #I'm performing this operation here because each touch does not have information about the others,
                #also, I'm doing this to be stubborn and figure out how to get the touches calibrating,
                #presently, the touches are set in the touch.py if the rv is greater than the no_touch value + noise
                #Check if the rv corresponds to just one touch (no others activated) and then raise value with filter (what about lowering it, Hank?)
#                 if ((touch.rv > (touch.one_touch + touch.one_touch_noise)) and (self.states[index-1]==False) and (self.states[index-2]==False)):
#                     touch.one_touch=(touch.one_touch*0.65 + touch.rv*0.35) #refine the measurement of the average no_touch value
#                     self.one_touch[index]=touch.one_touch
                

            
#             print("rv0", self.rvs[0], "rv1", self.rvs[1], "rv2", self.rvs[2], "no_touch0", self.no_touch[0],"no_touch1", self.no_touch[1],"no_touch1", self.no_touch[2])
#             print("rv", self.rvs[1],
#                   "no_touch", self.no_touch[1],"no_touch_noise", self.no_touch[1]+(self.no_touch_noise[1]*self.windowflip),
#                   "one_touch", self.one_touch[1],"one_touch_noise", self.one_touch[1]+(self.one_touch_noise[1]*self.windowflip))
#             self.windowflip*=-1



#             print(self.states)
            await self.update_menu()
            #make the menu pause between updates
            await asyncio.sleep_ms(500)
        
        
        
        
        
            
            
            
            
            
            
            
            
            
            
            
            
