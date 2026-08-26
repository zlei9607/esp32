"""ESP32 + PCA9685 web servo control. Upload: main.py pca9685.py servo.py index.html"""

import network
import socket
import time
from machine import Pin, SoftI2C
from pca9685 import PCA9685
from servo import Servo, move_all, nod, peace, self_test

WIFI_SSID = ""
WIFI_PASSWORD = ""

SDA, SCL, ADDR, FREQ = 21, 22, 0x40, 50
MAX_A = (180, 180, 180, 180, 180, 100)
HOME = (90, 90, 90, 90, 90, 90)
ARM = (90, 30, 180, 140, 90, 100)
N = 6


def wifi(ssid, pwd, timeout=25):
    network.WLAN(network.AP_IF).active(False)
    w = network.WLAN(network.STA_IF)
    w.active(True)
    if not w.isconnected():
        w.connect(ssid, pwd)
        t0 = time.ticks_ms()
        while not w.isconnected():
            if time.ticks_diff(time.ticks_ms(), t0) > timeout * 1000:
                raise RuntimeError("WiFi timeout")
            time.sleep_ms(200)
    print("WiFi:", w.ifconfig()[0])
    return w


def qs(path):
    if "?" not in path:
        return path, {}
    base, q = path.split("?", 1)
    p = {}
    for part in q.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            p[k] = v
    return base, p


def reply(cli, status, body, ctype="text/html; charset=utf-8"):
    if isinstance(body, str):
        body = body.encode()
    h = "HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % (
        status, ctype, len(body)
    )
    cli.send(h.encode() + body)


def angles(servos):
    return "[" + ",".join(str(s.angle) for s in servos) + "]"


def main():
    with open("index.html") as f:
        html = f.read()

    i2c = SoftI2C(sda=Pin(SDA), scl=Pin(SCL), freq=400000)
    if ADDR not in i2c.scan():
        raise RuntimeError("PCA9685 0x40 not found")
    pca = PCA9685(i2c, ADDR, FREQ)
    servos = [Servo(pca, i, HOME[i], MAX_A[i]) for i in range(N)]

    ip = wifi(WIFI_SSID, WIFI_PASSWORD).ifconfig()[0]
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 80))
    srv.listen(2)
    print("http://%s/" % ip)

    while True:
        cli, _ = srv.accept()
        try:
            req = cli.recv(1024)
            if not req:
                continue
            line = req.split(b"\r\n", 1)[0].decode().split()
            if len(line) < 2:
                continue
            path, p = qs(line[1])
            J = "application/json"

            if path in ("/", "/index.html"):
                reply(cli, "200 OK", html)
            elif path == "/state":
                reply(cli, "200 OK", angles(servos), J)
            elif path == "/set":
                i, a = int(p.get("s", "-1")), int(p.get("a", "90"))
                if 0 <= i < N:
                    servos[i].set(a)
                    reply(cli, "200 OK", '{"ok":1}', J)
                else:
                    reply(cli, "400 Bad Request", '{"ok":0}', J)
            elif path == "/home":
                move_all(servos, HOME)
                reply(cli, "200 OK", angles(servos), J)
            elif path == "/arm":
                move_all(servos, ARM)
                reply(cli, "200 OK", angles(servos), J)
            elif path == "/nod":
                nod(servos, ARM)
                reply(cli, "200 OK", angles(servos), J)
            elif path == "/peace":
                peace(servos, ARM)
                reply(cli, "200 OK", angles(servos), J)
            elif path == "/test":
                self_test(servos)
                reply(cli, "200 OK", angles(servos), J)
            else:
                reply(cli, "404 Not Found", "Not Found")
        except Exception as e:
            print("err:", e)
        finally:
            try:
                cli.close()
            except OSError:
                pass


main()
