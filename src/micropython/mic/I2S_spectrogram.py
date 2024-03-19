# The MIT License (MIT)
# Copyright (c) 2022 Mike Teachman
# https://opensource.org/licenses/MIT

# Purpose:  Read audio samples from an I2S microphone and write to SD card
#
# - read 32-bit audio samples from I2S hardware, typically an I2S MEMS Microphone
# - convert 32-bit samples to specified bit size and format
# - samples will be continuously written to the WAV file
#   for the specified amount of time
#
# uasyncio 

import os
import time
import urandom
import uasyncio as asyncio
from machine import I2S
from machine import Pin

if os.uname().machine.count("ESP32"):
    # ======= I2S CONFIGURATION =======
    SD_PIN = 4
    SCK_PIN = 5
    WS_PIN = 12
    I2S_ID = 0
    BUFFER_LENGTH_IN_BYTES = 40000
    # ======= I2S CONFIGURATION =======

else:
    print("Warning: program not tested with this board")

# ======= AUDIO CONFIGURATION =======
RECORD_TIME_IN_SECONDS = 0.1
WAV_SAMPLE_SIZE_IN_BITS = 16
FORMAT = I2S.MONO
SAMPLE_RATE_IN_HZ = 22050
# ======= AUDIO CONFIGURATION =======

format_to_channels = {I2S.MONO: 1, I2S.STEREO: 2}
NUM_CHANNELS = format_to_channels[FORMAT]
WAV_SAMPLE_SIZE_IN_BYTES = WAV_SAMPLE_SIZE_IN_BITS // 8
RECORDING_SIZE_IN_BYTES = (RECORD_TIME_IN_SECONDS * SAMPLE_RATE_IN_HZ * WAV_SAMPLE_SIZE_IN_BYTES * NUM_CHANNELS)

async def get_mic_audio_samples(audio_in):
    sreader = asyncio.StreamReader(audio_in)

    mic_samples = bytearray(10000)
    mic_samples_mv = memoryview(mic_samples)
    
    num_sample_bytes_written_to_wav = 0
    
    print("==========  START RECORDING ==========")
    while num_sample_bytes_written_to_wav < RECORDING_SIZE_IN_BYTES:
        num_bytes_read_from_mic = await sreader.readinto(mic_samples_mv)
        if num_bytes_read_from_mic > 0:
            num_bytes_to_write = min(
                num_bytes_read_from_mic, RECORDING_SIZE_IN_BYTES - num_sample_bytes_written_to_wav
            )
            # Write samples to WAV file
            # Implementation needed here
            # For now, let's just increment the counter
            num_sample_bytes_written_to_wav += num_bytes_to_write  # Increment counter
            
    print("==========  DONE RECORDING ==========")
    print(num_bytes_read_from_mic)
    print(mic_samples_mv.hex())
    audio_in.deinit()  # Cleanup

async def spectrogram(name):
    while True:
        await asyncio.sleep(urandom.randrange(2, 5))
        print("{} woke spectrogram up".format(name))
        time.sleep_ms(10)  # simulates task doing something

async def colorchord(name):
    while True:
        await asyncio.sleep(urandom.randrange(2, 5))
        print("{} woke colorchord up".format(name))
        time.sleep_ms(10)  # simulates task doing something

async def main(audio_in):
    mic_record = asyncio.create_task(get_mic_audio_samples(audio_in))

    while True:
        await asyncio.sleep_ms(10)

try:
    audio_in = I2S(
        I2S_ID,
        sck=Pin(SCK_PIN),
        ws=Pin(WS_PIN),
        sd=Pin(SD_PIN),
        mode=I2S.RX,
        bits=WAV_SAMPLE_SIZE_IN_BITS,
        format=FORMAT,
        rate=SAMPLE_RATE_IN_HZ,
        ibuf=BUFFER_LENGTH_IN_BYTES,
    )

    asyncio.run(main(audio_in))
    
except (KeyboardInterrupt, Exception) as e:
    print("Exception {} {}\n".format(type(e).__name__, e))
finally:
    audio_in.deinit()  # Cleanup
