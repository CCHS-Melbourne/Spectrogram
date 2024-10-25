import asyncio
from machine import Pin
from mic import Mic
from debug import set_global_exception
from touch import Touch

async def main():
    set_global_exception()
    #touch0 = Touch(Pin(11))
    #touch1 = Touch(Pin(12))
    #touch2 = Touch(Pin(13))
    microphone = Mic()

    await asyncio.gather(microphone.start()) #touch0.start(), touch1.start(), touch2.start())
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()  # Clear retained state
