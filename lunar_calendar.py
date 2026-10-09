# lunar_calendar.py — CYD MicroPython + LVGL9 ปฏิทินจันทรคติ / วันพระ
# Display config มาจาก ../lvgl_final.py (ILI9341 RGB SWAP1 ROT0 320x240, 24MHz)
# เริ่มแสดง "เดือนปัจจุบันก่อน" (จาก time.localtime(), fallback Oct 2026)
# mark วันพระ: พื้นเหลือง + "*"
#
# ฟอนต์ไทย: เฟิร์มแวร์นี้ไม่มี tiny_ttf -> อยากได้ UI ไทยต้องสร้าง thai15.bin
#   (lv_font_conv --size 15 --format bin --bpp 4 --no-compress
#    --font NotoSansThai-Bold.ttf --range 0x20-0x7E,0x0E00-0x0E7F -o thai15.bin)
#   แล้วอัปโหลดไว้ที่ root คู่กับไฟล์นี้ UI จะเป็นไทย (MON_TH/WD_TH/ขึ้น/แรม) ทั้งหมด
#   ถ้าไม่มี thai15.bin จะ fallback อังกฤษอัตโนมัติ (อ่านได้ ไม่เป็นกล่องสี่เหลี่ยม)
#   โหลดแบบ tiny_ttf_create_data: อ่านไฟล์ 47KB เข้า RAM ครั้งเดียว ไม่ต้องใช้ fs_driver
#
# WiFi (ตั้งใน config.py) + sync เวลา NTP (+7 ชม.)
#
# วิธีรันบน CYD: อัปโหลด thai_lunar.py + lunar_calendar.py + NotoSansThai-Bold.ttf
#   แล้ว `import lunar_calendar`
# วันพระ = ขึ้น/แรม 8 ค่ำ และ 15 ค่ำ (เดือนละ 4 วัน) ตาม thai_lunar.php

from micropython import const
import lvgl as lv
import machine, lcd_bus, ili9341
import time
import gc
# หมายเหตุ: xpt2046/task_handler/thai_lunar import หลัง display init
# (จอต้องได้ heap สดที่สุด เทียบเท่า disp_test ที่รันผ่าน)

# ================= ตั้งค่า (แก้ตรงนี้ที่เดียว) =================
# ถ้ามีไฟล์ config.py (อยู่ใน .gitignore ไม่ขึ้น GitHub) จะใช้ค่าจากนั้นแทน
# ดูตัวอย่างได้ที่ config_example.py
WIFI_SSID = "YOUR_SSID"          # ชื่อ wifi
WIFI_PASS = "YOUR_PASSWORD"      # รหัส wifi
NTP_HOST = "pool.ntp.org"    # เซิร์ฟเวอร์เวลา (NTP)
NTP_PORT = 123
TIME_HOST = "akkasua.3bbddns.com"  # fallback http ถ้า NTP โดนบล็อก
TIME_PORT = 57862
TIME_PATH = "/unixtime.php"
TZ_HOURS = 7                 # โซนเวลาไทย (+7)
THEME = 0                    # ธีมสี: 0 ดำ / 1 น้ำเงินเข้ม / 2 ขาว
# ==============================================================
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
    # รับเฉพาะตัวเลข (เผื่อ php ส่ง whitespace/html ปนมา)
    s = "".join(ch for ch in str(txt) if ch.isdigit())
    return int(s) if s else None

def _ntp_time(timeout_s=5):
    # NTP เบากว่า http มาก: UDP packet 48 bytes, ใช้แค่ socket+struct (builtin)
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
        return secs - 2208988800  # epoch 1900 -> 1970 (unix time)
    except Exception as e:
        print("ntp fail:", e)
        return None

