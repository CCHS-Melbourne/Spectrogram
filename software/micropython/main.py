import asyncio
from machine import Pin
from mic import Mic
from debug import set_global_exception
from touch import Touch
from menu import Menu

async def main():
    #set_global_exception()
    touch0 = Touch(Pin(4))
    touch1 = Touch(Pin(3))
    touch2 = Touch(Pin(2))
    microphone = Mic()
    menu = Menu(microphone)
    menu.add_touch(touch0)
    menu.add_touch(touch1)
    menu.add_touch(touch2)

    #print("Starting main gather...")
    await asyncio.gather(touch0.start(), touch1.start(), touch2.start(), menu.start(), microphone.start())
    #await asyncio.gather(microphone.start())
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()  # Clear retained state
