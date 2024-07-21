import asyncio
from mic import Mic
from leds import Leds
from debug import set_global_exception

async def main():
    set_global_exception()
    m = Mic()
    l = Leds()
    #await asyncio.create_task(m.run())
    #await asyncio.create_task(l.dance())
    await asyncio.create_task(l.colorHSV(10000, 10, 1))
    # await leds.run_forever()  # Non-terminating method
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()  # Clear retained state