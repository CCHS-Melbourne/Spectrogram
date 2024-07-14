import asyncio

class Leds():
    def __iter__(self):
        return 42

async def light():
    leds = Leds()
    print('waiting for leds')
    res = await leds  # Retrieve result
    print('done', res)

asyncio.run(light())
