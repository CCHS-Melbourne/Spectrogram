#this is all some janky LED controlling code inherited/squashed/stretched into the spectrogram
#the intent is to use this function to map/cycle hues and understand them in the non-fastLED, 65535 not 255 hue space
import uasyncio as asyncio
from leds import Leds
from time import sleep_ms, ticks_ms, ticks_diff

class Hue_Learner:
    def __init__(self):
        print("init")
        self.leds = Leds()
        self.base_hue=0
        self.hue_delta=2000
        self.hue_change_incrm=-500
        self.delay=int(1000/30) #30 FPS    
        self.num_leds=12
        
    async def start(self):
        print("starting")
        while True:
            start_time=ticks_ms()
            
            for j in range(0,3):#for each LED strip
                for i in range(0,self.num_leds):#for each LED on the strip
                    #0-65535 (16bit)
                    #(index1,index2,hue,sat.brightness)
                    
                    await self.leds.show_hsv(j,i,int((self.base_hue+self.hue_delta*i)+(j*self.num_leds*self.hue_delta))%65535,255,5)#j+1 because otherwise the first row would be all one colour
                await self.leds.write(j)
                await asyncio.sleep_ms(0)  # Yield to other tasks
                
            self.base_hue+=self.hue_change_incrm
            exec_time=ticks_diff(ticks_ms(),start_time)
            remaining_delay=max(0,self.delay-exec_time)
#             print("exec_time",exec_time,"remaining_delay",remaining_delay)
            await asyncio.sleep_ms(int(remaining_delay))
            

hue_learner=Hue_Learner()
try:
    asyncio.run(hue_learner.start())
except KeyboardInterrupt:
    print("stopped by user")