def _http_get_unixtime():
    # fallback http ด้วย socket ดิบ (ไม่ใช้ urequests: กิน RAM เกิน)
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
        ts = _parse_unixtime(body.decode().strip())
        return ts
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
        # epoch ของบอร์ดนี้เริ่ม 2000-01-01 (localtime(0) -> 2000) ไม่ใช่ 1970
        # ต้องลบ 946684800 ก่อนเรียก localtime ไม่งั้นปีจะเพี้ยน +30 (เช่น 2056)
        try:
            diff = 946684800 if time.localtime(0)[0] == 2000 else 0
        except Exception:
            diff = 946684800
        ts_local = ts + TZ_HOURS * 3600 - diff
        t = time.localtime(ts_local)
        # machine.RTC: (y,m,d,weekday,h,min,s,ms), weekday Mon=0
        try:
            rtc = machine.RTC()
            rtc.datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
        except Exception as e:
            print("rtc set fail:", e)
            return False
        print("time sync ok [%s]: ts=%d -> %d-%02d-%02d %02d:%02d:%02d (+%d)" %
              (src, ts, t[0], t[1], t[2], t[3], t[4], t[5], TZ_HOURS))
        return True
    except Exception as e:
        print("time sync err:", e)
        return False

# NOTE: sync เวลาก่อน init จอ เฉพาะเมื่อ RTC เพี้ยน (กัน C init จอชนกับงาน network)
# ถ้า RTC ดีอยู่แล้วข้าม wifi ไปเลย: จอ+UI ต้องการ heap สด (wifi ทิ้งไว้กิน RAM)

def rtc_sane():
    try:
        y = time.localtime()[0]
        return 2024 <= y <= 2040
    except Exception:
        return False

if not rtc_sane():
    try:
        import gc
        gc.collect()
        _synced = False
        if wifi_connect():
            _synced = bool(sync_time())
            try:  # ปิด radio ก่อนรีบูต ไม่งั้น state ค้างข้าม reset แล้ว SPI จอ init ไม่ผ่าน (259)
                import network
                _sta = network.WLAN(network.STA_IF)
                try:
                    if _sta.isconnected():
                        _sta.disconnect()
                except Exception:
                    pass
                try:
                    if _sta.active():
                        _sta.active(False)
                except Exception:
                    pass
            except Exception:
                pass
            gc.collect()
        else:
            print("skip time sync (no wifi)")
        if _synced:
            # จอ+UI ต้องการ RAM มาก อยู่ร่วม session กับ wifi ไม่ได้:
            # รีบูตเอา heap สะอาด (RTC จำเวลาข้ามรีบูต) แล้วรันปฏิทินใหม่
            print("time synced, rebooting for clean heap...")
            print("after reboot run: import lunar_calendar")
            time.sleep(1)
            machine.reset()
    except Exception as e:
        print("wifi/sync block fail (ignored):", e)
else:
    # RTC ดีอยู่แล้ว: ข้าม wifi ทั้งหมด (ไม่ import network / ไม่แตะ radio)
    # เพื่อให้ heap ก่อน init จอสะอาดที่สุด (พิสูจน์แล้วว่าแบบนี้รันผ่าน)
    _t = time.localtime()
    print("RTC ok %d-%02d-%02d, skip wifi" % (_t[0], _t[1], _t[2]))
    gc.collect()

# ---------- display init (copy จาก ../lvgl_final.py, ห้ามแก้ค่านอกเหนือนี้) ----------
spi_bus = machine.SPI.Bus(host=1, mosi=13, miso=12, sck=14)
display_bus = lcd_bus.SPIBus(spi_bus=spi_bus, freq=24000000, dc=2, cs=15)

indev_bus = machine.SPI.Bus(host=2, mosi=32, miso=39, sck=25)
indev_dev = machine.SPI.Device(spi_bus=indev_bus, freq=2000000, cs=33)

display = ili9341.ILI9341(
    data_bus=display_bus,
    display_width=320,
    display_height=240,
    backlight_pin=21,
    backlight_on_state=ili9341.STATE_PWM,
    color_space=lv.COLOR_FORMAT.RGB565,
    color_byte_order=ili9341.BYTE_ORDER_RGB,
    rgb565_byte_swap=True,
)
display._ORIENTATION_TABLE = (128, 224, 64, 32)
display.set_rotation(lv.DISPLAY_ROTATION._0)
display.set_power(True)
display.init(1)
display.set_backlight(100)

import xpt2046
indev = xpt2046.XPT2046(device=indev_dev)
# if not indev.is_calibrated:
#     indev.calibrate()

