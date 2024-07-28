from ulab import utils
import math
import asyncio
from leds import Leds
from ulab import numpy as np
from machine import Pin, I2S
from time import ticks_us, ticks_diff

SAMPLE_RATE = 22050 # Hz (WLED is 22050)
SAMPLE_SIZE = 16
SAMPLE_COUNT = 2048 # (WLED is 512)

rawsamples = bytearray(SAMPLE_COUNT * SAMPLE_SIZE // 8)
scratchpad = np.zeros(2 * SAMPLE_COUNT) # re-usable RAM for the calculation of the FFT

ID = 0
SD = Pin(12)
SCK = Pin(13)
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


        async def sum_and_scale(m, f, t):
            #scale = [None if i == 0 else math.sqrt(i)/i for i in range(200)]
            return sum([m[i]/20 for i in range(f,t+1)])# * scale[t-f+1]
            #print(len(m), f, t)
            #return sum([m[i] for i in range(f, t+1)])

        fftCalc = [
            await sum_and_scale(magnitudes,1,2), #  22 -   108 Hz
            await sum_and_scale(magnitudes,3,4), #     -   194 Hz
            await sum_and_scale(magnitudes,5,7), #     -   323 Hz
            await sum_and_scale(magnitudes,8,11), #    -   495 Hz
            await sum_and_scale(magnitudes,12,16), #   -   711 Hz
            await sum_and_scale(magnitudes,17,23), #   -  1012 Hz
            await sum_and_scale(magnitudes,24,33), #   -  1443 Hz
            await sum_and_scale(magnitudes,34,46), #   -  2003 Hz
            await sum_and_scale(magnitudes,47,62), #   -  2692 Hz
            await sum_and_scale(magnitudes,47,52),

            await sum_and_scale(magnitudes,53,62),
            await sum_and_scale(magnitudes,63,70), #   -  3510 Hz
            await sum_and_scale(magnitudes,71,81),
            await sum_and_scale(magnitudes,82,103), #  -  4457 Hz
            await sum_and_scale(magnitudes,104,127), # -  5491 Hz
            await sum_and_scale(magnitudes,128,152), # -  6568 Hz
            await sum_and_scale(magnitudes,153,178), # -  7687 Hz
            await sum_and_scale(magnitudes,179,205), # -  8850 Hz
            await sum_and_scale(magnitudes,206,232), # - 10013 Hz
            await sum_and_scale(magnitudes,206,232), # - 10013 Hz

            await sum_and_scale(magnitudes,233, 300),
            await sum_and_scale(magnitudes,301,400),
            await sum_and_scale(magnitudes,401,500),
            await sum_and_scale(magnitudes,501,600),
            await sum_and_scale(magnitudes,601,700),
            await sum_and_scale(magnitudes,701,800),
            await sum_and_scale(magnitudes,801,900),
            await sum_and_scale(magnitudes,901,1000),
            await sum_and_scale(magnitudes,1001,1100),
            await sum_and_scale(magnitudes,1101,1200),

            await sum_and_scale(magnitudes,1201,1300),
            await sum_and_scale(magnitudes,1301,1400),
            await sum_and_scale(magnitudes,1401,1500),
            await sum_and_scale(magnitudes,1501,1600),
            await sum_and_scale(magnitudes,1601,1700),
            await sum_and_scale(magnitudes,1701,1800),
        ]
        t1 = ticks_us()
        #print(f'mini-wled:  {ticks_diff(t1, t0):6d} µs')

        return fftCalc


    async def start(self):
        leds = Leds()

        while True:
            sreader = asyncio.StreamReader(self.microphone)
            _num_bytes_read = await sreader.readinto(rawsamples)

            if SAMPLE_SIZE == 8:
                samples = np.frombuffer(rawsamples, dtype=np.int8)
            elif SAMPLE_SIZE == 16:
                samples = np.frombuffer(rawsamples, dtype=np.int16)
            else:
                raise NotImplementedError

            # calculate channels from samples
            channels = await self.mini_wled(samples)

            t0 = ticks_us()
            for i in range(0, len(channels)):
                if channels[i] != float("-inf"):
                    if int(channels[i])<=170: #the blue-red part of the hue colour space is at the high end (2^14 to 2^16). if the magnitude is less than (2/3)*255, map to the blue-red zone
                        original_range = [0, 170]
                        target_range = [32768, 65535]
                        hue=np.interp(int(channels[i]),original_range,target_range)[0] #interp gives and array, extract first value
                    else: #the red-yellow part of the hue colour space is at the low end (0 to 2^14). if the magnitude is greater than (2/3)*255, map to the red-yellow zone
                        original_range = [171, 255]
                        target_range = [0, 16320]
                        hue=np.interp(int(channels[i]),original_range,target_range)[0] #interp gives and array, extract first value
                await leds.show_hsv(i, int(hue), int(channels[i])*8, 5)
            t1 = ticks_us()
            #print(f'mic run led write:{ticks_diff(t1, t0):6d} µs')

