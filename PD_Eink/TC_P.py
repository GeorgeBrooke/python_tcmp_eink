# -*- coding: utf-8 -*-
#
# Display class for the Pervasive Display TC(M)-P series of e-ink displays and
# controllers.
#
# Supported:
# * TCM-P441 (4.41 inch panel)
# Untested:
# * TCM-P102
# Unsuported:
# * TCM-P74
#
# Copyright © 2017 George Brooke.
#
# Based on Adafruit SSD1306 OLED display class which is:
# Copyright © 2014-2016 Adafruit Industries.
# Author: Tony DiCola
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
from __future__ import division
import logging
import time

from PIL import Image

import Adafruit_GPIO as GPIO
import Adafruit_GPIO.SPI as SPI

TCMP_RESPONSE = {
        0x9000: "Success",
        0x6700: "Incorrect value for data length",
        0x6C00: "Incorrect value for expected reply length",
        0x6A00: "Invalid P1 or P2 parameter",
        0x6D00: "Unsupported command"
        }
TCMP_RESP_OK = 0x9000

# Controller commands
# Sensor info
TCMP_READ_TEMP = dict(inst=0xE5, p1=0x01, p2=0x00, len_resp=2)
# Hardware info
TCMP_GET_DEV_INFO = dict(inst=0x30, p1=0x01, p2=0x01, len_resp=0,
                         read_string=True)
TCMP_GET_DEV_ID = dict(inst=0x30, p1=0x02, p2=0x01, len_resp=20)
# Firmware info
TCMP_GET_SYS_INFO = dict(inst=0x31, p1=0x01, p2=0x01, len_resp=0,
                         read_string=True)
TCMP_GET_SYS_VER = dict(inst=0x31, p1=0x02, p2=0x01, len_resp=16)
# Image control
TCMP_UPLOAD_IMAGE = dict(inst=0x20, p1=0x01, p2=0)
TCMP_RESET_POINTER = dict(inst=0x20, p1=0x0D, p2=0)
TCMP_DISPLAY_UPDATE = dict(inst=0x24, p1=0x01, p2=0)
# Image headers
TCMP_HEADER_441 = [0x33, 0x01, 0x90, 0x01, 0x2C, 0x01, 0x00] + [0]*9
TCMP_HEADER_74 = [0x3A, 0x01, 0xE0, 0x03, 0x20, 0x01, 0x04] + [0]*9
TCMP_HEADER_102 = [0x3D, 0x04, 0x00, 0x05, 0x00, 0x01, 0x00] + [0]*9

TCMP_MAX_HZ = 3000000  # 3MHz
# Default speed selected because it works with long and not especially neat
# wiring
TCMP_DEF_HZ = 200000  # 200kHz


