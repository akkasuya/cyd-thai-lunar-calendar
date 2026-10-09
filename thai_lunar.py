# thai_lunar.py — MicroPython port of thai_lunar.php
# ปฏิทินจันทรคติไทย: ตารางวันขึ้น 1 ค่ำ 8 ธ.ค. 2561 - 6 ธ.ค. 2572 (ตรงปฏิทินหลวง)
# นอกเขตตาราง: ประมาณด้วยหลักคี่-คู่ (อาจคลาด 1-2 วัน)
# วันพระ: ขึ้น/แรม 8 ค่ำ และ 15 ค่ำ + แรม 14 ค่ำของเดือนขาด (29 วัน ไม่มีแรม 15)
# (_holy_full/is_holy_day; ส่วน is_holy(khaat) เป็นเช็กดิบ 8/15 เก็บไว้เพื่อความเข้ากันได้)
# MicroPython: ใช้แต่ int + tuple, ไม่มี datetime/dict หนัก
# หมายเหตุ RAM: day-number เก็บเป็น array('l') (~600B) ไม่ใช้ list of tuples (~6KB)

from array import array

# (y, m, d, lunar_month, extra)
MONTH_STARTS = (
    (2018,12,8,1,0),(2019,1,6,2,0),(2019,2,5,3,0),(2019,3,6,4,0),
    (2019,4,5,5,0),(2019,5,4,6,0),(2019,6,3,7,0),(2019,7,2,8,0),
    (2019,8,1,9,0),(2019,8,30,10,0),(2019,9,29,11,0),(2019,10,28,12,0),
    (2019,11,27,1,0),(2019,12,26,2,0),(2020,1,25,3,0),(2020,2,23,4,0),
    (2020,3,24,5,0),(2020,4,22,6,0),(2020,5,22,7,0),(2020,6,21,8,0),
    (2020,7,21,9,0),(2020,8,19,10,0),(2020,9,18,11,0),(2020,10,17,12,0),
    (2020,11,16,1,0),(2020,12,15,2,0),(2021,1,14,3,0),(2021,2,12,4,0),
    (2021,3,14,5,0),(2021,4,12,6,0),(2021,5,12,7,0),(2021,6,10,8,0),
    (2021,7,10,8,1),(2021,8,9,9,0),(2021,9,7,10,0),(2021,10,7,11,0),
    (2021,11,5,12,0),(2021,12,5,1,0),(2022,1,3,2,0),(2022,2,2,3,0),
    (2022,3,3,4,0),(2022,4,2,5,0),(2022,5,1,6,0),(2022,5,31,7,0),
    (2022,6,29,8,0),(2022,7,29,9,0),(2022,8,27,10,0),(2022,9,26,11,0),
    (2022,10,25,12,0),(2022,11,24,1,0),(2022,12,23,2,0),(2023,1,22,3,0),
    (2023,2,20,4,0),(2023,3,22,5,0),(2023,4,20,6,0),(2023,5,20,7,0),
    (2023,6,18,8,0),(2023,7,18,8,1),(2023,8,17,9,0),(2023,9,15,10,0),
    (2023,10,15,11,0),(2023,11,13,12,0),(2023,12,13,1,0),(2024,1,11,2,0),
    (2024,2,10,3,0),(2024,3,10,4,0),(2024,4,9,5,0),(2024,5,8,6,0),
    (2024,6,7,7,0),(2024,7,6,8,0),(2024,8,5,9,0),(2024,9,3,10,0),
    (2024,10,3,11,0),(2024,11,1,12,0),(2024,12,1,1,0),(2024,12,30,2,0),
    (2025,1,29,3,0),(2025,2,27,4,0),(2025,3,29,5,0),(2025,4,27,6,0),
    (2025,5,27,7,0),(2025,6,26,8,0),(2025,7,26,9,0),(2025,8,24,10,0),
    (2025,9,23,11,0),(2025,10,22,12,0),(2025,11,21,1,0),(2025,12,20,2,0),
    (2026,1,19,3,0),(2026,2,17,4,0),(2026,3,19,5,0),(2026,4,17,6,0),
    (2026,5,17,7,0),(2026,6,15,8,0),(2026,7,15,8,1),(2026,8,14,9,0),
    (2026,9,12,10,0),(2026,10,12,11,0),(2026,11,10,12,0),(2026,12,10,1,0),
    (2027,1,8,2,0),(2027,2,7,3,0),(2027,3,8,4,0),(2027,4,7,5,0),
    (2027,5,6,6,0),(2027,6,5,7,0),(2027,7,4,8,0),(2027,8,3,9,0),
    (2027,9,1,10,0),(2027,10,1,11,0),(2027,10,30,12,0),(2027,11,29,1,0),
    (2027,12,28,2,0),(2028,1,27,3,0),(2028,2,25,4,0),(2028,3,26,5,0),
    (2028,4,24,6,0),(2028,5,24,7,0),(2028,6,22,8,0),(2028,7,22,9,0),
    (2028,8,20,10,0),(2028,9,19,11,0),(2028,10,18,12,0),(2028,11,17,1,0),
    (2028,12,16,2,0),(2029,1,15,3,0),(2029,2,13,4,0),(2029,3,15,5,0),
    (2029,4,13,6,0),(2029,5,13,7,0),(2029,6,11,8,0),(2029,7,11,8,1),
    (2029,8,10,9,0),(2029,9,8,10,0),(2029,10,8,11,0),(2029,11,6,12,0),
    (2029,12,6,1,0),
)

