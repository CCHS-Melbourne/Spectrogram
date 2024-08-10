import asyncio
from machine import Pin
from mic import Mic
from debug import set_global_exception
from touch import Touch

async def main():
    set_global_exception()
    m = Mic()
    t1 = Touch(Pin(2))
    #t2 = Touch(Pin(?))
    await asyncio.gather(m.start(), t1.start())
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()  # Clear retained state
