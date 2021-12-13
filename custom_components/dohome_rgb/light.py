"""Support for DoHome RGB Lights"""
from __future__ import annotations

import logging
from datetime import timedelta
import homeassistant.util.color as color_util
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    PLATFORM_SCHEMA,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    LightEntity,
)

from .convert import _dohome_percent, _dohome_to_uint8
from .dohome_api import _send_command

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

CONF_ENTITIES = 'entities'
CONF_NAME = 'name'
CONF_SID = 'sid'
CONF_IP = 'ip'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITIES, default=[]): cv.ensure_list,
})

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    '''
    Initialises submitted devices
    '''
    devices = []
    for device in config[CONF_ENTITIES]:
        devices.append(DoHomeLight(hass, device))
    if len(devices) > 0:
        add_devices(devices)


class DoHomeLight(LightEntity):
    '''
    Entity of the DoHome light device
    '''
    def __init__(self, hass, device):
        self._device = device
        self._name = device[CONF_NAME]
        self._state = False
        self._rgb = (255, 255, 255)
        self._brightness = 255
        self._color_temp = 128
        self._color_mode = COLOR_MODE_HS
        self._available = True
        self.update(True)

    @property
    def name(self):
        '''
        Return the name of the device.
        '''
        return self._name

    @property
    def unique_id(self):
        """Return the unique_id of the device."""
        return self._name

    @property
    def brightness(self):
        '''Return the brightness of this light between 0..255.'''
        return self._brightness

    @property
    def color_mode(self):
        '''Return the color mode of this light'''
        return self._color_mode

    @property
    def available(self):
        '''Returns status of this light.'''
        return self._available

    @property
    def hs_color(self):
        '''Return the color property.'''
        return color_util.color_RGB_to_hs(*self._rgb)

    @property
    def is_on(self):
        '''Return true if light is on.'''
        return self._state

    @property
    def color_temp(self):
        return self._color_temp

    @property
    def supported_color_modes(self):
        return { COLOR_MODE_HS, COLOR_MODE_COLOR_TEMP }

    @property
    def min_mireds(self):
        return 0

    @property
    def max_mireds(self):
        return 255

    def turn_on(self, **kwargs):
        '''Turn the light on.'''
        rgb = [0, 0, 0]
        white = [0, 0]

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        if ATTR_HS_COLOR in kwargs:
            self._rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            self._color_mode = COLOR_MODE_HS
        if ATTR_COLOR_TEMP in kwargs:
            self._color_temp = kwargs[ATTR_COLOR_TEMP]
            self._color_mode = COLOR_MODE_COLOR_TEMP

        brigthness_percent = self._brightness / 255

        if self._color_mode is COLOR_MODE_HS:
            rgb = list(
                map(lambda x: 5000 * (x / 255) * brigthness_percent, self._rgb))
        elif self._color_mode is COLOR_MODE_COLOR_TEMP:
            warm = 5000 * self._color_temp / 255
            cold = 5000 - warm
            warm = warm * brigthness_percent
            cold = cold * brigthness_percent
            white = [cold, warm]

        self._state = True
        self._set_state(rgb, white)

    def turn_off(self, **kwargs):
        '''Turn the light off.'''
        self._state = False
        self._set_state([0, 0, 0], [0, 0])

    def _set_state(self, rgb, white):
        data = {
            'r': int(rgb[0]),
            'g': int(rgb[1]),
            'b': int(rgb[2]),
            'w': int(white[0]),
            'm': int(white[1])
        }
        self._send_command(6, data)

    def update(self):
        '''
        Loads state from device
        '''
        state = self._send_command(25)
        if state is None:
            return
        if state['r'] + state['g'] + state['b'] == 0:
            if state['w'] + state['m'] == 0:
                self._state = False
            else:
                brighness_percent = _dohome_percent(state['m'] + state['w'])
                self._state = True
                self._color_mode = COLOR_MODE_COLOR_TEMP
                self._brightness = 255 * brighness_percent
                self._color_temp = _dohome_to_uint8(state['m'] / brighness_percent)
        else:
            self._state = True
            self._color_mode = COLOR_MODE_HS
            self._rgb = list(map(_dohome_to_uint8, [state['r'], state['g'], state['b']]))
            if not is_first:
                return
            _, _, brightness = color_util.color_RGB_to_xy_brightness(
                state['r'],
                state['g'],
                state['b']
            )
            self._brightness = int(brightness)

    def _send_command(self, cmd, data=None):
        result = _send_command(
            self._device[CONF_IP],
            self._device[CONF_SID],
            cmd,
            data
        )
        self._available = not result is None
        return result