import task_handler
th = task_handler.TaskHandler()
# ---------- end display init ----------

import thai_lunar as TL
try:
    TL._starts()  # warmup cache ตารางจันทรคติตอน heap สด กัน alloc ไม่ผ่านตอน redraw
    gc.collect()
except Exception as e:
    print("lunar warmup fail:", e)

# ---------- โหลดฟอนต์ไทย (3 ระดับ) ----------
# 1) tiny_ttf_create_data (ถ้าเฟิร์มแวร์มี)  2) thai15.bin ผ่าน lv.binfont_create
#    (เฟิร์มแวร์นี้ไม่มี tiny_ttf -> ต้องใช้ .bin)  3) ไม่มีฟอนต์ = อังกฤษ (ไม่โชว์กล่อง)
# สร้าง thai15.bin บน PC (มี node): lv_font_conv --size 15 --format bin --bpp 4
#   --no-compress --font NotoSansThai-Bold.ttf --range 0x20-0x7E,0x0E00-0x0E7F
#   -o thai15.bin แล้วอัปโหลดไว้ที่ root คู่กับไฟล์นี้
FONT_TH = None
USE_THAI = False
_ttf_data = None  # เก็บ buffer ไว้ห้ามปล่อย (tiny_ttf ใช้อ้างอิงตลอด)
_fs_reg = False

def _reg_fs():
    global _fs_reg
    if _fs_reg:
        return True
    try:
        import fs_driver
        drv = lv.fs_drv_t()
        fs_driver.fs_register(drv, 'S')
        _fs_reg = True
        return True
    except Exception as e:
        print("fs register fail:", e)
        return False

def load_thai_font():
    global FONT_TH, USE_THAI, _ttf_data
    import gc
    try:
        # --- ระดับ 1: tiny_ttf (ถ้ามีในเฟิร์มแวร์) ---
        create = getattr(lv, "tiny_ttf_create_data", None)
        if create is not None:
            for p in ("NotoSansThai-Bold.ttf", "/NotoSansThai-Bold.ttf",
                      "lunar_calendar/NotoSansThai-Bold.ttf"):
                try:
                    with open(p, "rb") as f:
                        _ttf_data = f.read()
                    print("thai font file:", p, len(_ttf_data), "bytes")
                    break
                except OSError:
                    continue
            if _ttf_data:
                gc.collect()
                FONT_TH = create(_ttf_data, len(_ttf_data), 15)
                if FONT_TH is not None:
                    USE_THAI = True
                    print("thai font: tiny_ttf OK")
                    return
                print("tiny_ttf create fail, try binfont")
                _ttf_data = None
                gc.collect()
        else:
            print("no tiny_ttf in firmware, try binfont")
        # --- ระดับ 2: binfont thai15.bin (ประหยัด RAM กว่า ttf มาก) ---
        if _reg_fs():
            for p in ("S:/thai15.bin", "S:thai15.bin"):
                try:
                    f = lv.binfont_create(p)
                except Exception as e:
                    print("binfont", p, "err:", e)
                    continue
                if f is not None:
                    FONT_TH = f
                    USE_THAI = True
                    print("thai font: binfont OK", p)
                    return
                print("binfont", p, "-> None")
        print("thai font: not found -> English fallback (no boxes)")
    except Exception as e:
        print("thai font fail:", e, "-> English fallback")
        FONT_TH = None
        USE_THAI = False

load_thai_font()

def F(lbl):
    if FONT_TH:
        lbl.set_style_text_font(FONT_TH, 0)
    return lbl

# ---------- สตริงอังกฤษ / ไทย (ไทยใช้เมื่อโหลดฟอนต์สำเร็จ) ----------
MON_EN = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
WD_EN = ("Su", "Mo", "Tu", "We", "Th", "Fr", "Sa")
MON_TH = ("", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
          "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.")
GREG_TH = ("", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
           "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม")
WD_TH = ("อา", "จ", "อ", "พ", "พฤ", "ศ", "ส")
WD_FULL_TH = ("จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์")

