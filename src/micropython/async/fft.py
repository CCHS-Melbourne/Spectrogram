from ulab import numpy as np
from ulab import utils as utils

class Fft():
    async def test():
        x = np.linspace(0, 10, num=1024)
        y = np.sin(x)

        a = utils.spectrogram(y)

        print('original vector:\n', y)
        print('\nspectrum:\n', a)