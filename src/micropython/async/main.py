import asyncio
from machine import Pin
from mic import Mic
from debug import set_global_exception
from touch import Touch

async def main():
    set_global_exception()
    touch0 = Touch(Pin(2))
    #touch1 = Touch(Pin(?))
    m = Mic()

    await asyncio.gather(m.start(), touch0.start())
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()  # Clear retained state
