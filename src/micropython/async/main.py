import asyncio
from machine import Pin
from mic import Mic
from touch import Touch
from debug import set_global_exception

async def main():
    set_global_exception()
    m = Mic()
    t = Touch(Pin(2))
    await asyncio.gather(m.start(), t.start())
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()  # Clear retained state
