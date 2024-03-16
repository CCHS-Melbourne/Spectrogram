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
    SCK_PIN = 5
    WS_PIN = 12
    SD_PIN = 4
    I2S_ID = 0
    BUFFER_LENGTH_IN_BYTES = 40000
    # ======= I2S CONFIGURATION =======

else:
    print("Warning: program not tested with this board")

# ======= AUDIO CONFIGURATION =======
RECORD_TIME_IN_SECONDS = 10
WAV_SAMPLE_SIZE_IN_BITS = 16
FORMAT = I2S.MONO
SAMPLE_RATE_IN_HZ = 22050
# ======= AUDIO CONFIGURATION =======

format_to_channels = {I2S.MONO: 1, I2S.STEREO: 2}
NUM_CHANNELS = format_to_channels[FORMAT]
WAV_SAMPLE_SIZE_IN_BYTES = WAV_SAMPLE_SIZE_IN_BITS // 8
RECORDING_SIZE_IN_BYTES = (
    RECORD_TIME_IN_SECONDS * SAMPLE_RATE_IN_HZ * WAV_SAMPLE_SIZE_IN_BYTES * NUM_CHANNELS
)

async def get_mic_audio_samples(audio_in, wav):
    sreader = asyncio.StreamReader(audio_in)

    # allocate sample array
    # memoryview used to reduce heap allocation
    mic_samples = bytearray(10000)
    mic_samples_mv = memoryview(mic_samples)

    # continuously read audio samples from I2S hardware
    print("Recording size: {} bytes".format(RECORDING_SIZE_IN_BYTES))
    print("==========  START RECORDING ==========")
    while num_sample_bytes_written_to_wav < RECORDING_SIZE_IN_BYTES:
        # read samples from the I2S peripheral
        num_bytes_read_from_mic = await sreader.readinto(mic_samples_mv)
        # write samples to WAV file
        if num_bytes_read_from_mic > 0:
            num_bytes_to_write = min(
                num_bytes_read_from_mic, RECORDING_SIZE_IN_BYTES - num_sample_bytes_written_to_wav
            )

    # cleanup
    audio_in.deinit()


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


async def main(audio_in, wav):
    mic_record = asyncio.create_task(get_mic_audio_samples(audio_in, wav))
    spectrogram = asyncio.create_task(spectrogram("Hank's Magic"))
    colorchord = asyncio.create_task(colorchord("CNLohr's magic"))

    # keep the event loop active
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

    asyncio.run(main(audio_in, wav))
except (KeyboardInterrupt, Exception) as e:
    print("Exception {} {}\n".format(type(e).__name__, e))
finally:
    # cleanup
    audio_in.deinit()
    ret = asyncio.new_event_loop()  # Clear retained uasyncio state