class TCMP(object):
    """Class for TC(M)-P e-ink display panels from Pervasive Displays. This
    class detects the display type and adapts accordingly"""

    def __init__(self, bsy, spi_bus=None, spi_device=None, sclk=None, din=None,
                 cs=None, spi=None, gpio=None, speed=TCMP_DEF_HZ):
        self._log = logging.getLogger('PD_Eink.TC_P')

        self._width = None
        self._height = None
        self._model = None
        # The panels support different image formats...
        self._img_format = None
        self._header = None
        self._img_buffer = None

        # Default to platform GPIO
        self._gpio = gpio
        if self._gpio is None:
            self._gpio = GPIO.get_platform_gpio()

        # Setup the busy pin
        self._bsy = bsy
        self._gpio.setup(self._bsy, GPIO.IN, GPIO.PUD_UP)

        # SPI priority: passed SPI > Hardware SPI > Software SPI
        if spi is not None:
            self._log.info('Using passed SPI')
            self._spi = spi
        elif spi_bus is not None and spi_device is not None:
            self._log.info('Using hardware SPI')
            self._spi = SPI.SpiDev(spi_bus, spi_device,
                                   max_speed_hz=speed)
        elif sclk is not None and din is not None and cs is not None:
            self._log.info('Using software SPI')
            self._spi = SPI.BitBang(self._gpio, sclk, din, None, cs)
            # Bitbang doesn't support setting speed.
        else:
            raise ValueError('Not enough arguments to setup SPI.')

        # Set the required SPI parameters
        # Clock Polarity (CPOL) = 1
        # Clock Phase (CPHA) = 1
        # Bit order = MSB first
        # This should be MODE 3 (0b11) SPI
        self._spi.set_mode(3)
        self._spi.set_bit_order(SPI.MSBFIRST)

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def model(self):
        return self._model

    @property
    def temp(self):
        """Temperature of the controller board."""
        resp = self.command(**TCMP_READ_TEMP)
        # Calculations taken from the TCon developers guide
        val = (resp[0] << 8) | resp[1]

        if val < 42:
            a = 0.66
            b = -19.69
        elif val < 62:
            a = 0.52
            b = -13.95
        elif val < 87:
            a = 0.43
            b = -8.55
        else:
            a = 0.39
            b = -4.57

        t = (a * val) + b

        return t

    def begin(self):
        """Initialise display and read display type."""
        dev_info = self._get_dev_info()

        if dev_info == "MpicoSys TC-P441-230_v1.0":
            # Tested
            self._model = "TC-P441"
            self._width = 400
            self._height = 300
            # Format 2 is also supported but 0 is simpler
            self._img_format = 0
            self._img_buffer = [0] * 15000
            self._header = TCMP_HEADER_441
        elif dev_info == "MpicoSys TC-P74-230_v1.0":
            # Not supported
            self._model = "TC-P74"
            self._width = 480
            self._height = 800
            self._img_format = 4
            self._img_buffer = [0] * 48000
            self._header = TCMP_HEADER_74
        elif dev_info == "MpicoSys TC-P102-220_v1.1":
            # Untested but should work
            self._model = "TC-P102"
            self._width = 1024
            self._height = 1280
            self._img_format = 0
            self._img_buffer = [0] * 163840
            self._header = TCMP_HEADER_102

        m = 'Detected a {} with a resolution of {}x{}'.format(self._model,
                                                              self._width,
                                                              self._height)
        self._log.info(m)

        if self._model == "TC-P74":
            raise NotImplementedError

    def command(self, inst, p1, p2, data=None, len_resp=None,
                read_string=False):
        """
        Send a command to the e-ink contoller and read the response.

        Three parameters are required:
            inst: Instruction to send.
            p1, p2: Positional paramters for all commands.

        There are two optional paramters:
            data: List (or other iterable) of bytes to send.
            len_resp: Length in bytes of the expted response.

        If read_string is True then an ugly hack will be used to read the
        string, null, resp_code responses to some system info commands.
        This is required due to a combination of the odd way these
        responses are formatted (no known length and you must read beyond
        the null terminator) and the fact that the data is lost if more
        than one readbytes() transation is called (is CS deasserted?).
        The work-around is to read 100bytes then search for the null
        terminator and trim the response list.
        """
        if data is None:
            len_data = 0
        else:
            len_data = len(data)

        if len_data > 250:
            raise ValueError('Data is too large {}>250'.format(len_data))
        if (len_resp is not None) and (len_resp > 0xFF):
            raise ValueError('Response length must fit in one byte.')

        # Now build the packet as a list of bytes
        packet = [inst, p1, p2, len_data]
        if data:
            packet.extend(data)
        if len_resp is not None:
            packet.append(len_resp)
        else:
            # set an expected response length for use further on
            len_resp = 0

        # Send it
        self._log.debug('SEND: [{}]'.format(', '.
                        join('0x{:02X}'.format(i) for i in packet)))
        self._spi.write(packet)

        # Allow setting an explicit read_string length, remember to include
        # the null terminator in the length.
        if read_string is True:
            read_string = 100
        if read_string:
            len_resp = read_string

        # Add two bytes to the read for the response values
        len_resp += 2
        self._busy_wait()

        resp = self._spi.read(len_resp)
        self._log.debug('RCVD: [{}]'.format(', '.
                        join('0x{:02X}'.format(i) for i in resp)))
        # print(resp)

        if read_string:
            try:
                # Find the null terminator
                nullpoint = resp.index(0)
            except ValueError:
                raise CommunicationError('Could not find null terminator' +
                                         'in string response')
            try:
                # Trim the response to two bytes beyond the null terminator
                # to include the response code.
                # This is +3 as the endpoint is non-inclusive in slicing.
                resp = resp[:nullpoint+3]
                data = resp[:nullpoint]
                rval = (resp[nullpoint + 1] << 8) | resp[nullpoint + 2]
            except IndexError:
                raise CommunicationError('Response too long for buffer.')
        else:
            data = resp[:-2]
            rval = (resp[-2] << 8) | resp[-1]
        # Now test the response code for success.
        if rval != TCMP_RESP_OK:
            emsg = TCMP_RESPONSE.get(rval, 'Unknown error')
            msg = ('TCMP Command returned failure code:' +
                   '0x{:02X} - {}'.format(rval, emsg))
            self._log.info(msg)
            raise TCMPError(msg)

        return data

    def display(self):
        """Upload the local image to the display and refresh the screen."""
        self.upload()
        self.refresh()

    def upload(self):
        """Send the local image buffer to the controller flash."""
        # Error handling:
        # We ignore exceptions during image upload as experiance shows
        # these are spurious. Possibly we should have a threshold for
        # considering the upload to have failed. Retries will need to
        # resend the entire image.

        # We can send up to 250 bytes in each packet
        BATCH = 250

        # This copy wastes space, but it's only 170kb
        im_file = self._header + self._img_buffer
        im_len = len(im_file)

        # First reset controllers image pointer to the start of memory
        self.command(**TCMP_RESET_POINTER)

        for s in range(0, im_len, BATCH):
            e = s + BATCH
            if e > im_len:
                # Final packet may be smaller
                e = im_len

            try:
                self.command(data=im_file[s:e], **TCMP_UPLOAD_IMAGE)
            except TCMPError:
                pass

    def refresh(self):
        """Refresh the display, showing the contents of the controller
        flash."""
        self.command(**TCMP_DISPLAY_UPDATE)

    @property
    def image(self):
        """Local buffered image, stored in the format used by the display
        controller."""
        im = Image.new('1', (self.width, self.height))
        if self._img_format == 0:
            im.putdata(self._unconvert_0)
        elif self._img_format == 2:
            raise NotImplementedError
        elif self._img_format == 4:
            raise NotImplementedError
        return im

    @image.setter
    def image(self, image):
        """Set local buffer to the PIL image. This must be in 1 bit mode
        and equal to the display size. The image is converted into the
        correct format for the display."""
        if image.mode != '1':
            raise ValueError("Image must be in 1-bit mode (mode 1).")
        imwidth, imheight = image.size
        if imwidth != self.width or imheight != self.height:
            raise ValueError("Image dimensions must match the display" +
                             "({}x{}; image was {}x{})"
                             .format(self.width, self.height, imwidth,
                                     imheight))
        pix = image.getdata()
        if self._img_format == 0:
            self._convert_0(pix)
        elif self._img_format == 2:
            # Alt for P441
            raise NotImplementedError()
        elif self._img_format == 4:
            raise NotImplementedError()

    def clear(self):
        """Clear the local display buffer."""
        self._img_buffer = [0x00] * len(self._img_buffer)

    def _busy_wait(self):
        """Wait for the busy pin to be deasserted. TODO: Add a timeout."""
        # So far this works, but it might need to wait incase the busy
        # signal hasn't been asserted yet...
        while self._gpio.is_low(self._bsy):
            time.sleep(0.01)

    def _resp_ok(self, resp):
        """Check if the response from the contoller indicates success."""
        # Combine two bytes from the end of the response into one value
        flag = (resp[-1] << 8) | resp[-1]
        rv = TCMP_RESPONSE.get(flag, 'Unknown error')
        self._log.info('Command failed: 0x{:02X} - {}'.format(flag, rv))
        return flag == TCMP_RESP_OK

    def _get_dev_info(self):
        """Read the device identifier string."""
        resp = self.command(**TCMP_GET_DEV_INFO)
        # Create a string from the ascii values of all but the last three
        # bytes (null term and resp code)
        dev = "".join(chr(b) for b in resp)
        return dev

    def _convert_0(self, pix):
        """Convert a sequence of pixels (as bytes) into format 0 data (one
        bit per pixel) and store in local image buffer."""
        out_pos = 0
        for i in range(0, len(pix), 8):
            o = (bool(pix[i+0]) << 7)\
              | (bool(pix[i+1]) << 6)\
              | (bool(pix[i+2]) << 5)\
              | (bool(pix[i+3]) << 4)\
              | (bool(pix[i+4]) << 3)\
              | (bool(pix[i+5]) << 2)\
              | (bool(pix[i+6]) << 1)\
              | (bool(pix[i+7]))
            # Flip the bits here as black/white are inverted on these displays
            # then & with 0xff to keep only one byte of it
            self._img_buffer[out_pos] = (~o) & 0xFF
            out_pos += 1

    def _unconvert_0(self):
        """Convert the format 0 image data in the internal buffer into a
        series of one byte per pixel which can be loaded by PIL."""
        out_buf = [None] * (len(self._img_buffer) * 8)
        in_pos = 0
        for i in range(0, len(out_buf), 8):
            b = self._img_buffer[in_pos]
            out_buf[i+0] = (b & 0x80) >> 7
            out_buf[i+1] = (b & 0x80) >> 6
            out_buf[i+2] = (b & 0x80) >> 5
            out_buf[i+3] = (b & 0x80) >> 4
            out_buf[i+4] = (b & 0x80) >> 3
            out_buf[i+5] = (b & 0x80) >> 2
            out_buf[i+6] = (b & 0x80) >> 1
            out_buf[i+7] = (b & 0x80)

            in_pos += 1


class TCMPError(Exception):
    pass


class CommunicationError(TCMPError):
    pass
