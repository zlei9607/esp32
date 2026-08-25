# ESP32 通过巴法云 MQTT 控制继电器，微信「巴法云」小程序远程开关

## 硬件清单

| 配件        | 购买 | 参考图                                                                     |
|-----------|------|-------------------------------------------------------------------------|
| ESP32 开发板 | [链接](https://e.tb.cn/h.8QnrIjBGCaL87kO?tk=NwqlT2GwiDR) | <img src="./img/image-20260825163926161.png" width="200">  |
| 继电器       | [链接](https://e.tb.cn/h.8lIGuOTV4FPgMWD?tk=dVonTWiJdj5) | <img src="./img/image-20260825181319322.png" width="200">  |
| LED灯      | [链接](https://e.tb.cn/h.8lIpkKmsfEYwvZx?tk=6t0uTWilKTg) | <img src="./img/image-20260825181319371.png" width="200">  |
| 220欧电阻    | [链接](https://e.tb.cn/h.8kXscWcM8sHhxPO?tk=bvvXTWimWnT) | <img src="./img/image-20260825181101168.png" width="200">! |
| 5V 电源 + 杜邦线 | [链接](https://e.tb.cn/h.8jMGqH3UVVq74ua?tk=vhmkT2ua5qC) | <img src="./img/image-20260825163926191.png" width="200">  |

## 环境搭建

[ESP32+Thonny+MicroPython环境搭建](ESP32+Thonny+MicroPython环境搭建.md)

## 快速开始

### 1. 接线图

这里用**5v电源+LED灯**模拟**家庭交流电+电灯**，交流电零线接继电器ON，火线接继电器COM。

![image-20260825173405863](img/image-20260825173405863.png)

| ESP32 | 继电器模块 |
|-------|-------|
| GPIO4 | IN    |
| 5V    | VCC   |
| GND   | GND   |

### 2. 注册巴法云

- 打开 [https://cloud.bemfa.com](https://cloud.bemfa.com) 注册并登录
- 进入 **控制台**，复制 **私钥**（一长串 32 位字符）
- 进入 **MQTT 设备云**，**新建设备**，选择设备类型，创建后复制主题名

  ![image-20260825163926156](img/image-20260825163926156.png)

### 3. 上传程序

- 编辑 `main.py`，填写以下信息

   ```
   WIFI_SSID = "你的WiFi"
   WIFI_PWD = "你的密码"
   BEMFA_UID = "控制台复制的私钥"
   TOPIC = "与控制台创建的主题名一致"
   ```
- 用 Thonny 上传到 ESP32 根目录为 `main.py`
- 代码地址 [https://github.com/zlei9607/esp32/tree/main/bemfa](https://github.com/zlei9607/esp32/tree/main/bemfa)


### 4. 微信小程序控制

- 微信搜索 **「巴法云」** 小程序
- 登录同一账号
- 界面上会出现开关按钮，点 **开/关** 即可

  <img src="./img/image-20260825174954387.png" width="250" alt="网页控制">

  小程序发 `on` / `off`，ESP32 收到后控制 GPIO4 继电器。