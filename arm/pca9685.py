"""PCA9685 16-ch PWM (servo 50Hz)."""

import time


class PCA9685:
    def __init__(self, i2c, addr=0x40, freq=50):
        self.i2c, self.addr = i2c, addr
        self._w(0x00, b"\x00")
        time.sleep_ms(5)
        self.set_freq(freq)

    def _w(self, reg, data):
        self.i2c.writeto_mem(self.addr, reg, data)

    def set_freq(self, freq):
        pre = int(25000000.0 / (4096 * freq) + 0.5) - 1
        old = self.i2c.readfrom_mem(self.addr, 0x00, 1)[0]
        self._w(0x00, bytes([(old & 0x7F) | 0x10]))
        self._w(0xFE, bytes([pre]))
        self._w(0x00, bytes([old]))
        time.sleep_ms(5)
        self._w(0x00, bytes([old | 0xA1]))

    def set_pulse_us(self, ch, us):
        ticks = max(0, min(4095, us * 4096 // 20000))
        base = 0x06 + 4 * ch
        self._w(base, bytes([0, 0, ticks & 0xFF, (ticks >> 8) & 0xFF]))