# ชื่อเดือนจันทรคติ (ASCII-safe สำหรับฟอนต์ LVGL ดีฟอลต์ที่ไม่มีภาษาไทย)
# ถ้ามีฟอนต์ไทย ให้ใช้ MONTH_NAMES_TH แทน
MONTH_NAMES_TH = (None,'อ้าย','ยี่','สาม','สี่','ห้า','หก','เจ็ด','แปด','เก้า','สิบ','สิบเอ็ด','สิบสอง')
MONTH_NAMES = (None,'Ai','Yi','Sam','Si','Ha','Hok','Chet','Paet','Kao','Sip','Sip-et','Sip-song')

# วันสำคัญที่มีชื่อ: (name_th, name_en, phase 0=Khuen 1=Raem, khaat, month, extra_only)
# extra_only=1 เช่น อาสาฬหฯ/เข้าพรรษา ใช้เดือน 8 หลังเมื่อปีนั้นมี 8 สองเดือน
# ปีอธิกมาส (เดือน 8 สองหน): มาฆบูชา ขึ้น 15 เดือน 3->4, วิสาขบูชา ขึ้น 15 เดือน 6->7
# (holy_name_* เลื่อนให้อัตโนมัติผ่าน _lunar_year_has_double8)
BUDDHIST_DAYS = (
    ('มาฆบูชา','Makha',0,15,3,0),
    ('วิสาขบูชา','Visakha',0,15,6,0),
    ('อาสาฬหบูชา','Asalha',0,15,8,1),
    ('เข้าพรรษา','Khao Phansa',1,1,8,1),
    ('ออกพรรษา','Ok Phansa',0,15,11,0),
)

def _lunar_year_has_double8(idx):
    # ปีจันทรคติ (เดือน 1..12) ที่มีเดือน idx นี้อยู่ มีเดือน 8 หลังหรือไม่
    # ใช้เลื่อนชื่อ มาฆบูชา (3->4) / วิสาขบูชา (6->7) ในปีอธิกมาส
    # หมายเหตุ: นอกเขตตาราง (idx ชนขอบ) เป็นค่าประมาณเช่นเดียวกับ lunar()
    n = len(MONTH_STARTS)
    if idx < 0:
        idx = 0
    elif idx >= n:
        idx = n - 1
    s = idx
    for _ in range(14):
        if MONTH_STARTS[s][3] == 1 and MONTH_STARTS[s][4] == 0:
            break
        if s == 0:
            break
        s -= 1
    e = idx
    for _ in range(16):
        if e + 1 >= n:
            break
        if MONTH_STARTS[e+1][3] == 1 and MONTH_STARTS[e+1][4] == 0:
            break
        e += 1
    for j in range(s, e + 1):
        if MONTH_STARTS[j][3] == 8 and MONTH_STARTS[j][4] == 1:
            return True
    return False

