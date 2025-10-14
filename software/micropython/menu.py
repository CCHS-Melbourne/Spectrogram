import asyncio
from time import ticks_ms, ticks_diff

class Menu:
    def __init__(self, watchdog, mic):
        self.watchdog=watchdog
        
        self.state_changed=False
        self.menu_pix=[[],[],[],[],[],[],[],[],[],[],[],[]]#12 values to fill.
        
        self.main_modes=["Intensity","Synesthesia"]
        self.main_mode_index=0
        self.main_mode=self.main_modes[self.main_mode_index]
        
        
        self.sub_modes=[['brightness','LEDs_per_px','start_note','decibel_ceiling'],['brightness','LEDs_per_px','start_note','decibel_ceiling']] #On the wishlist but not critical path: 'hue_select'
        self.sub_mode_index=0
        self.sub_mode=self.sub_modes[self.main_mode_index][self.sub_mode_index]
        
        #dictionary entries should reflect their sub_mode name, so the sub_mode variable can be recycled/used to efficiently point to the right sub_sub modes
        self.sub_sub_modes={'brightness':[['flat','scaling'],['flat','scaling']],'decibel_ceiling':[['max_db_set','min_db_set'],['max_db_set','min_db_set']]}
        self.sub_sub_mode_index=0
        #actually store the sub_sub_mode for less verbose menue use
        self.sub_sub_mode=self.sub_sub_modes[self.sub_mode][0][0]
        
        self.mic=mic
        self.stored_brightness_index=self.mic.brightness_index
        self.stored_lowest_db_setting=self.mic.lowest_db
        
        self.touches = []
        self.rvs = [0,0,0]
        self.states = [False,False,False]
        self.no_touch = [0,0,0]
        self.no_touch_noise = [0,0,0]
        self.one_touch = [0,0,0]
        self.one_touch_noise = [0,0,0]
        
        self.first_press=True
        self.start_time=ticks_ms()
        self.menu_on_time=0
        
        
        #self.windowflip=1 #reduce number of lines by plotting a sawtooth for the thresholds
            
    def add_touch(self, touch):
        self.touches.append(touch)
        print("Added touch.")
#         print("Added touch:", touch.id(self))

#     async def start(self):
#         while True:
#             state=self.touches[0].state
#             print(state)
#             await asyncio.sleep_ms(1000)
    
    async def update_main_mode(self):
        self.main_mode_index+=1
        self.main_mode_index%=len(self.main_modes)
        
        if self.main_modes[self.main_mode_index]=="Synesthesia":
            #automatically rescale brightness to turn on faint blue LEDs so notes can be differentiated
            self.stored_brightness_index=self.mic.brightness_index
            self.mic.brightness_index=5 #lowest index that shows difference between A, A#, C, C#, ect...
            self.mic.brightness=self.mic.brightnesses[self.mic.brightness_index]
            
            #automatically rescale db range to analyse only the loudest notes - too visually noisy otherwise.
            self.stored_lowest_db_setting=self.mic.lowest_db
            self.mic.auto_low_control=True 
            
        else:
            #return the brightness to the stored/user-selected value for intensity
            self.mic.brightness_index=self.stored_brightness_index
            
            self.mic.auto_low_control=False
            #return the decible range to the previous good-looking/user-set range.
            self.mic.lowest_db=self.stored_lowest_db_setting
            
            
        self.mic.menu_update_required=True
            
            
                        
    async def update_value(self, direction):
        if self.sub_mode=="brightness":
