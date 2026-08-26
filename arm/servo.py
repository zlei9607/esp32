"""Servo + arm motions."""

import time
from machine import idle

_US0, _US1 = 500, 2500
_STEP, _MS = 2, 20


class Servo:
    def __init__(self, pca, ch, home, max_a):
        self.pca, self.ch, self.max_angle = pca, ch, max_a
        self.home = self.angle = max(0, min(max_a, home))
        self.set(self.angle)

    def set(self, angle):
        self.angle = max(0, min(self.max_angle, int(angle)))
        us = _US0 + (_US1 - _US0) * self.angle // 180
        self.pca.set_pulse_us(self.ch, us)


def move_slow(s, target):
    target = max(0, min(s.max_angle, int(target)))
    while s.angle != target:
        d = _STEP if s.angle < target else -_STEP
        nxt = s.angle + d
        if (d > 0 and nxt > target) or (d < 0 and nxt < target):
            nxt = target
        s.set(nxt)
        time.sleep_ms(_MS)
        idle()


def move_all(servos, angles):
    for s, a in zip(servos, angles):
        move_slow(s, a)


def nod(servos, pose, idx=3, lo=130, hi=180, n=3, end=140):
    move_all(servos, pose)
    s = servos[idx]
    for _ in range(n):
        move_slow(s, lo)
        move_slow(s, hi)
    move_slow(s, end)


def peace(servos, pose, a4=60, a6=70):
    move_all(servos, pose)
    move_slow(servos[3], a4)
    move_slow(servos[5], a6)


def self_test(servos):
    for s in servos:
        move_slow(s, 0)
        move_slow(s, s.home)
        time.sleep(1)