_START_DNUMS = None

def dnum(y, m, d):
    # day number (proleptic Gregorian, March-based) — ใช้ int ล้วน
    if m <= 2:
        y -= 1
        m += 12
    return 365*y + y//4 - y//100 + y//400 + (153*(m-3)+2)//5 + d - 1

def _starts():
    global _START_DNUMS
    if _START_DNUMS is None:
        _START_DNUMS = array('l', (dnum(y, m, d) for (y, m, d, _lm, _ex) in MONTH_STARTS))
    return _START_DNUMS

def is_leap(y):
    return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)

def days_in_month(y, m):
    if m == 2:
        return 29 if is_leap(y) else 28
    if m in (1,3,5,7,8,10,12):
        return 31
    return 30

def weekday_mon0(y, m, d):
    # Monday=0..Sunday=6 ; 1970-01-01 = Thursday(3)
    return (dnum(y,m,d) - dnum(1970,1,1) + 3) % 7

def _find_month(dn):
    s = _starts()
    # linear จากท้าย (เดือนปัจจุบันอยู่ท้ายตารางเสมอ)
    for i in range(len(s)-1, -1, -1):
        if dn >= s[i]:
            return i
    return 0

def lunar(y, m, d):
    # return (phase 0=Khuen/1=Raem, khaat, lunar_month, extra, offset, idx)
    dn = dnum(y,m,d)
    s = _starts()
    i = _find_month(dn)
    if i >= len(s)-1:
        # ท้ายตาราง: ประมาณความยาวเดือนด้วยหลักคี่-คู่ (คี่ 29 / คู่ 30)
        # ถ้า dn เกินเดือนสุดท้าย ให้เดินหน้าต่อ (รองรับหลัง ธ.ค. 2572 แบบประมาณ)
        lm = MONTH_STARTS[i][3]; ex = MONTH_STARTS[i][4]
        cur = s[i]
        while True:
            length = 29 if (lm % 2 == 1 and not ex) else 30
            # เดือนคู่ 30 วันสองครั้งติด = เดือนหลัง (ตรรกะเดียวกับ PHP)
            nxt_len = 29 if ((lm+1) % 2 == 1) else 30
            _ = nxt_len
            if dn < cur + length:
                break
            cur += length
            if lm % 2 == 0 and length == 30:
                # candidate: เดือนหลังของเดือนเดิม (เช็กแบบง่าย: ให้เดือนหลัง 1 ครั้งแล้วไปต่อ)
                # หมายเหตุ: นอกเขตตารางเป็นค่าประมาณ
                if not ex:
                    ex = 1
                else:
                    ex = 0
                    lm = lm % 12 + 1
            else:
                ex = 0
                lm = lm % 12 + 1
        return _pack(dn - cur, lm, ex, i)
    rec_dn = s[i]
    lm = MONTH_STARTS[i][3]; ex = MONTH_STARTS[i][4]
    return _pack(dn - rec_dn, lm, ex, i)

def _pack(offset, lm, ex, idx):
    if offset <= 14:
        return (0, offset+1, lm, ex, offset, idx)
    return (1, offset-14, lm, ex, offset, idx)

def is_holy(khaat):
    # เช็กดิบ: 8/15 ค่ำ (ไม่รวมแรม 14 เดือนขาด — ใช้ _holy_full/is_holy_day แทน)
    return khaat == 8 or khaat == 15

def _lunar_month_len(idx, lm, ex):
    # ความยาวเดือนจันทรคติ (วัน): ในตาราง = ผลต่างวันขึ้น 1 ค่ำ (รองรับเดือนผิดปกติเอง)
    # ท้ายตาราง = หลักคี่-คู่ (คี่ 29 / คู่ 30, เดือนหลังนับ 30)
    s = _starts()
    if 0 <= idx < len(s) - 1:
        return s[idx+1] - s[idx]
    return 29 if (lm % 2 == 1 and not ex) else 30

