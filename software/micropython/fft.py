import config
import asyncio
from ulab import numpy as np
from ulab import utils as utils

#finally time for the Hann window, like a year and a half later:
window = np.array([0.5 - 0.5 * np.cos(2 * np.pi * i / (config.SAMPLE_COUNT - 1)) for i in range(config.SAMPLE_COUNT)])

class Fft():
    async def test(self):
        x = np.linspace(0, 10, num=1024)
        y = np.sin(x)

        a = utils.spectrogram(y)

        print('original vector:\n', y)
        print('\nspectrum:\n', a)
        
    async def crunch(self,samples):   
        #apply Hann window
        windowed_samples = samples * window
        magnitudes = utils.spectrogram(windowed_samples)
        return magnitudes
        await asyncio.sleep_ms(wait_time)