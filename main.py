# main.py — รันปฏิทินจันทรคติอัตโนมัติตอนบูต (boot.py ห้ามแตะ: มีไว้ตั้งค่าพื้นฐาน)
# มีการ์ดกัน boot-loop: ถ้าบูตแล้วพังเกิน 3 ครั้งติด (ตัวนับใน RTC memory)
# จะข้าม autorun ให้รันเองด้วย `import lunar_calendar`
# หมายเหตุ: หลังไฟดับครั้งแรกจะ sync เวลา + รีบูตเอง 1 รอบ แล้วปฏิทินขึ้นเอง

import machine

_n = 0
try:
    _mem = machine.RTC().memory()
    _n = _mem[0] if _mem else 0
except Exception:
    _n = 0

if _n >= 3:
    print("main: skip autorun (crashed %d times), run manually: import lunar_calendar" % _n)
else:
    try:
        machine.RTC().memory(bytes([_n + 1]))
    except Exception:
        pass
    import lunar_calendar
