import asyncio
from machine import Pin
from mic import Mic
from debug import set_global_exception
from touch import Touch
from menu import Menu
import utime

class Watchdog:
    def __init__(self, check_interval_ms=100, alert_threshold_ms=200):
        self.task_heartbeats={}
        self.check_interval_ms=100
        self.alert_threshold_ms=200
    
    def heartbeat(self, taskname):
        now=utime.ticks_ms()
        self.task_heartbeats[taskname]=now
    
        
    async def watch(self):
        """Monitor all registered tasks for starvation"""
        while True:
            await asyncio.sleep_ms(self.check_interval_ms)
            now = utime.ticks_ms()
            
            for task_name, last_heartbeat in self.task_heartbeats.items():
                elapsed = utime.ticks_diff(now, last_heartbeat)
#                 print(f"{task_name} {elapsed}ms")
                if elapsed > self.alert_threshold_ms:
                    print(f"⚠️  {task_name} hasn't run in {elapsed}ms!")


async def main():
    #set_global_exception()
    watchdog = Watchdog() #must be passed to each class object if being used.
    touch0 = Touch(watchdog,Pin(4))
    touch1 = Touch(watchdog,Pin(3))
    touch2 = Touch(watchdog,Pin(2))
    microphone = Mic(watchdog)
    menu = Menu(watchdog,microphone)
    menu.add_touch(touch0)
    menu.add_touch(touch1)
    menu.add_touch(touch2)

    #print("Starting main gather...")
    await asyncio.gather(watchdog.watch(),touch0.start(), touch1.start(), touch2.start(), menu.start(), microphone.start())
    #await asyncio.gather(microphone.start())
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()  # Clear retained state
