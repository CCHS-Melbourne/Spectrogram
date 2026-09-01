import config
import asyncio
from machine import Pin, I2S
from ulab import numpy as np


SAMPLE_RATE = config.SAMPLE_RATE # Hz
SAMPLE_SIZE = config.SAMPLE_SIZE
SAMPLE_COUNT = config.SAMPLE_COUNT #8192 #


# Size of the I2S DMA buffer, the smaller this is then the
# faster each loop iteration can update the LEDs

I2S_SAMPLE_COUNT = config.I2S_SAMPLE_COUNT
I2S_SAMPLE_BYTES = I2S_SAMPLE_COUNT * SAMPLE_SIZE // 8

# Code below assumes the I2S buffer size is an exact multiple of the sample count
assert(SAMPLE_COUNT % I2S_SAMPLE_COUNT == 0)

# Tuning:
#
# - The smaller SAMPLE_COUNT is then the more quickly responsive the LEDs will
#   be. Limit will be a minimum buffer size before the FFT results don't work
#   (TODO: calculate this?)
#
# - The smaller I2S_SAMPLE_COUNT then the higher the update rate for the LEDs so
#   they'll look less jittery. Limit will be a minimum where the CPU can't
#   keep up (because need to perform FFT on full SAMPLE_COUNT for each iteration.)


                                        
ID = 0 #I2S identity
SD = Pin(config.SD)
SCK = Pin(config.SCK)
WS = Pin(config.WS)

class AudioSampler():
    def __init__(self):
        self.microphone = I2S(ID, sck=SCK, ws=WS, sd=SD, mode=I2S.RX,
                                bits=SAMPLE_SIZE, format=I2S.MONO, rate=SAMPLE_RATE,
                                ibuf=I2S_SAMPLE_BYTES)
        
        self.flag = asyncio.ThreadSafeFlag()

        # Define the callback for the IRQ that sets the flag
        def irq_handler(noop):
            self.flag.set()

        # Attach the IRQ handler
        self.microphone.irq(irq_handler)
        
        self.samples = np.zeros(SAMPLE_COUNT, dtype=np.int16)
        #claude sonnet says this is a big issue #sample_bytearray = samples.tobytes()  # bytearray points to the sample samples array
        self.sample_bytearray=self.samples.tobytes()
        self.scratchpad = np.zeros(2 * SAMPLE_COUNT) # re-usable RAM for the calculation of the FFT
                                            # avoids memory fragmentation and thus OOM errors
        
        
        self.sample_view = memoryview(self.sample_bytearray)  # save an allocation by reusing this
        self.n_slice = 0
        
        # Discard initial garbage, also need to do an initial read so IRQ starts triggering
        self.microphone.readinto(self.sample_bytearray)
        
        
    async def sample(self):       
        await self.flag.wait()
        
        # this number should be non-zero, so the other coros can run. but if it's large
        # then can probably tune the buffer sizes to get more responsiveness

        # Set up a slice into I2S_SAMPLE_COUNT samples of the 'samples'
        # array, viewed as an unstructured bytearray
        start_idx = self.n_slice * I2S_SAMPLE_BYTES
        end_idx = start_idx + I2S_SAMPLE_BYTES
        read_slice = self.sample_view[start_idx:end_idx]

        # Read I2S samples into just this slice of bytes
        num_read = self.microphone.readinto(read_slice) # 1ms !

        assert(num_read == I2S_SAMPLE_BYTES)  # if not true then need to be a bit more tricky about measuring slices
        
        # Increment for the next rolling chunk of samples
        self.n_slice = (self.n_slice + 1) % (SAMPLE_COUNT // I2S_SAMPLE_COUNT)
        start = self.n_slice * I2S_SAMPLE_COUNT
        self.samples[:]=np.roll(np.frombuffer(self.sample_bytearray,dtype=np.int16),-start)

#         self.n_slice += 1
#         if self.n_slice * I2S_SAMPLE_COUNT == SAMPLE_COUNT:
#             self.n_slice = 0
#             self.samples[:]=np.frombuffer(self.sample_bytearray,dtype=np.int16)
        
        

#             print(f"after I2S: {gc.mem_free()}")
        
        return(self.samples)
    
        await asyncio.sleep_ms(0) #yeild control. #this one line appears to have made the program substantially more responsive in the menu side of things.
        
