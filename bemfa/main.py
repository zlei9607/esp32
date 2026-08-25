"""
ESP32 + 巴法云 MQTT 继电器控制

微信搜「巴法云」小程序，添加同主题名即可远程开关。

消息格式：收到 on / off 控制继电器
注意：状态上报必须发到 主题/up，不能发回原主题，否则会自己收到消息形成开关循环。
"""

import network
import time
from machine import Pin
from umqtt.simple import MQTTClient


# ---------- 填写你的配置 ----------

WIFI_SSID = ""
WIFI_PWD = ""

# 巴法云控制台 → 私钥（32 位字符串，当作 MQTT client_id）
BEMFA_UID = ""

# 开关类主题建议以 002 结尾；你当前主题是 006，也能收消息，但小程序类型可能不同
TOPIC = ""
MQTT_HOST = "bemfa.com"
MQTT_PORT = 9501

# ---------- 继电器（高电平触发）----------

RELAY_ON = 1
RELAY_OFF = 0
RELAY_PIN = 4

relay = Pin(RELAY_PIN, Pin.OUT, value=RELAY_OFF)
mqtt_client = None


def log(msg):
    print(msg)


def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        log("连接 WiFi: " + WIFI_SSID)
        wlan.connect(WIFI_SSID, WIFI_PWD)
        for _ in range(40):
            if wlan.isconnected():
                break
            time.sleep(0.5)

    if wlan.isconnected():
        log("WiFi OK, IP: " + wlan.ifconfig()[0])
        return True

    log("WiFi 失败")
    return False


def set_relay(on):
    level = RELAY_ON if on else RELAY_OFF
    relay.value(level)
    log("继电器 {} (GPIO{}={})".format("开" if on else "关", RELAY_PIN, level))


def publish_state(on):
    """
    只更新云端显示，不推送给订阅者。
    必须用 主题/up，若发到原主题，自己又会收到 on/off → 继电器反复开关。
    """
    if mqtt_client:
        mqtt_client.publish(TOPIC + "/up", "on" if on else "off")


def on_message(topic, msg):
    cmd = msg.decode().strip().lower()
    log("收到 [{}]: {}".format(topic, cmd))

    if cmd == "on":
        set_relay(True)
        publish_state(True)
    elif cmd == "off":
        set_relay(False)
        publish_state(False)
    else:
        log("未知指令，只支持 on / off")


def mqtt_start():
    global mqtt_client

    log("连接巴法云 MQTT...")
    # 私钥作 client_id，用户名密码留空
    client = MQTTClient(BEMFA_UID, MQTT_HOST, MQTT_PORT)
    client.set_callback(on_message)
    client.connect()
    client.subscribe(TOPIC)
    log("已订阅主题: " + TOPIC)

    mqtt_client = client
    return client


def main():
    global mqtt_client

    log("=== ESP32 巴法云继电器 ===")

    if not wifi_connect():
        return

    while True:
        client = None
        try:
            client = mqtt_start()
            log("等待小程序下发 on / off ...")
            while True:
                client.check_msg()
                time.sleep(0.2)
        except Exception as e:
            log("MQTT 异常: " + repr(e))
        finally:
            mqtt_client = None
            if client:
                try:
                    client.disconnect()
                except Exception:
                    pass
            log("5 秒后重连...")
            time.sleep(5)


main()

