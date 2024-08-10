import asyncio
from machine import Pin
from mic import Mic
from debug import set_global_exception
from touch import Touch

async def main():
    set_global_exception()
    m = Mic()
    t = Touch(Pin(2))
    await asyncio.gather(m.start(), t.start())
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()  # Clear retained state
