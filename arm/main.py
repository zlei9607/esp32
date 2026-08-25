"""
ESP32 + PCA9685 + MicroPython：网页控制 6 路舵机

I2C 默认：SDA=GPIO21，SCL=GPIO22，地址 0x40
舵机：PCA9685 CH0～CH5 = 舵机 1～6

归位 / 上电：全部 90°
机械臂形态：90, 30, 180, 140, 90, 100
点头模式：先机械臂形态，再 4号 130°↔180°×3，结束 140°
比耶模式：先机械臂形态，再 4号→60°、6号→70°
舵机6 最大 100°
"""

import network
import socket
import time
from machine import Pin, SoftI2C, idle

WIFI_SSID = ""
WIFI_PASSWORD = ""

# ---------- PCA9685 / I2C（ESP32 默认）----------
I2C_SDA = 21
I2C_SCL = 22
PCA9685_ADDR = 0x40
SERVO_CHS = (0, 1, 2, 3, 4, 5)  # CH0～CH5 → 舵机 1～6

SERVO_LABELS = (1, 2, 3, 4, 5, 6)
SERVO_MAX = (180, 180, 180, 180, 180, 100)
SERVO_HOME = (90, 90, 90, 90, 90, 90)
HOME_BTN = (90, 90, 90, 90, 90, 90)
ARM_POSE = (90, 30, 180, 140, 90, 100)
NOD_SERVO = 3
NOD_LOW, NOD_HIGH, NOD_TIMES = 130, 180, 3
NOD_END = 140
PEACE_S4, PEACE_S6 = 60, 70
N = len(SERVO_CHS)

PWM_FREQ = 50
PULSE_US_MIN = 500
PULSE_US_MAX = 2500
SLOW_STEP = 2
SLOW_MS = 20


class PCA9685:
    """精简 PCA9685 驱动：50Hz 舵机 PWM。"""

    MODE1 = 0x00
    PRESCALE = 0xFE
    LED0_ON_L = 0x06

    def __init__(self, i2c, addr=PCA9685_ADDR, freq=PWM_FREQ):
        self.i2c = i2c
        self.addr = addr
        self._write(self.MODE1, b"\x00")
        time.sleep_ms(5)
        self.set_freq(freq)

    def _write(self, reg, data):
        self.i2c.writeto_mem(self.addr, reg, data)

    def set_freq(self, freq):
        # 内部时钟约 25MHz，prescale = round(25e6 / (4096 * freq)) - 1
        prescale = int(25000000.0 / (4096 * freq) + 0.5) - 1
        old = self.i2c.readfrom_mem(self.addr, self.MODE1, 1)[0]
        self._write(self.MODE1, bytes([(old & 0x7F) | 0x10]))  # sleep
        self._write(self.PRESCALE, bytes([prescale]))
        self._write(self.MODE1, bytes([old]))
        time.sleep_ms(5)
        self._write(self.MODE1, bytes([old | 0xA1]))  # auto-increment + restart

    def set_pwm(self, channel, on, off):
        # on/off：0～4095 的计数点
        base = self.LED0_ON_L + 4 * channel
        self._write(
            base,
            bytes(
                [
                    on & 0xFF,
                    (on >> 8) & 0xFF,
                    off & 0xFF,
                    (off >> 8) & 0xFF,
                    ]
            ),
        )

    def set_pulse_us(self, channel, us):
        # 周期 20ms = 20000us → 4096 ticks
        ticks = us * 4096 // 20000
        ticks = max(0, min(4095, ticks))
        self.set_pwm(channel, 0, ticks)


def angle_to_us(angle):
    angle = max(0, min(180, int(angle)))
    return PULSE_US_MIN + (PULSE_US_MAX - PULSE_US_MIN) * angle // 180


class Servo:
    def __init__(self, pca, channel, home, max_angle):
        self.pca = pca
        self.channel = channel
        self.max_angle = max_angle
        self.home = max(0, min(max_angle, home))
        self.angle = self.home
        self.set(self.angle)

    def set(self, angle):
        self.angle = max(0, min(self.max_angle, int(angle)))
        self.pca.set_pulse_us(self.channel, angle_to_us(self.angle))


