#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# display_image.py
#
# Take a file in any format supported by Pillow and display it on an attached
# TCMP e-ink screen.
#
import argparse
import logging
import sys

from PIL import Image

try:
    import PD_Eink
except ImportError:
    FAKE = True
else:
    FAKE = False

SPI_BUS = 0
SPI_DEV = 0
BUSY_PIN = 18


class FakeDisp(object):
    def __init__(self):
        self.width = 400
        self.height = 300


def main(in_file):
    if FAKE:
        disp = FakeDisp()
    else:
        disp = PD_Eink.TCMP(spi_bus=SPI_BUS, spi_device=SPI_DEV, bsy=BUSY_PIN)
        disp.begin()
    print(in_file)

    in_im = Image.open(in_file)
    in_im.thumbnail((disp.width, disp.height))
    in_im = in_im.convert('1')  # Convert to 1 bit

    # Create a new image the full size of the screen and centre the downsampled
    # image on it.
    im = Image.new('1', (disp.width, disp.height), color=255)
    y_off = (im.height - in_im.height) // 2
    x_off = (im.width - in_im.width) // 2

    im.paste(in_im, (x_off, y_off))

    if FAKE:
        im.show()
        return

    disp.image = im
    disp.display()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        handlers=[logging.StreamHandler()])
    main(sys.argv[-1])
