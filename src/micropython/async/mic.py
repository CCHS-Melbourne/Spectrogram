from ulab import utils
import math
import asyncio
from leds import Leds
from ulab import numpy as np
from machine import Pin, I2S
from time import ticks_us, ticks_diff

SAMPLE_RATE = 16000 # Hz
SAMPLE_SIZE = 16
SAMPLE_COUNT = 512

rawsamples = bytearray(SAMPLE_COUNT * SAMPLE_SIZE // 8)
scratchpad = np.zeros(2 * SAMPLE_COUNT) # re-usable RAM for the calculation of the FFT

ID = 0
SD = Pin(15)
SCK = Pin(16)
WS = Pin(17)

class Mic():
    def __init__(self):
        self.microphone = I2S(ID, sck=SCK, ws=WS, sd=SD, mode=I2S.RX,
                              bits=SAMPLE_SIZE, format=I2S.MONO, rate=SAMPLE_RATE,
                              #ibuf=len(rawsamples)*10+1024) # FIXME: Just set it to 40000 as the example sketch?
                              ibuf=8000)


    # FIXME: Needs thorough review and optimization, way too slow with 12*3 LEDs as-is
    async def mini_wled(self, samples):
        t0 = ticks_us()
        assert (len(samples) == SAMPLE_COUNT)

        tfft0 = ticks_us()
        magnitudes = utils.spectrogram(samples, scratchpad=scratchpad, log=True)
        tfft1 = ticks_us()
        #print(f'spectrogram:{ticks_diff(tfft1, tfft0):6d} µs')


        def sum_and_scale(m, f, t):
            return sum([m[i]/20 for i in range(f,t+1)])# * scale[t-f+1]

        fft_ranges = [
            (1, 2), (3, 4), (5, 7), (8, 11), (12, 16), (17, 23), (24, 33), 
            (34, 46), (47, 62), (47, 52), (53, 62), (63, 70), (71, 81), 
            (82, 103), (104, 127), (128, 152), (153, 178), (179, 205), 
            (206, 232), (206, 232), (233, 300), (301, 400), (401, 500), 
            #(501, 600), (601, 700), (701, 800), (801, 900), (901, 1000), 
            # (1001, 1100), (1101, 1200), (1201, 1300), (1301, 1400), 
            #(1401, 1500), (1501, 1600), (1601, 1700), (1701, 1800)
        ]

        t1 = ticks_us()
        fftCalc = [sum_and_scale(magnitudes, f, t) for f, t in fft_ranges]
        #print(f'mini-wled:  {ticks_diff(t1, t0):6d} µs')

        return fftCalc


    async def start(self):
        leds = Leds()

        while True:
            await asyncio.StreamReader(self.microphone).readinto(rawsamples)
            samples = np.frombuffer(rawsamples, dtype=np.int16)

            # calculate channels from samples
            channels = await self.mini_wled(samples)

            t0 = ticks_us()
            for i, led in enumerate(channels):
                if led != float("-inf"): # TODO: Filter upstream, getting too many here.
                    led = int(led)
                    if led<=170: #the blue-red part of the hue colour space is at the high end (2^14 to 2^16). if the magnitude is less than (2/3)*255, map to the blue-red zone
                        original_range = [0, 170]
                        target_range = [32768, 65535]
                        hue=np.interp(led,original_range,target_range)[0] #interp gives and array, extract first value
                    else: #the red-yellow part of the hue colour space is at the low end (0 to 2^14). if the magnitude is greater than (2/3)*255, map to the red-yellow zone
                        original_range = [171, 255]
                        target_range = [0, 16320]
                        hue=np.interp(led,original_range,target_range)[0] #interp gives and array, extract first value
                    #print(i, led)
                    await leds.show_hsv(i, int(hue), int(led)*20, 5)
            t1 = ticks_us()
            print(f'mic run led write:{ticks_diff(t1, t0):6d} µs')
