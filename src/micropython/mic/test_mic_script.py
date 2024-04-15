import uasyncio as asyncio
from machine import I2S, Pin, Timer
import time

async def read_microphone_data(audio_in, duration_seconds):
    sreader = asyncio.StreamReader(audio_in)
    start_time = time.time()
    
    try:
        while True:
            # Check if the specified duration has elapsed
            if time.time() - start_time >= duration_seconds:
                print("Finished recording.")
                break

            # Read data from the microphone
            data = await sreader.read(1024)  # Adjust buffer size as needed

            # Optionally, print the data (you might want to comment this out for very short durations)
            print("Microphone data:", data)
    finally:
        # Clean up resources
        audio_in.deinit()

def main():
    # Configure I2S interface for microphone input
    audio_in = I2S(
        0,  # I2S peripheral ID
        sck=Pin(5),  # Serial clock pin
        ws=Pin(25),  # Word select (or word clock) pin
        sd=Pin(35),  # Serial data input pin
        mode=I2S.RX,
        bits=32,  # 32-bit samples
        format=I2S.MONO,  # Mono audio
        rate=44100,  # Sample rate (adjust as needed)
        ibuf=1024  # Input buffer size (adjust as needed)
    )

    # Start reading microphone data asynchronously, running for a specified duration
    duration_seconds = 0.1  # How long to record, in seconds
    asyncio.run(read_microphone_data(audio_in, duration_seconds))

if __name__ == "__main__":
    main()