def _holy_full(phase, khaat, lm, ex, idx):
    # วันพระ: 8/15 ค่ำ + แรม 14 ค่ำของเดือนขาด (29 วัน)
    if khaat == 8 or khaat == 15:
        return True
    return phase == 1 and khaat == 14 and _lunar_month_len(idx, lm, ex) == 29

def is_holy_day(y, m, d):
    # วันพระหรือไม่ (รวมแรม 14 เดือนขาด) — ใช้แทน is_holy เมื่อมีวันที่ครบ
    phase, khaat, lm, ex, _off, idx = lunar(y, m, d)
    return _holy_full(phase, khaat, lm, ex, idx)

def holy_name_en(phase, khaat, lm, ex, idx):
    dbl8 = None
    for (_th, en, p, k, mo, extra_only) in BUDDHIST_DAYS:
        if mo == 3 or mo == 6:
            # ปีอธิกมาส: มาฆบูชา 3->4, วิสาขบูชา 6->7
            if dbl8 is None:
                dbl8 = _lunar_year_has_double8(idx)
            if dbl8:
                mo += 1
        if p == phase and k == khaat and mo == lm:
            if extra_only and not ex:
                # ถ้าปีนั้นมีเดือน 8 หลัง ต้องใช้เดือนหลังเท่านั้น
                s = _starts()
                nxt = MONTH_STARTS[idx+1] if idx+1 < len(s) else None
                if nxt and nxt[3] == 8 and nxt[4] == 1:
                    continue
            return en
    return None

def holy_name_th(phase, khaat, lm, ex, idx):
    dbl8 = None
    for (th, _en, p, k, mo, extra_only) in BUDDHIST_DAYS:
        if mo == 3 or mo == 6:
            # ปีอธิกมาส: มาฆบูชา 3->4, วิสาขบูชา 6->7
            if dbl8 is None:
                dbl8 = _lunar_year_has_double8(idx)
            if dbl8:
                mo += 1
        if p == phase and k == khaat and mo == lm:
            if extra_only and not ex:
                s = _starts()
                nxt = MONTH_STARTS[idx+1] if idx+1 < len(s) else None
                if nxt and nxt[3] == 8 and nxt[4] == 1:
                    continue
            return th
    return None

def info(y, m, d):
    phase, khaat, lm, ex, _off, idx = lunar(y,m,d)
    holy = _holy_full(phase, khaat, lm, ex, idx)
    return (phase, khaat, lm, ex, holy, holy_name_en(phase,khaat,lm,ex,idx))

def holy_days_in_month(y, m):
    # return list ของ (day, phase, khaat, lunar_month, extra, name_en)
    out = []
    for dd in range(1, days_in_month(y,m)+1):
        phase, khaat, lm, ex, _off, idx = lunar(y,m,dd)
        if _holy_full(phase, khaat, lm, ex, idx):
            out.append((dd, phase, khaat, lm, ex, holy_name_en(phase,khaat,lm,ex,idx)))
    return out

def label_en(y, m, d):
    # ASCII ล้วนสำหรับฟอนต์ LVGL built-in (ไม่มีไทย): "Raem 12 Kh10" / "Khuen 15 Kh11 *PHRA*"
    # (L ท้าย = เดือนหลัง, เทียบเท่า 'หลัง' ใน label_th)
    phase, khaat, lm, ex, _off, idx = lunar(y,m,d)
    p = 'Khuen' if phase == 0 else 'Raem'
    s = '%s %d Kh%d%s' % (p, khaat, lm, 'L' if ex else '')
    if _holy_full(phase, khaat, lm, ex, idx):
        s += ' *PHRA*'
    return s

def label_th(y, m, d):
    # ใช้เมื่อมีฟอนต์ไทยเท่านั้น
    phase, khaat, lm, ex, _off, idx = lunar(y,m,d)
    p = 'ขึ้น' if phase == 0 else 'แรม'
    s = '%s %d ค่ำ เดือน%s%s' % (p, khaat, MONTH_NAMES_TH[lm], 'หลัง' if ex else '')
    if _holy_full(phase, khaat, lm, ex, idx):
        s += ' (วันพระ)'
    return s
