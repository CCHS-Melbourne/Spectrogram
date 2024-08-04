from ulab import utils
import math
import asyncio
from leds import Leds
from ulab import numpy as np
from machine import Pin, I2S
from time import ticks_us, ticks_diff

SAMPLE_RATE = 16000 # Hz
SAMPLE_SIZE = 16
SAMPLE_COUNT = 2048

rawsamples = bytearray(SAMPLE_COUNT * SAMPLE_SIZE // 8)
scratchpad = np.zeros(2 * SAMPLE_COUNT) # re-usable RAM for the calculation of the FFT
                                        # avoids memory fragmentation and thus OOM errors

ID = 0
SD = Pin(15)
SCK = Pin(16)
WS = Pin(17)

class Mic():
    def __init__(self):
        self.microphone = I2S(ID, sck=SCK, ws=WS, sd=SD, mode=I2S.RX,
                              bits=SAMPLE_SIZE, format=I2S.MONO, rate=SAMPLE_RATE,
                              ibuf=4096)


    # FIXME: Needs thorough review and optimization, way too slow with 12*3 LEDs as-is
    async def mini_wled(self, samples):
        t0 = ticks_us()

        tfft0 = ticks_us()
        magnitudes = utils.spectrogram(samples, scratchpad=scratchpad)#, log=True)
        #magnitudes = utils.spectrogram(samples)
        tfft1 = ticks_us()
        #print(f'spectrogram:{ticks_diff(tfft1, tfft0):6d} µs')

        fft_ranges = [
            (1, 2), (3, 4), (5, 7), (8, 11), (12, 16), (17, 23), (24, 33), 
            (34, 46), (47, 62), (47, 52), (53, 62), (63, 70), (71, 81), 
            (82, 103), (104, 127), (128, 152), (153, 178), (179, 205), 
            (206, 232), (206, 232), (233, 300), (301, 400), (401, 500), 
            (501, 600), (601, 700), (701, 800), (801, 900), (901, 1000), 
            (1001, 1100), (1101, 1200), (1201, 1300), (1301, 1400), 
            (1401, 1500), (1501, 1600), (1601, 1700), (1701, 1800)
        ]

        t1 = ticks_us()

        tsc0 = ticks_us()
        fftCalc = [np.sum(magnitudes[f:t+1]) for f, t in fft_ranges]
        tsc1 = ticks_us()
        #print(f'sum_and_scale:{ticks_diff(tsc1, tsc0):6d} µs')

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

            # Assuming channels is a numpy array
            leds_array = np.array(channels)

            # Create masks for different hue ranges
            mask_blue_red = leds_array <= 170
            mask_red_yellow = leds_array > 170

            # Define ranges and target mappings
            original_range_blue_red = np.array([0, 170])
            target_range_blue_red = np.array([32768, 65535])
            original_range_red_yellow = np.array([171, 255])
            target_range_red_yellow = np.array([0, 16320])

            # Interpolate for hues
            hue_blue_red = np.interp(leds_array[mask_blue_red], original_range_blue_red, target_range_blue_red)
            hue_red_yellow = np.interp(leds_array[mask_red_yellow], original_range_red_yellow, target_range_red_yellow)

            # Combine hue results
            hues = np.where(mask_blue_red, hue_blue_red, hue_red_yellow)

            # Calculate value based on LED
            values = np.where(leds_array != float("-inf"), np.clip(leds_array / 200, 0, 255), 0)

            # Prepare indices and valid LEDs
            indices = np.arange(len(channels))

            # Filter out invalid LEDs
            valid_indices = leds_array != float("-inf")

            # Use async to call show_hsv for valid LEDs
            for i, hue, value in zip(indices[valid_indices], hues[valid_indices], values[valid_indices]):
                await leds.show_hsv(i, int(hue), int(value), int(value/10))

            t1 = ticks_us()
            print(f'mic run led write:{ticks_diff(t1, t0):6d} µs')
