import asyncio
from mic import Mic
from debug import set_global_exception

async def main():
    set_global_exception()
    m = Mic()
    await asyncio.create_task(m.run())
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()  # Clear retained state
