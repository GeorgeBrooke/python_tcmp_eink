#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import logging

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

import PD_Eink

SPI_BUS = 0
SPI_DEV = 0
BUSY_PIN = 18

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

disp = PD_Eink.TCMP(spi_bus=SPI_BUS, spi_device=SPI_DEV, bsy=BUSY_PIN)
# Bitbang SPI
# disp = PD_Eink.P441(sclk=17, din=25, cs=22, bsy=BUSY_PIN)
# Or custom SPI
# diso = PD_Eink.P441(spi=SPI, bsy=BUSY_PIN)

# Initialise display
disp.begin()

# Blank the display
disp.clear()
disp.display()

# Shape drawing from Adafruit example:
# https://learn.adafruit.com/ssd1306-oled-displays-with-raspberry-pi-and-beagle
# bone-black/usage
#
# Get a PIL image of the correct size with 1bit colour
width = disp.width
height = disp.height
image = Image.new('1', (width, height), color=255)

# Get a drawing object on the image
draw = ImageDraw.ImageDraw(image)

# Draw some shapes.
# First define some constants to allow easy resizing of shapes.
padding = 2
shape_width = 60
top = padding
bottom = height-padding
# Move left to right keeping track of the current x position for drawing shapes
x = padding
# Draw an ellipse.
draw.ellipse((x, top, x+shape_width, bottom), outline=0, fill=255)
x += shape_width+padding
# Draw a rectangle.
draw.rectangle((x, top, x+shape_width, bottom), outline=0, fill=255)
x += shape_width+padding
# Draw a triangle.
draw.polygon([(x, bottom), (x+shape_width/2, top), (x+shape_width, bottom)],
             outline=0, fill=255)
x += shape_width+padding
# Draw an X.
draw.line((x, bottom, x+shape_width, top), fill=0)
draw.line((x, top, x+shape_width, bottom), fill=0)
x += shape_width+padding

# Load default font.
font = ImageFont.load_default()

# Alternatively load a TTF font.
# Some other nice fonts to try: http://www.dafont.com/bitmap.php
# font = ImageFont.truetype('Minecraftia.ttf', 8)
# font = ImageFont.truetype('/usr/share/fonts/TTF/Gentium-R.ttf', size=40)
font = ImageFont.truetype('/usr/share/fonts/TTF/RobotoCondensed-Regular.ttf', size=60)

# Write two lines of text.
draw.text((x, top),    'Hello',  font=font, fill=0)
draw.text((x, top+50), 'World!', font=font, fill=0)

# Display image.
disp.image = image
disp.display()