#             current_time=ticks_ms()
#             button_held=ticks_diff(current_time,self.start_time,)
#             print('button held (ms): ',button_held)
#             if button_held <= 1000:
#                 brightness_step=1
#             elif 1000 < button_held <= 2000:
#                 brightness_step=10
#             elif 2000 < button_held:
#                 brightness_step=20
#             print('Brightness step: ',brightness_step)
            
            if direction=="+":
                if self.mic.brightness_index<len(self.mic.brightnesses)-1:
                    self.mic.brightness_index+=1
                self.mic.brightness=self.mic.brightnesses[self.mic.brightness_index]
                self.mic.menu_update_required=True

            if direction=="-":
                if self.mic.brightness_index>=1:
                    self.mic.brightness_index-=1
                self.mic.brightness=self.mic.brightnesses[self.mic.brightness_index]
                self.mic.menu_update_required=True
            
            if direction=="u":
                self.mic.show_menu_in_mic=True
                self.mic.menu_update_required=True
                self.mic.menu_thing_updating="brightness"
                
            print("Brightness in menu: ", self.mic.brightness)
        
        elif self.sub_mode=="LEDs_per_px":
            
            if direction=="+":
                self.mic.show_menu_in_mic=True
                self.mic.menu_update_required=True
                
                
                await self.mic.relocate_start_range_index()
                print("changed resolution, new start range index: ",self.mic.start_range_index)
                
                if self.mic.notes_per_led_index>=1:
                    self.mic.notes_per_led_index-=1
                    self.mic.notes_per_led=self.mic.notes_per_led_options[self.mic.notes_per_led_index]
                    print("Notes per LED: ", self.mic.notes_per_led)

                await self.mic.relocate_start_range_index()
                print("changed resolution (notes/led):", self.mic.notes_per_led, "new start range index: ",self.mic.start_range_index)    

                
            elif direction=="-":
                self.mic.show_menu_in_mic=True
                self.mic.menu_update_required=True
                
                if self.mic.notes_per_led_index<len(self.mic.notes_per_led_options)-1:
                    self.mic.notes_per_led_index+=1
                    self.mic.notes_per_led=self.mic.notes_per_led_options[self.mic.notes_per_led_index]
                    print("Notes per LED: ", self.mic.notes_per_led)
                
                await self.mic.relocate_start_range_index()
                print("changed resolution (notes/led):", self.mic.notes_per_led, "new start range index: ",self.mic.start_range_index)    

            elif direction=="u":
                print("Notes per LED: ", self.mic.notes_per_led)
                self.mic.show_menu_in_mic=True
                self.mic.menu_update_required=True
                self.mic.menu_thing_updating="notes_per_px"            
            return
        
        elif self.sub_mode=="start_note":            
            if direction=="+":
                self.mic.start_range_index+=1
                self.mic.absolute_note_index=self.mic.start_range_index*self.mic.notes_per_led
                print("absolute_note: ",self.mic.absolute_note_index)
                
                #these checks are probably better to do in the ol mic
                if self.mic.start_range_index>=self.mic.full_window_len-self.mic.number_of_octaves: #this check is important for when changing resolutions, adjusting so the user isn't left in a dead spot
                    self.mic.start_range_index=self.mic.full_window_len-self.mic.number_of_octaves
                    self.mic.absolute_note_index=self.mic.start_range_index*self.mic.notes_per_led
                self.mic.menu_update_required=True

            elif direction=="-":
                if self.mic.start_range_index>=1:
                    self.mic.start_range_index-=1
                    self.mic.absolute_note_index-=self.mic.notes_per_led                
                    print("absolute_note: ",self.mic.absolute_note_index)
                    
                if self.mic.start_range_index<=0:
                    self.mic.star_range_index=0
                if self.mic.absolute_note_index<=0:
                    self.mic.abolute_note_index=0
