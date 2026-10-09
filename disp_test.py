# disp_test.py — ทดสอบจอ CYD อย่างเดียว (ไม่ใช้ wifi/ฟอนต์/UI: ใช้ RAM น้อยสุด)
# วิธีใช้: ถอดเสียบไฟบอร์ดก่อน 1 ครั้ง แล้วใน Shell พิมพ์ `import disp_test`
# ผลที่ควรได้: จอแดงทั้งจอ + log "disp_test: RED"
# ถ้า Guru/ฟ้าค้างเหมือนเดิม = บั๊กที่ firmware (SPI.Bus) ต้องแฟลชเฟิร์มแวร์ใหม่

from micropython import const
import lvgl as lv
import machine, lcd_bus, ili9341
import task_handler

print("disp_test: init display bus...")
spi_bus = machine.SPI.Bus(host=1, mosi=13, miso=12, sck=14)
print("disp_test: bus ok")
display_bus = lcd_bus.SPIBus(spi_bus=spi_bus, freq=24000000, dc=2, cs=15)
print("disp_test: display_bus ok")

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
print("disp_test: display init ok")

th = task_handler.TaskHandler()

scr = lv.screen_active()
scr.clean()
scr.set_style_bg_color(lv.color_hex(0xFF0000), 0)
print("disp_test: RED screen should show")
