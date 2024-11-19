# PancakeLED lights

Also known as "EdgeLit" it's a 36 LED stack of neopixel joy with an integrated microphone:

* Audio reactive LEDs
* Acrylic-ready, to show off your creative animations
* Stepped structure to elimate gaps between edge-lit panels
* Touch-enabled to switch between all its range of features

## Micropyhon

Pre-compiled firmwares live in `fw` folder.

If you have a Waveshare Mini S3 board, you need to flash an appropriate 4MB flash binary (with ulab):

```
esptool.py --chip esp32s3 --port /dev/ttyACM0 write_flash -z 0 fw/generic_s3_flash_4M_ulab_micropython.bin
```

Otherwise browse around the available firmwares in `micropython/src/fw` folder and/or build it yourself with micropython-builder!

### Building

For building the firmware it helps to use `mpbuild` like so:

```
$ git clone https://github.com/mattytrentini/mpbuild && cd mpbuild
$ git clone https://github.com/v923z/micropython-ulab ulab
$ python3 -mvenv .venv && source .venv/bin/activate && pip install -e .
(.venv)$ mpbuild build ESP32_GENERIC_S3 FLASH_4M USER_C_MODULES=$PWD/ulab/code/micropython.cmake all
```

The resulting object you want to flash with the `esptool.py` command from the previous section is `firmware.bin`.

### Running

```sh
cd src/micropython
./run.sh
```