def move_slow(servo, target):
    target = max(0, min(servo.max_angle, int(target)))
    while servo.angle != target:
        if servo.angle < target:
            servo.set(min(servo.angle + SLOW_STEP, target))
        else:
            servo.set(max(servo.angle - SLOW_STEP, target))
        time.sleep_ms(SLOW_MS)
        idle()


def move_sequential(servos, targets):
    for s, t in zip(servos, targets):
        move_slow(s, t)


def run_nod_mode(servos):
    move_sequential(servos, ARM_POSE)
    s = servos[NOD_SERVO]
    for _ in range(NOD_TIMES):
        move_slow(s, NOD_LOW)
        move_slow(s, NOD_HIGH)
    move_slow(s, NOD_END)


def run_peace_mode(servos):
    move_sequential(servos, ARM_POSE)
    move_slow(servos[3], PEACE_S4)
    move_slow(servos[5], PEACE_S6)


def run_self_test(servos):
    for servo in servos:
        move_slow(servo, 0)
        move_slow(servo, servo.home)
        time.sleep(1)


def connect_wifi(ssid, password, timeout_s=25, retries=3):
    try:
        network.WLAN(network.AP_IF).active(False)
    except OSError:
        pass
    wlan = network.WLAN(network.STA_IF)
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            try:
                wlan.disconnect()
            except OSError:
                pass
            wlan.active(False)
            time.sleep_ms(300)
            wlan.active(True)
            time.sleep_ms(300)
            if not wlan.isconnected():
                print("正在连接 WiFi (%d/%d): %s" % (attempt, retries, ssid))
                wlan.connect(ssid, password)
                t0 = time.ticks_ms()
                while not wlan.isconnected():
                    if time.ticks_diff(time.ticks_ms(), t0) > timeout_s * 1000:
                        raise OSError("连接超时")
                    time.sleep_ms(200)
            print("WiFi 成功:", wlan.ifconfig())
            return wlan
        except OSError as e:
            last_error = e
            print("WiFi 失败:", e)
            try:
                wlan.active(False)
            except OSError:
                pass
            time.sleep_ms(500)
    raise RuntimeError("WiFi 连不上: %s" % last_error)


def parse_url(path):
    if "?" not in path:
        return path, {}
    base, query = path.split("?", 1)
    params = {}
    for part in query.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v
    return base, params


def http_send(client, status, body, content_type="text/html; charset=utf-8"):
    if isinstance(body, str):
        body = body.encode()
    head = (
               "HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n\r\n"
           ) % (status, content_type, len(body))
    client.send(head.encode() + body)


def angles_json(servos):
    return "[" + ",".join(str(s.angle) for s in servos) + "]"


# 与 index.html 保持一致；改 UI 时先改 index.html，再复制到此处
HTML = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>舵机控制</title>
<style>
  button { font-size: 20px; padding: 14px 8px; margin: 6px 4px; width: 160px; min-height: 52px; box-sizing: border-box; }
  input[type=range] { width: 100%; height: 32px; }
  p { font-size: 18px; }
</style>
</head>
<body>
<h1>六路舵机控制</h1>
<div id="list"></div>
<p>
  <button id="homeBtn">一键归位</button>
  <button id="armBtn">机械臂形态</button>
  <button id="nodBtn">点头模式</button>
  <button id="peaceBtn">比耶模式</button>
  <button id="testBtn">启动自测</button>
  <span id="status"></span>
</p>
<script>
const LABELS = [1,2,3,4,5,6];
const SCALE = [180,180,180,180,180,180];
const LIMIT = [180,180,180,180,180,100];
const START = [90,90,90,90,90,90];
const box = document.getElementById('list');
const statusEl = document.getElementById('status');

function clampDeg(i, deg) {
  return Math.max(0, Math.min(LIMIT[i], deg));
}

function apply(angles) {
  angles.forEach((deg, i) => {
    const slider = document.getElementById('r' + i);
    const label = document.getElementById('v' + i);
    deg = clampDeg(i, deg);
    if (slider) slider.value = deg;
    if (label) label.textContent = deg + '°';
  });
}

function send(i, deg) {
  deg = clampDeg(i, deg);
  const slider = document.getElementById('r' + i);
  if (slider) slider.value = deg;
  fetch('/set?s=' + i + '&a=' + deg).catch(() => {});
  const label = document.getElementById('v' + i);
  if (label) label.textContent = deg + '°';
}

