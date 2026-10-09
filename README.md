# CYD Thai Lunar Calendar

ปฏิทินจันทรคติไทย + วันพระ บนบอร์ด CYD (ESP32 + ILI9341) ด้วย MicroPython + LVGL9

![screenshot](20261009_105122.jpg)

## Files

- `lunar_calendar.py` — แอปหลัก (UI ปฏิทิน, WiFi/NTP sync เวลา, ธีมสี)
- `thai_lunar.py` — คำนวณจันทรคติไทย/วันพระ
- `synctime.py` — sync เวลาอย่างเดียว (ใช้หลังไฟดับ)
- `main.py` — autorun ตอนบูต (กัน boot-loop)
- `disp_test.py` — เทสต์จออย่างเดียว
- `thai15.bin` — ฟอนต์ไทยสำหรับ LVGL (build จาก `NotoSansThai-Bold.ttf` ด้วย `lv_font_conv`)
- `config_example.py` — ก็อปเป็น `config.py` แล้วใส่ WiFi ของตัวเอง (`config.py` ไม่ขึ้น git)

## Run on board

อัปโหลด `lunar_calendar.py` + `thai_lunar.py` + `thai15.bin` + `config.py` ขึ้นบอร์ด แล้วใน Shell พิมพ์ `import lunar_calendar`
