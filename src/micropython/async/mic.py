import fft
import math
from leds import Leds
from ulab import numpy as np
from machine import Pin, I2S

SAMPLE_RATE = 22050 # Hz (WLED is 22050)
SAMPLE_SIZE = 16
SAMPLE_COUNT = 512 # (WLED is 512)
rawsamples = bytearray(SAMPLE_COUNT * SAMPLE_SIZE // 8)

ID = 0
SD = Pin(5)
SCK = Pin(2)
WS = Pin(4)

class Mic():
    def __init__(self):
        #>>> m = mic.Mic()
        #E (37838) i2s_common: i2s_new_channel(867): there should be at least 2 DMA buffers
        #E (37848) i2s_std: i2s_channel_init_std_mode(204): input parameter 'handle' is NULL
        #E (37848) i2s_common: i2s_channel_register_event_callback(316): input parameter 'handle' is NULL
        #E (37858) i2s_common: i2s_channel_enable(1077): input parameter 'handle' is NULL
        self.microphone = I2S(ID, sck=SCK, ws=WS, sd=SD, mode=I2S.RX,
                     bits=SAMPLE_SIZE, format=I2S.MONO, rate=SAMPLE_RATE,
                     ibuf=len(rawsamples)*2+1024)

        # Set a callback. ``handler`` is called when ``buf`` is emptied (``write`` method) or becomes full (``readinto`` method).  
        # Setting a callback changes the ``write`` and ``readinto`` methods to non-blocking operation.
        # ``handler`` is called in the context of the MicroPython scheduler.
        self.microphone.irq(self.i2s_handler)
        self.microphone.start()

    def flat_top_window(N):
        n = np.linspace(0, N, num=N)
        return 0.2810639 - (0.5208972 * np.cos(2 * math.pi * n/N)) + (0.1980399 * np.cos(4 * math.pi * n/N))

    def mini_wled(self, samples):
        assert (len(samples) == SAMPLE_COUNT)

        # TODO: These two lines can be substituted by ulab's utils.spectrogram() ?
        re, im = np.fft.fft(samples * self.flat_top_window(SAMPLE_COUNT))
        magnitudes = np.sqrt(re*re + im*im)
        
        
        def sum_and_scale(m, f, t):
            scale = [None if i == 0 else math.sqrt(i)/i for i in range(30)]
            return sum([m[i] for i in range(f,t+1)]) * scale[t-f+1]
        
        fftCalc = [
            sum_and_scale(magnitudes,1,2), #  22 -   108 Hz
            sum_and_scale(magnitudes,3,4), #     -   194 Hz
            sum_and_scale(magnitudes,5,7), #     -   323 Hz
            sum_and_scale(magnitudes,8,11), #    -   495 Hz
            sum_and_scale(magnitudes,12,16), #   -   711 Hz
            sum_and_scale(magnitudes,17,23), #   -  1012 Hz
            sum_and_scale(magnitudes,24,33), #   -  1443 Hz
            sum_and_scale(magnitudes,34,46), #   -  2003 Hz
            
            sum_and_scale(magnitudes,47,62), #   -  2692 Hz
            sum_and_scale(magnitudes,63,81), #   -  3510 Hz
            sum_and_scale(magnitudes,82,103), #  -  4457 Hz
            sum_and_scale(magnitudes,104,127), # -  5491 Hz
            sum_and_scale(magnitudes,128,152), # -  6568 Hz
            sum_and_scale(magnitudes,153,178), # -  7687 Hz
            sum_and_scale(magnitudes,179,205), # -  8850 Hz
            sum_and_scale(magnitudes,206,232), # - 10013 Hz
        ]
        
        return fftCalc

    async def i2s_handler():
        '''
        What to do when buf is emptied or becomes full?
        '''
        print("I2S event occurred")


    async def run(self):
        led_array = Leds()

        # https://docs.micropython.org/en/latest/library/machine.I2S.html#class-i2s-inter-ic-sound-bus-protocol
        #     
        # swriter = asyncio.StreamWriter(audio_out)
        # swriter.write(buf)
        # await swriter.drain()

        num_bytes_read = await self.microphone.readinto(rawsamples)

        assert (num_bytes_read == len(rawsamples))

        if SAMPLE_SIZE == 8:
            samples = np.frombuffer(rawsamples, dtype=np.int8)
        elif SAMPLE_SIZE == 16:
            samples = np.frombuffer(rawsamples, dtype=np.int16)
        else:
            raise NotImplementedError

        # calculate channels from samples
        channels = self.mini_wled(samples)
        print(channels)