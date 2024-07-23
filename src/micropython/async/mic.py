from ulab import utils as utils
SAMPLE_COUNT = 512 # (WLED is 512)

rawsamples = bytearray(SAMPLE_COUNT * SAMPLE_SIZE // 8)

ID = 0
SD = Pin(5)
SCK = Pin(2)
WS = Pin(4)

UNPOWER, MINPEAK = lambda x: math.pow(x,1/2), None

class Mic():
    def __init__(self):
        self.microphone = I2S(ID, sck=SCK, ws=WS, sd=SD, mode=I2S.RX,
                              bits=SAMPLE_SIZE, format=I2S.MONO, rate=SAMPLE_RATE,
                              #ibuf=len(rawsamples)*10+1024) # FIXME: Just set it to 40000 as the example sketch?
                              ibuf=8000)


    async def mini_wled(self, samples):
        assert (len(samples) == SAMPLE_COUNT)
        
        magnitudes = utils.spectrogram(samples)

        async def sum_and_scale(m, f, t):
            scale = [None if i == 0 else math.sqrt(i)/i for i in range(30)]
            return sum([m[i] for i in range(f,t+1)]) * scale[t-f+1]
        
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
            await sum_and_scale(magnitudes,63,81), #   -  3510 Hz
            await sum_and_scale(magnitudes,82,103), #  -  4457 Hz
            await sum_and_scale(magnitudes,104,127), # -  5491 Hz
            await sum_and_scale(magnitudes,128,152), # -  6568 Hz
            await sum_and_scale(magnitudes,153,178), # -  7687 Hz
            await sum_and_scale(magnitudes,179,205), # -  8850 Hz
            await sum_and_scale(magnitudes,206,232), # - 10013 Hz
        ]

        #print(fftCalc)
        return fftCalc


    async def run(self):
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

            channels = [UNPOWER(channels[i]) if channels[i] >= 1 else 0 for i in range(len(channels))]
            for i in range(0, 15):
                await leds.show_hsv(i, 1, 1, int(channels[i]))