# ---------- ธีมสี (เลือกด้วย THEME บนสุดของไฟล์) ----------
_THEMES = (
    {"bg": 0x000000, "cell": 0x222222, "dim": 0x555555, "phra": 0xFFD800,
     "today": 0x00FFFF, "sel": 0x00FF00, "sun": 0xFF6060,
     "white": 0xFFFFFF, "black": 0x000000, "detail": 0xFFFF00, "sub": 0x00FFFF},
    {"bg": 0x000A1A, "cell": 0x12325E, "dim": 0x5A7BA6, "phra": 0xFFD800,
     "today": 0x00FFFF, "sel": 0x00FF00, "sun": 0xFF8080,
     "white": 0xFFFFFF, "black": 0x000000, "detail": 0xFFE45E, "sub": 0x7FD4FF},
    {"bg": 0xFFFFFF, "cell": 0xE8E8E8, "dim": 0x999999, "phra": 0xFFB300,
     "today": 0x0080FF, "sel": 0x00A000, "sun": 0xFF0000,
     "white": 0x000000, "black": 0xFFFFFF, "detail": 0x7A5C00, "sub": 0x0066CC},
)
_T = _THEMES[THEME] if 0 <= THEME < len(_THEMES) else _THEMES[0]
C_BG = lv.color_hex(_T["bg"])
C_CELL = lv.color_hex(_T["cell"])
C_DIM = lv.color_hex(_T["dim"])
C_PHRA = lv.color_hex(_T["phra"])     # วันพระ
C_TODAY = lv.color_hex(_T["today"])   # ขอบ = วันนี้
C_SEL = lv.color_hex(_T["sel"])       # ขอบ = วันที่เลือก
C_SUN = lv.color_hex(_T["sun"])
C_WHITE = lv.color_hex(_T["white"])   # สีตัวหนังสือหลัก
C_BLACK = lv.color_hex(_T["black"])   # สีตัวหนังสือบนพื้นวันพระ
C_DETAIL = lv.color_hex(_T["detail"])
C_SUB = lv.color_hex(_T["sub"])
del _THEMES, _T

def now_ymd():
    t = time.localtime()
    y, m, d = t[0], t[1], t[2]
    if y < 2020 or y > 2035:  # RTC ยังไม่ตั้ง / NTP ยังไม่ sync
        y, m, d = 2026, 10, 8
    return y, m, d

TODAY_Y, TODAY_M, TODAY_D = now_ymd()
state = {"y": TODAY_Y, "m": TODAY_M, "sel": TODAY_D}

try:
    import gc
    gc.collect()  # เคลียร์ heap ก่อนสร้างวิดเจ็ต ~100 ตัว
except Exception:
    pass
scr = lv.screen_active()
scr.clean()
scr.set_style_bg_color(C_BG, 0)
scr.set_style_pad_all(0, 0)
scr.set_style_border_width(0, 0)

# --- header: [<] [T] [ title ] [>] ---
btn_prev = lv.button(scr)
btn_prev.set_size(34, 24)
btn_prev.set_pos(4, 4)
F(lv.label(btn_prev)).set_text("<")
btn_prev.get_child(0).center()

btn_today = lv.button(scr)
btn_today.set_size(30, 24)
btn_today.set_pos(42, 4)
F(lv.label(btn_today)).set_text("T")
btn_today.get_child(0).center()

btn_next = lv.button(scr)
btn_next.set_size(34, 24)
btn_next.set_pos(282, 4)
F(lv.label(btn_next)).set_text(">")
btn_next.get_child(0).center()

title_lbl = F(lv.label(scr))
title_lbl.set_size(204, 24)
title_lbl.set_pos(74, 4)
title_lbl.set_style_text_color(C_WHITE, 0)
title_lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

# --- แถววันในสัปดาห์ (ไทยเมื่อมีฟอนต์ ไม่งั้นอังกฤษ ไม่โชว์กล่อง) ---
WD = WD_TH if USE_THAI else WD_EN
for c in range(7):
    w = F(lv.label(scr))
    w.set_size(44, 14)
    w.set_pos(6 + c * 44, 32)
    w.set_text(WD[c])
    w.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    w.set_style_text_color(C_SUN if c == 0 else C_WHITE, 0)

