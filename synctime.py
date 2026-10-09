# synctime.py — sync เวลา CYD แบบ standalone (ไม่แตะ LVGL/jog เลย กิน RAM น้อย)
# ใช้ครั้งแรกหลังไฟดับ / RTC เพี้ยน: ใน Shell พิมพ์ `import synctime`
# เสร็จแล้วค่อย `import lunar_calendar` (RTC ยังจำเวลาได้ จะข้าม wifi เอง)
# ตั้ง wifi ใน config.py (ก็อปจาก config_example.py), NTP: pool.ntp.org, +7 ชม.

import time
import machine

# WiFi ดูค่าจาก config.py ก่อน (ไม่ขึ้น git), ดูตัวอย่างที่ config_example.py
WIFI_SSID = "YOUR_SSID"
WIFI_PASS = "YOUR_PASSWORD"
NTP_HOST = "pool.ntp.org"
NTP_PORT = 123
TIME_HOST = "akkasua.3bbddns.com"
TIME_PORT = 57862
TIME_PATH = "/unixtime.php"
TZ_HOURS = 7
try:
    import config as _cfg
    WIFI_SSID = getattr(_cfg, "WIFI_SSID", WIFI_SSID)
    WIFI_PASS = getattr(_cfg, "WIFI_PASS", WIFI_PASS)
except ImportError:
    pass


def wifi_connect(ssid=WIFI_SSID, pwd=WIFI_PASS, timeout_s=15):
    try:
        import network
    except ImportError:
        print("no network module, skip wifi")
        return False
    import time as _t
    sta = network.WLAN(network.STA_IF)
    try:
        sta.active(True)
    except Exception as e:
        print("wlan active fail:", e)
    if sta.isconnected():
        print("wifi already:", sta.ifconfig())
        return True
    print("wifi connect:", ssid)
    try:
        sta.connect(ssid, pwd)
    except Exception as e:
        print("wifi connect fail:", e)
        return False
    for _ in range(timeout_s * 10):
        if sta.isconnected():
            print("wifi ok:", sta.ifconfig())
            return True
        _t.sleep_ms(100)
    print("wifi timeout, not connected")
    return False


def _parse_unixtime(txt):
    s = "".join(ch for ch in str(txt) if ch.isdigit())
    return int(s) if s else None


def _ntp_time(timeout_s=8):
    try:
        import socket
        import struct
    except ImportError as e:
        print("ntp import fail:", e)
        return None
    try:
        addr = socket.getaddrinfo(NTP_HOST, NTP_PORT)[0][-1]
        so = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            so.settimeout(timeout_s)
            pkt = bytearray(48)
            pkt[0] = 0x1B
            so.sendto(pkt, addr)
            data, _ = so.recvfrom(48)
        finally:
            try:
                so.close()
            except Exception:
                pass
        if len(data) < 48:
            print("ntp short reply")
            return None
        secs = struct.unpack("!I", data[40:44])[0]
        return secs - 2208988800
    except Exception as e:
        print("ntp fail:", e)
        return None


def _http_get_unixtime():
    try:
        import socket
        addr = socket.getaddrinfo(TIME_HOST, TIME_PORT)[0][-1]
        so = socket.socket()
        so.settimeout(10)
        so.connect(addr)
        so.send(b"GET " + TIME_PATH.encode() + b" HTTP/1.0\r\nHost: " +
                TIME_HOST.encode() + b"\r\nConnection: close\r\n\r\n")
        buf = b""
        while True:
            chunk = so.recv(256)
            if not chunk:
                break
            buf += chunk
        so.close()
        body = buf.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in buf else buf
        return _parse_unixtime(body.decode().strip())
    except Exception as e:
        print("socket http fail:", e)
        return None


def sync_time():
    ts = _ntp_time()
    src = "ntp"
    if ts is None:
        print("ntp fail, try http")
        ts = _http_get_unixtime()
        src = "http"
    if not ts:
        print("time sync fail, keep RTC")
        return False
    try:
        try:
            diff = 946684800 if time.localtime(0)[0] == 2000 else 0
        except Exception:
            diff = 946684800
        t = time.localtime(ts + TZ_HOURS * 3600 - diff)
        try:
            machine.RTC().datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
        except Exception as e:
            print("rtc set fail:", e)
            return False
        print("time sync ok [%s]: %d-%02d-%02d %02d:%02d:%02d (+%d)" %
              (src, t[0], t[1], t[2], t[3], t[4], t[5], TZ_HOURS))
        return True
    except Exception as e:
        print("time sync err:", e)
        return False


print("RTC now:", time.localtime()[:6])
ok = False
if wifi_connect():
    ok = sync_time()
else:
    print("skip time sync (no wifi)")
if ok:
    # รีบูตเพื่อคืน heap สะอาด (RTC จำเวลาข้ามรีบูต) แล้วค่อยรันปฏิทิน
    print("rebooting for clean heap... then run: import lunar_calendar")
    time.sleep(1)
    machine.reset()
else:
    print("sync failed, NOT rebooting. fix wifi then run: import synctime")