#                 if self.mic.start_range_index<=-self.mic.max_window_overreach:
#                     self.mic.start_range_index=-self.mic.max_window_overreach
                self.mic.menu_update_required=True
                       
            elif direction=="u":
                #tell the menu that an update is required, needed or it will draw every frame.
                self.mic.menu_update_required=True
                #set the menu update required by the mic LED updater
                self.mic.menu_thing_updating="start_range_index"
                            
            print("Start range index: ", self.mic.start_range_index)
            return
        
        #Need to make these one general call.
        elif self.sub_mode=="decibel_ceiling":
            print("tried to change decibel ceiling")
            
            if direction=="+":
                #tell the menu that an update is required, needed or it will draw every frame.
                self.mic.menu_update_required=True
                #set the menu update required by the mic LED updater
                self.mic.menu_thing_updating="highest_db"
                
                if self.mic.db_selection=='max_db_set':
                    #control the movement of the pixel indicating the top of the colourmapping range
                    if self.mic.max_db_set_point<=-20:
                        self.mic.max_db_set_point+=10
                        print("increased max db range to: ", self.mic.max_db_set_point)
                    elif self.mic.max_db_set_point>-20:
                        print("can't increase maxDB, if this is a concern to your visualization quest, you need to get hearing protection")
                else:
                    #control the position of the pixel indicating the bottom of the colourmapping range
                    if self.mic.lowest_db<=self.mic.max_db_set_point-20:
                        self.mic.lowest_db+=10
                        print("increased min db range to: ", self.mic.lowest_db)
                    #make sure the min db value cant get too near to the max db value
                    elif self.mic.lowest_db>self.mic.max_db_set_point-20:
                        print("can't increase/raise to the lowest db, you'll lose all resolution")
                
                
            if direction=="-":
                #tell the menu that an update is required, needed or it will draw every frame.
                self.mic.menu_update_required=True
                #set the menu update required by the mic LED updater
                self.mic.menu_thing_updating="highest_db"
                
                if self.mic.db_selection=='max_db_set':
                    #control the movement of the pixel indicating the top of the colourmapping range
                    if self.mic.max_db_set_point>=self.mic.lowest_db+20:
                        self.mic.max_db_set_point-=10
                        print("decreased max db range to: ", self.mic.max_db_set_point)
                    elif self.mic.max_db_set_point<self.mic.lowest_db+20:
                        print("can't decrease below/near to the lowest db, won't decrease range further, you'll lose all resolution")
                else:
                    #control the position of the pixel indicating the bottom of the colourmapping range
                    if self.mic.lowest_db>=-110:
                        self.mic.lowest_db-=10
                        print("decreased min db range to: ", self.mic.lowest_db)
                    #make sure the min db value cant get too near to the max db value
                    elif self.mic.lowest_db<-110:
                        print("can't lower any further, you'll lose sight of the pixel. If you can hear down here, you must get overstimulated very easily.")                    
            
            
            elif direction=="u":
                #tell the menu that an update is required, needed or it will draw every frame.
                self.mic.menu_update_required=True
                #set the menu update required by the mic LED updater
                self.mic.menu_thing_updating="highest_db"
            
            return	
    
            
    async def change_submode(self,direction):
        if direction=="+":
            self.sub_mode_index+=1
            self.sub_mode_index%=len(self.sub_modes[self.main_mode_index])
        elif direction=="-":
            self.sub_mode_index-=1
            self.sub_mode_index%=len(self.sub_modes[self.main_mode_index])
        
        self.sub_mode=self.sub_modes[self.main_mode_index][self.sub_mode_index]
        print("Current sub-mode: ",self.sub_mode)
        
        return

    async def update_sub_value(self):
        
        if self.sub_mode=="brightness":
            self.mic.brightness_sub_mode=self.sub_sub_mode
            print("brightness submode changed to: ", self.mic.brightness_sub_mode)
            self.mic.menu_update_required=True
            self.mic.show_menu_in_mic=True
        #only change if in the decible select window.
        if self.sub_mode=="decibel_ceiling":
            
            self.mic.db_selection=self.sub_sub_mode
            self.mic.show_menu_in_mic=True
        
        return

    async def change_sub_submode(self):        
        self.sub_sub_mode_index+=1
        self.sub_sub_mode_index%=len(self.sub_sub_modes)
       
        #fetch the sub_sub_modes from a dictionary acording to the main and sub_modes
        self.sub_sub_mode=self.sub_sub_modes[self.sub_mode][self.main_mode_index][self.sub_sub_mode_index]
        print("Current sub-sub-mode: ",self.sub_sub_mode)

    #check button combinations: call setting functions, then call updating functions, which set values/"things_updating" flags in mic 
    async def update_menu(self):
            #check each button combination and perform an action accordingly
            if (self.states==[True,True,True] and self.state_changed!=True):
                self.menu_on_time=ticks_ms()
                print("Changing main mode")
                
                await self.update_main_mode()
                self.mic.mode=self.main_modes[self.main_mode_index]
                
                print("main mode: ", self.main_modes[self.main_mode_index])
                self.state_changed=True
            
            if (self.states==[True,False,False] and self.state_changed!=True):
                self.menu_on_time=ticks_ms()
                print("Going up")
                await self.update_value("+")
                if self.first_press==True:
                    self.start_time=ticks_ms()
                    self.first_press=False
                
            if (self.states==[False,True,False] and self.state_changed!=True):
                self.menu_on_time=ticks_ms()
                print("Going down")
                await self.update_value("-")
                if self.first_press==True:
                    self.start_time=ticks_ms()
                    self.first_press=False
                
            if (self.states==[True,False,True] and self.state_changed!=True and self.first_press==True):
                self.first_press=False
                self.menu_on_time=ticks_ms()
                print("Next submode")
                await self.change_submode("+")
                await self.update_value("u")
                self.mic.show_menu_in_mic=True
                
                
            if (self.states==[False,True,True] and self.state_changed!=True and self.first_press==True):
                self.first_press=False
                self.menu_on_time=ticks_ms()
                print("Previous submode")
                await self.change_submode("-")
                await self.update_value("u")
                self.mic.show_menu_in_mic=True
            
            #Thought about adding more user control to the decibel levels, decided against, one level of menues too far. Just need a better AGC. So built one.
            if (self.states==[False,False,True] and self.state_changed!=True and self.first_press==True):
                self.first_press=False
                self.menu_on_time=ticks_ms()
                print("Toggle sub_sub_mode")
                #update sub_sub_mode
                await self.change_sub_submode()
                #set value flags/"how_things_update" in mic.
                await self.update_sub_value()
                self.mic.show_menu_in_mic=True
            
            #toggle the menu on and off
            if (self.states==[True,True,False] and self.state_changed!=True and self.first_press==True):
                #deactivate the toggle?
                self.first_press=False
                self.menu_on_time=ticks_ms()
                
                if self.mic.show_menu_in_mic==False:
                    self.mic.show_menu_in_mic=True
                    self.mic.menu_update_required=True  
                elif self.mic.show_menu_in_mic==True:
                    self.mic.show_menu_in_mic=False
                
                print("Menu toggled: ", self.mic.show_menu_in_mic)                 
            
            #reset everything if the menu is released.
            if (self.states==[False,False,False]):
                self.state_changed=False
                self.first_press=True
                self.start_time=ticks_ms()
            
            if self.state_changed==False:
                try:
#                     print("checking menu timeout")
                    menu_time_elapsed=ticks_diff(ticks_ms(),self.menu_on_time)
#                     print("Menu time elapsed:", menu_time_elapsed)
                    menu_time_out=10000
                    if menu_time_elapsed>menu_time_out:
                        self.mic.show_menu_in_mic=False
                except Exception as e:
                    print("exception:", e)
                    pass
    
    async def start(self):
        while True:
#             self.watchdog.heartbeat('Menu') #use if you want to be updating and reporting from the menu.
            
            for index,touch in enumerate(self.touches):                    
                self.states[index]=touch.state
                self.rvs[index]=touch.rv
#                 print("rv0", self.rvs[0], "rv1", self.rvs[1], "rv2", self.rvs[2])
                
#             print(self.states)
#             print("rv0", self.rvs[0], "rv1", self.rvs[1], "rv2", self.rvs[2])
            await self.update_menu()
            
            #make the menu pause between updates
            await asyncio.sleep_ms(400)
#             await asyncio.sleep_ms(0)
        
        
        
        
        
            
            
            
            
            
            
            
            
            
            
            
            