# --- ตารางวัน 7x6 (สร้างครั้งเดียว reuse) ---
# ใช้ label + CLICKABLE แทน button (เบากว่าครึ่ง: ไม่ต้องมี label ลูกอีกชั้น)
GX0, GY0, CW, CH = 6, 48, 44, 20
cells = []  # (lbl, day|0)
for r in range(6):
    for c in range(7):
        lb = F(lv.label(scr))
        lb.set_size(42, 18)
        lb.set_pos(GX0 + c * CW, GY0 + r * CH)
        lb.set_style_bg_color(C_CELL, 0)
        lb.set_style_bg_opa(lv.OPA.COVER, 0)
        lb.set_style_border_width(0, 0)
        lb.set_style_pad_all(0, 0)
        lb.set_style_pad_top(1, 0)
        lb.set_style_radius(3, 0)
        lb.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        lb.add_flag(lv.obj.FLAG.CLICKABLE)
        cells.append([lb, 0])

# --- รายละเอียด + คำอธิบาย ---
detail_lbl = F(lv.label(scr))
detail_lbl.set_size(312, 36)
detail_lbl.set_pos(4, 186)
detail_lbl.set_style_text_color(C_DETAIL, 0)
detail_lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

legend_lbl = F(lv.label(scr))
legend_lbl.set_size(312, 15)
legend_lbl.set_pos(4, 223)
legend_lbl.set_text("* = วันพระ (ขึ้น/แรม 8,15 ค่ำ)" if USE_THAI
                    else "* = Wan Phra (K8/K15/R8/R15) | tap day")
legend_lbl.set_style_text_color(C_DIM, 0)
legend_lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

def show_detail(y, m, d):
    if USE_THAI:
        phase, khaat, lm, ex, _off, idx = TL.lunar(y, m, d)
        wd = WD_FULL_TH[TL.weekday_mon0(y, m, d)]
        line1 = "%d %s %d (%s)" % (d, GREG_TH[m], y + 543, wd)
        line2 = TL.label_th(y, m, d)
        nm = TL.holy_name_th(phase, khaat, lm, ex, idx)
        if nm:
            line2 += " " + nm
        detail_lbl.set_text(line1 + "\n" + line2)
        print(line1 + " " + line2)
    else:
        # fallback ฟอนต์ LVGL  built-in ไม่มีไทย -> ใช้ ASCII ล้วน (อ่านได้ ไม่เป็นกล่อง)
        phase, khaat, lm, ex, holy, name = TL.info(y, m, d)
        p = "Khuen" if phase == 0 else "Raem"
        s = "%d %s: %s %d Kh%d%s" % (d, MON_EN[m], p, khaat, lm, "L" if ex else "")
        if holy:
            s += " *PHRA*"
            if name:
                s += " " + name
        detail_lbl.set_text(s)
        print(s)