for (let i = 0; i < LABELS.length; i++) {
  const div = document.createElement('div');
  div.innerHTML =
    '<p>舵机 ' + LABELS[i] + '：<span id="v' + i + '">' + START[i] + '°</span><br/>' +
    '<input id="r' + i + '" type="range" min="0" max="' + SCALE[i] + '" value="' + START[i] + '"/></p>';
  box.appendChild(div);
  div.querySelector('input').oninput = (e) => send(i, +e.target.value);
}

const actionBtns = ['homeBtn', 'armBtn', 'nodBtn', 'peaceBtn', 'testBtn']
  .map(id => document.getElementById(id));

async function callApi(path, okText, failText) {
  actionBtns.forEach(btn => { btn.disabled = true; });
  statusEl.textContent = ' …';
  try {
    apply(await (await fetch(path)).json());
    statusEl.textContent = ' ' + okText;
  } catch (e) {
    statusEl.textContent = ' ' + failText;
  } finally {
    actionBtns.forEach(btn => { btn.disabled = false; });
  }
}

document.getElementById('homeBtn').onclick = () => callApi('/home', '已归位', '归位失败');
document.getElementById('armBtn').onclick = () => callApi('/arm', '机械臂形态', '切换失败');
document.getElementById('nodBtn').onclick = () => callApi('/nod', '点头完成', '点头失败');
document.getElementById('peaceBtn').onclick = () => callApi('/peace', '比耶完成', '比耶失败');
document.getElementById('testBtn').onclick = () => callApi('/test', '自测完成', '自测失败');

fetch('/state').then(r => r.json()).then(apply).catch(() => {});
</script>
</body>
</html>
"""


def main():
    i2c = SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=400000)
    devices = i2c.scan()
    print("I2C 设备:", [hex(d) for d in devices])
    if PCA9685_ADDR not in devices:
        raise RuntimeError("未找到 PCA9685 (0x40)，请检查 SDA=21 / SCL=22 接线")

    pca = PCA9685(i2c, PCA9685_ADDR, PWM_FREQ)
    servos = [
        Servo(pca, SERVO_CHS[i], SERVO_HOME[i], SERVO_MAX[i]) for i in range(N)
    ]
    print("PCA9685 就绪，舵机通道 CH0～CH5")

    ip = connect_wifi(WIFI_SSID, WIFI_PASSWORD).ifconfig()[0]

    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", 80))
    server.listen(2)
    print("请在浏览器打开: http://%s/" % ip)

    while True:
        client, _addr = server.accept()
        try:
            req = client.recv(1024)
            if not req:
                continue
            parts = req.split(b"\r\n", 1)[0].decode().split()
            if len(parts) < 2:
                continue
            path, params = parse_url(parts[1])

            if path in ("/", "/index.html"):
                http_send(client, "200 OK", HTML)
            elif path == "/state":
                http_send(client, "200 OK", angles_json(servos), "application/json")
            elif path == "/set":
                try:
                    idx = int(params.get("s", "-1"))
                    ang = int(params.get("a", "90"))
                    if 0 <= idx < N:
                        servos[idx].set(ang)
                        http_send(client, "200 OK", '{"ok":1}', "application/json")
                    else:
                        http_send(client, "400 Bad Request", '{"ok":0}', "application/json")
                except ValueError:
                    http_send(client, "400 Bad Request", '{"ok":0}', "application/json")
            elif path == "/home":
                move_sequential(servos, HOME_BTN)
                http_send(client, "200 OK", angles_json(servos), "application/json")
            elif path == "/arm":
                move_sequential(servos, ARM_POSE)
                http_send(client, "200 OK", angles_json(servos), "application/json")
            elif path == "/nod":
                run_nod_mode(servos)
                http_send(client, "200 OK", angles_json(servos), "application/json")
            elif path == "/peace":
                run_peace_mode(servos)
                http_send(client, "200 OK", angles_json(servos), "application/json")
            elif path == "/test":
                run_self_test(servos)
                http_send(client, "200 OK", angles_json(servos), "application/json")
            else:
                http_send(client, "404 Not Found", "Not Found")
        except Exception as e:
            print("请求出错:", e)
        finally:
            try:
                client.close()
            except OSError:
                pass


main()

