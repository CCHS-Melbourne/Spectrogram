# PancakeLED lights

Also known as "EdgeLit" it's a 36 LED stack of neopixel joy with an integrated microphone:

* Audio reactive LEDs
* Acrylic-ready, to show off your creative animations
* Touch-enabled to switch between all its range of features

## Micropyhon

If you have a Waveshare Mini S3 board, you need to flash an appropriate 4MB flash binary (with ulab):

```
esptool.py --chip esp32s3 --port /dev/ttyACM0 write_flash -z 0 ~/dev/personal/pancake-legend-lights/src/micropython/fw/generic_s3_flash_4M_ulab_micropython.bin
```

Otherwise browse around the available firmwares in `micropython/src/fw` folder and/or build it yourself with micropython-builder!