def redraw():
    try:
        import gc
        gc.collect()  # เคลียร์ก่อนคำนวณวาดใหม่ (กัน heap แตก)
    except Exception:
        pass
    y, m = state["y"], state["m"]
    dim = TL.days_in_month(y, m)
    # คอลัมน์ของวันที่ 1 (Su=0..Sa=6)
    start_col = (TL.weekday_mon0(y, m, 1) + 1) % 7
    # วันเดือนก่อนหน้ามาเติมช่องว่าง
    pm = m - 1 if m > 1 else 12
    py = y if m > 1 else y - 1
    prev_dim = TL.days_in_month(py, pm)

    holy = TL.holy_days_in_month(y, m)  # [(day,phase,khaat,lm,ex,name)]
    holy_set = {}
    for (dd, ph, kh, lmo, exx, nm) in holy:
        holy_set[dd] = (ph, kh, nm)

    # หัว: ชื่อเดือนเต็ม + เวลาปัจจุบัน (label เดียวกัน, เว้น 2 ช่อง)
    update_title()
    phra_txt = ",".join(str(dd) for (dd, _, _, _, _, _) in holy)
    print("show %d-%02d holy=%s" % (y, m, phra_txt))

    sel = state["sel"]
    for i in range(42):
        lb = cells[i][0]
        d = i - start_col + 1
        if 1 <= d <= dim:
            is_phra = d in holy_set
            lb.set_text(("*%d" % d) if is_phra else str(d))
            lb.set_style_text_color(C_BLACK if is_phra else (C_SUN if (i % 7 == 0) else C_WHITE), 0)
            lb.set_style_bg_color(C_PHRA if is_phra else C_CELL, 0)
            # border: วันนี้ขอบฟ้า / วันที่เลือกขอบเขียว
            if y == TODAY_Y and m == TODAY_M and d == TODAY_D and d == sel:
                lb.set_style_border_width(2, 0)
                lb.set_style_border_color(C_SEL, 0)
            elif y == TODAY_Y and m == TODAY_M and d == TODAY_D:
                lb.set_style_border_width(2, 0)
                lb.set_style_border_color(C_TODAY, 0)
            elif d == sel:
                lb.set_style_border_width(2, 0)
                lb.set_style_border_color(C_SEL, 0)
            else:
                lb.set_style_border_width(0, 0)
            cells[i][1] = d
        else:
            # filler จากเดือนข้างเคียง (ตัวเลขจาง)
            fd = prev_dim + d if d < 1 else d - dim
            lb.set_text(str(fd))
            lb.set_style_text_color(C_DIM, 0)
            lb.set_style_bg_color(C_BG, 0)
            lb.set_style_border_width(0, 0)
            cells[i][1] = 0

    if sel and 1 <= sel <= dim:
        show_detail(y, m, sel)

# callback เดียวทั้งตาราง (ไม่สร้าง closure 42 ตัว: ประหยัด RAM)
def _on_cell(e):
    tgt = e.get_target()
    for j in range(42):
        if cells[j][0] == tgt:
            if cells[j][1]:
                state["sel"] = cells[j][1]
                redraw()
            break

for i in range(42):
    cells[i][0].add_event_cb(_on_cell, lv.EVENT.CLICKED, None)

def on_prev(e):
    y, m = state["y"], state["m"]
    m -= 1
    if m < 1:
        m, y = 12, y - 1
    state["y"], state["m"] = y, m
    state["sel"] = min(state["sel"], TL.days_in_month(y, m))
    redraw()

def on_next(e):
    y, m = state["y"], state["m"]
    m += 1
    if m > 12:
        m, y = 1, y + 1
    state["y"], state["m"] = y, m
    state["sel"] = min(state["sel"], TL.days_in_month(y, m))
    redraw()

def on_today(e):
    state["y"], state["m"], state["sel"] = TODAY_Y, TODAY_M, TODAY_D
    redraw()

btn_prev.add_event_cb(lambda e: on_prev(e), lv.EVENT.CLICKED, None)
btn_next.add_event_cb(lambda e: on_next(e), lv.EVENT.CLICKED, None)
btn_today.add_event_cb(lambda e: on_today(e), lv.EVENT.CLICKED, None)

def update_title():
    # ชื่อเดือนที่กำลังดู + เวลาปัจจุบัน (เช่น "ตุลาคม 2569  08:35")
    try:
        t = time.localtime()
        hh, mm = t[3], t[4]
    except Exception:
        hh, mm = 0, 0
    y, m = state["y"], state["m"]
    if USE_THAI:
        title_lbl.set_text("%s %d  %02d:%02d" % (GREG_TH[m], y + 543, hh, mm))
    else:
        title_lbl.set_text("%s %d  %02d:%02d" % (MON_EN[m], y, hh, mm))

def _title_tick(_timer):
    update_title()

# เริ่มที่เดือนปัจจุบันก่อน
redraw()
title_timer = lv.timer_create(_title_tick, 10000, None)  # รีเฟรชเวลาทุก 10 วิ
print("LVGL lunar calendar running: %d-%02d (today %d) thai=%s"
      % (state["y"], state["m"], TODAY_D, USE_THAI))

# รันถึงตรงนี้ = สำเร็จ: ล้างตัวนับ boot-loop ที่ main.py ใช้กันบูตวน
try:
    machine.RTC().memory(b"\x00")
except Exception:
    pass
