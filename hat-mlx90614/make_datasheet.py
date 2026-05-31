"""Generate one-page product introduction PDF for the Lumina IR-1."""

from fpdf import FPDF
from fpdf.enums import XPos, YPos

class PDF(FPDF):
    def header(self): pass
    def footer(self): pass

pdf = PDF(orientation="P", unit="mm", format="A4")
pdf.add_page()
pdf.set_margins(0, 0, 0)
pdf.set_auto_page_break(False)

W, H = 210, 297
PAD = 20  # horizontal page padding

# Background — white for print
pdf.set_fill_color(255, 255, 255)
pdf.rect(0, 0, W, H, "F")

# Top accent bar
pdf.set_fill_color(255, 136, 0)
pdf.rect(0, 0, W, 4, "F")

# Product name
pdf.set_xy(0, 14)
pdf.set_font("Helvetica", "B", 38)
pdf.set_text_color(20, 20, 30)
pdf.cell(W, 12, "LUMINA IR-1", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

pdf.set_font("Helvetica", "", 12)
pdf.set_text_color(255, 136, 0)
pdf.cell(W, 6, "Contactless Infrared Thermometer  |  M5StickC Plus Edition", align="C",
         new_x=XPos.LMARGIN, new_y=YPos.NEXT)

# Divider
pdf.set_draw_color(200, 200, 210)
pdf.set_line_width(0.3)
pdf.line(PAD, 38, W - PAD, 38)

col_l  = PAD
col_r  = 120
row_top = 44

# --- Left column: features ---
pdf.set_xy(col_l, row_top)
pdf.set_font("Helvetica", "B", 9)
pdf.set_text_color(255, 136, 0)
pdf.cell(90, 5, "KEY FEATURES", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

features = [
    ("Non-contact measurement",  "Point and read - no skin contact required."),
    ("Dual-channel sensing",     "Object temp and ambient temp read simultaneously."),
    ("Color-coded range bar",    "Visual indicator spans the full -70 C to +380 C sensor range,\n"
                                 "segmented by zone: blue / teal / orange / red."),
    ("Celsius / Fahrenheit",     "Toggle units instantly with Button A."),
    ("Flicker-free display",     "Partial-update rendering - only changed pixels are redrawn."),
    ("FreeSans UI font",         "Proportional typography for a clean, modern readout."),
]

pdf.set_xy(col_l, pdf.get_y() + 3)
for title, desc in features:
    y = pdf.get_y()
    pdf.set_fill_color(255, 136, 0)
    pdf.ellipse(col_l, y + 1.8, 2, 2, "F")
    pdf.set_xy(col_l + 4, y)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 30, 40)
    pdf.cell(86, 5, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_xy(col_l + 4, pdf.get_y())
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(90, 90, 100)
    pdf.multi_cell(86, 4, desc, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_y(pdf.get_y() + 2)

# --- Right column: screen mockup ---
mx = col_r
my = row_top
mw = 44
mh = 78

# Bezel
pdf.set_fill_color(28, 28, 32)
pdf.set_draw_color(80, 80, 90)
pdf.set_line_width(0.5)
pdf.rect(mx, my, mw + 8, mh + 8, "FD")

# Screen face
sx, sy = mx + 4, my + 4
sw, sh = mw, mh
pdf.set_fill_color(0, 0, 0)
pdf.rect(sx, sy, sw, sh, "F")

# Bar segments (right strip of screen)
bx = sx + sw - 8
bt = sy + 2
bh_total = sh - 4
pdf.set_fill_color(200, 40, 40)
pdf.rect(bx, bt, 6, bh_total * 0.31, "F")
pdf.set_fill_color(220, 120, 20)
pdf.rect(bx, bt + bh_total * 0.31, 6, bh_total * 0.22, "F")
pdf.set_fill_color(30, 180, 140)
pdf.rect(bx, bt + bh_total * 0.53, 6, bh_total * 0.26, "F")
pdf.set_fill_color(40, 80, 200)
pdf.rect(bx, bt + bh_total * 0.79, 6, bh_total * 0.21, "F")

# Indicators on bar
ind_obj_y = bt + bh_total * 0.70
pdf.set_fill_color(255, 255, 255)
pdf.rect(bx, ind_obj_y - 0.7, 6, 1.4, "F")
ind_amb_y = bt + bh_total * 0.73
pdf.set_fill_color(255, 136, 0)
pdf.rect(bx, ind_amb_y - 0.5, 6, 1.0, "F")

# Main reading
pdf.set_xy(sx, sy + 14)
pdf.set_font("Helvetica", "B", 18)
pdf.set_text_color(255, 255, 255)
pdf.cell(sw - 10, 10, "36.5", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

# Unit
pdf.set_xy(sx, sy + 25)
pdf.set_font("Helvetica", "", 12)
pdf.set_text_color(255, 136, 0)
pdf.cell(sw - 10, 8, "\xb0C", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

# Screen divider
pdf.set_draw_color(50, 50, 50)
pdf.set_line_width(0.2)
pdf.line(sx + 2, sy + 37, sx + sw - 12, sy + 37)

# Ambient reading
pdf.set_xy(sx, sy + 40)
pdf.set_font("Helvetica", "", 9)
pdf.set_text_color(147, 68, 0)
pdf.cell(sw - 10, 6, "22.1", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

# Button hint
pdf.set_xy(sx, sy + sh - 8)
pdf.set_font("Helvetica", "", 5)
pdf.set_text_color(50, 50, 60)
pdf.cell(sw - 10, 4, "A: C / F", align="C")

# Numbered callout dots on screen face
numbered = [
    (sy + 19, "1"),   # object temp
    (sy + 29, "2"),   # unit
    (sy + 43, "3"),   # ambient
]
for dot_y, num in numbered:
    dot_x = sx + 3
    pdf.set_fill_color(255, 136, 0)
    pdf.ellipse(dot_x, dot_y - 1.5, 3, 3, "F")
    pdf.set_xy(dot_x - 0.3, dot_y - 2)
    pdf.set_font("Helvetica", "B", 5)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(3, 3, num, align="C")

# "4" dot on bar
bar_dot_x = bx + 1
bar_dot_y = bt + 4
pdf.set_fill_color(255, 136, 0)
pdf.ellipse(bar_dot_x, bar_dot_y - 1.5, 3, 3, "F")
pdf.set_xy(bar_dot_x - 0.3, bar_dot_y - 2)
pdf.set_font("Helvetica", "B", 5)
pdf.set_text_color(0, 0, 0)
pdf.cell(3, 3, "4", align="C")

# Legend below mockup — 2x2 grid, clear of bezel bottom (my+mh+8)
legend = [("1", "Object temp"), ("2", "Unit (C/F)"), ("3", "Ambient temp"), ("4", "Range bar")]
col_w = 28
row_h = 6
for i, (num, label) in enumerate(legend):
    row = i // 2
    col = i % 2
    lx = mx + col * col_w
    ly = my + mh + 18 + row * row_h   # +18 clears bezel bottom (+8) with breathing room
    pdf.set_fill_color(255, 136, 0)
    pdf.ellipse(lx, ly - 1.2, 3, 3, "F")
    pdf.set_xy(lx - 0.3, ly - 2)
    pdf.set_font("Helvetica", "B", 5)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(3, 3, num, align="C")
    pdf.set_xy(lx + 4, ly - 2)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(80, 80, 90)
    pdf.cell(22, 3, label)

# --- Tech specs (single column) ---
spec_y = my + mh + 40   # below legend (2 rows * 6 + 18 offset + gap)
pdf.set_xy(col_l, spec_y)
pdf.set_font("Helvetica", "B", 9)
pdf.set_text_color(255, 136, 0)
pdf.cell(W - PAD * 2, 5, "TECHNICAL SPECIFICATIONS", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

pdf.set_line_width(0.3)
pdf.set_draw_color(200, 200, 210)
pdf.line(col_l, pdf.get_y() + 1, W - col_l, pdf.get_y() + 1)
pdf.set_y(pdf.get_y() + 4)

specs = [
    ("Sensor",             "Melexis MLX90614ESF-BAA"),
    ("Object temp range",  "-70 C to +380 C"),
    ("Ambient temp range", "-40 C to +125 C"),
    ("Accuracy",           "+/-0.5 C  (0 to 50 C target range)"),
    ("Resolution",         "0.02 C"),
    ("Interface",          "I2C SMBus  |  SDA GPIO0  |  SCL GPIO26"),
    ("Host board",         "M5StickC Plus  (ESP32-PICO-D4, 240 MHz)"),
    ("Display",            "1.14\" IPS LCD  135 x 240 px"),
    ("Firmware stack",     "Arduino / PlatformIO  |  FreeSans font"),
    ("Update rate",        "~3 Hz (partial redraw, flicker-free)"),
]

key_w = 46
val_w = W - PAD * 2 - key_w
for key, val in specs:
    y = pdf.get_y()
    pdf.set_xy(col_l, y)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(50, 50, 60)
    pdf.cell(key_w, 7, key + ":", new_x=XPos.RIGHT)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(100, 100, 110)
    pdf.cell(val_w, 7, val, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

# Bottom bar
pdf.set_fill_color(255, 136, 0)
pdf.rect(0, H - 8, W, 8, "F")
# "reachlin" centered in the orange bar
pdf.set_xy(0, H - 7)
pdf.set_font("Helvetica", "B", 8)
pdf.set_text_color(255, 255, 255)
pdf.cell(W, 6, "reachlin", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
# repo link just above the bar
pdf.set_xy(0, H - 16)
pdf.set_font("Helvetica", "", 7)
pdf.set_text_color(120, 120, 130)
pdf.cell(W, 5, "github.com/reachlin/lumina-ir1  |  MIT License", align="C")

out = "/Users/lincai/dev/vault-whisper/hat-mlx90614/lumina_ir1_datasheet.pdf"
pdf.output(out)
print(f"Saved: {out}")
