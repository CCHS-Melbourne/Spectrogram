import asyncio
from mic import Mic
from leds import Leds
from debug import set_global_exception

async def main():
    set_global_exception()
    m = Mic()
    l = Leds()
    await asyncio.create_task(m.run())
    #await asyncio.create_task(l.dance())
    # for i in range(65550):
    #     for le in range(15):
    #         await asyncio.create_task(l.show_hsv(le, 1, 1, i+100))
    #     #await asyncio.sleep_ms(10)
    # await leds.run_forever()  # Non-terminating method
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()  # Clear retained state
