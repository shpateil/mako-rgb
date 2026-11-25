#!/usr/bin/python3
# panel -- панель mako (gtk4). правки идут в черновик, в клавиатуру уходит
# только по кнопке "применить".
import json
import queue
import sys
import threading
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(HERE))
import mako  # noqa: E402
import perkey  # noqa: E402

LAYOUT = json.load(open(BASE / "data" / "layout-win68.json"))["keys"]
ICONS = json.load(open(BASE / "data" / "icons.json"))
FULLNAME = {int(k["index"]): k["name"] for k in LAYOUT}
BYNAME = {k["name"].lower(): int(k["index"]) for k in LAYOUT}
BOARD_W, BOARD_H = 615.0, 202.0
MIN_X, MIN_Y = 10.0, 15.0
OUTER_M = 10   # отступ от границ окна
OUTER_SP = 8   # между блоками
CARD_M = 12    # внутри карточки до её рамки
CARD_SP = 9    # между строками в карточке
DIR = Path.home() / ".local/share/mako"

MODES = ["static", "wave", "breath", "neon", "radar", "reactive",
         "aurora", "ripple", "twinkle", "cross", "fireworks", "striation"]
MODE_RU = {
    "custom": "свои цвета", "static": "статичный", "wave": "волна",
    "breath": "дыхание", "neon": "неон", "radar": "радар",
    "reactive": "на нажатие", "aurora": "аврора", "ripple": "рябь",
    "twinkle": "мерцание", "cross": "крест", "fireworks": "фейерверк",
    "striation": "полосы",
}
# какие режимы используют второй цвет и направление
MODE_USES = {
    "custom": "цвет каждой клавиши свой",
    "static": "один цвет, без анимации",
    "wave": "основной и второй цвет, есть направление",
    "breath": "основной цвет плавно гаснет и разгорается",
    "neon": "основной и второй цвет",
    "radar": "основной и второй цвет, есть направление",
    "reactive": "вспышка основным цветом по нажатию",
    "aurora": "основной и второй цвет, перелив",
    "ripple": "волна от нажатой клавиши",
    "twinkle": "мерцание основным цветом",
    "cross": "основной и второй цвет",
    "fireworks": "вспышки основным цветом",
    "striation": "полосы основным и вторым цветом",
}
MODE_ICON = {
    "custom": "Paintbrush", "static": "Square", "wave": "Activity",
    "breath": "Sun", "neon": "Lightbulb", "radar": "Gauge",
    "reactive": "Zap", "aurora": "Sparkles", "ripple": "Droplet",
    "twinkle": "Sparkles", "cross": "X", "fireworks": "Sparkles",
    "striation": "Layers",
}
DIRECTIONS = [("вправо", 0), ("влево", 1), ("вверх", 2), ("вниз", 3),
              ("от центра", 4), ("к центру", 5)]

PALETTE = [
    ("розовый", "#ff5fd9"), ("лиловый", "#b9a0d6"), ("голубой", "#5fd9ff"),
    ("мятный", "#5fffb4"), ("янтарь", "#ffb45f"), ("коралл", "#ff6b6b"),
    ("синий", "#5f8cff"), ("белый", "#e9edf4"),
]
GROUP_PRESETS = [
    ("wasd", ["w", "a", "s", "d"]),
    ("цифры", ["1!", "2@", "3#", "4$", "5%", "6^", "7&", "8*", "9(", "0)"]),
    ("ряд qwerty", ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"]),
    ("всё", None),
]
SHORT = {
    "Back": "bksp", "Del": "del", "Ins": "ins", "Caps": "caps", "Enter": "ent",
    "PgUp": "pgu", "PgDn": "pgd", "L-Shift": "sft", "R-Shift": "sft",
    "L-Ctrl": "ctl", "R-Ctrl": "ctl", "L-Win": "win", "L-Alt": "alt",
    "R-Alt": "alt", "Space": "spc", "Up": "up", "Down": "dn", "Left": "lt",
    "Right": "rt", "Fn": "fn", "Tab": "tab", "Esc": "esc",
}

CSS = b"""
window { background: #090a0c; }
.brand { font-size: 13px; font-weight: 700; color: #f2f4f7; }
.tag { font-size: 10px; color: #4c5158; }
.sec { font-size: 10px; font-weight: 700; color: #62686f; letter-spacing: 0.7px; }
.hint { font-size: 10px; color: #434850; }
.val { font-size: 10px; color: #c2c7ce; }
.card { background: #0b0d10; border: 1px solid #13161b; border-radius: 12px; }
.pill { padding: 2px 8px; border-radius: 999px; background: #0d0f13;
        color: #6d727b; font-size: 10px; border: 1px solid #15181d; }
.ok { color: #55a572; border-color: #13241a; background: #090e0b; }
.err { color: #bd6260; border-color: #231616; background: #0f0b0b; }
.btn { background: #0e1115; border: 1px solid #191d23; border-radius: 7px;
       color: #b1b6bd; font-size: 10px; padding: 0 8px; min-height: 26px; }
.btn:hover { background: #12161b; border-color: #22272f; }
.on { background: #16141e; border-color: #33273e; color: #e0d1ef; }
.go { background: #ff5fd9; border: none; border-radius: 7px; color: #180811;
      font-size: 10px; font-weight: 700; padding: 0 12px; min-height: 26px; }
.go:hover { background: #ff72dd; }
.go:disabled { background: #181420; color: #494352; }
scale { min-height: 20px; }
scale trough { background: #0f1216; border-radius: 999px; min-height: 2px; }
scale highlight { background: #ff5fd9; border-radius: 999px; }
scale slider { background: #e9ecf1; border-radius: 999px; min-width: 8px; min-height: 8px; }
scale value { font-size: 9px; color: #6b7078; }
dropdown button { background: #0e1115; border: 1px solid #191d23; border-radius: 7px;
                  color: #b1b6bd; font-size: 10px; min-height: 26px; padding: 0 7px; }
dropdown popover { background: #0c0e11; }
"""


def hex_rgb(s):
    s = s.lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def rgb_hex(c):
    return "#%02x%02x%02x" % tuple(int(x) for x in c)


def rounded(cr, x, y, w, h, r):
    r = max(0.0, min(r, w / 2, h / 2))
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -1.5708, 0)
    cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
    cr.arc(x + r, y + h - r, r, 1.5708, 3.1416)
    cr.arc(x + r, y + r, r, 3.1416, 4.7124)
    cr.close_path()


def svg_markup(name, size=14, color="#b1b6bd", stroke=2.0):
    parts = []
    for item in ICONS.get(name, []):
        tag = item[0]
        a = item[1] if len(item) > 1 else {}
        if tag == "path":
            parts.append('<path d="%s"/>' % a.get("d", ""))
        elif tag == "circle":
            parts.append('<circle cx="%s" cy="%s" r="%s"/>'
                         % (a.get("cx"), a.get("cy"), a.get("r")))
        elif tag == "rect":
            parts.append('<rect x="%s" y="%s" width="%s" height="%s" rx="%s"/>'
                         % (a.get("x", 0), a.get("y", 0), a.get("width"),
                            a.get("height"), a.get("rx", 0)))
        elif tag == "line":
            parts.append('<line x1="%s" y1="%s" x2="%s" y2="%s"/>'
                         % (a.get("x1"), a.get("y1"), a.get("x2"), a.get("y2")))
        elif tag in ("polyline", "polygon"):
            parts.append('<%s points="%s"/>' % (tag, a.get("points", "")))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 24 24" fill="none" stroke="%s" stroke-width="%s" '
            'stroke-linecap="round" stroke-linejoin="round">%s</svg>'
            % (size, size, color, stroke, "".join(parts)))


def icon_image(name, size=14, color="#b1b6bd"):
    try:
        loader = GdkPixbuf.PixbufLoader()
        loader.write(svg_markup(name, size, color).encode())
        loader.close()
        pb = loader.get_pixbuf()
        if pb is None:
            raise ValueError
        return Gtk.Image.new_from_paintable(Gdk.Texture.new_for_pixbuf(pb))
    except (GLib.Error, ValueError, TypeError):
        return Gtk.Image.new_from_icon_name("image-missing")


def icon_button(icon, label=None, color="#b1b6bd", css="btn"):
    btn = Gtk.Button()
    btn.add_css_class(css)
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    box.append(icon_image(icon, 12, color))
    if label:
        box.append(Gtk.Label(label=label))
    btn.set_child(box)
    return btn


class Swatch(Gtk.DrawingArea):
    def __init__(self, color, on_pick, size=22):
        super().__init__()
        self.color = color
        self.on_pick = on_pick
        self.sel = False
        self.set_content_width(size)
        self.set_content_height(size)
        self.set_cursor(Gdk.Cursor.new_from_name("pointer", None))
        self.set_draw_func(self._draw)
        c = Gtk.GestureClick()
        c.connect("pressed", lambda *a: self.on_pick(self.color))
        self.add_controller(c)

    def set_selected(self, on):
        if self.sel != on:
            self.sel = on
            self.queue_draw()

    def _draw(self, area, cr, w, h):
        r, g, b = hex_rgb(self.color)
        if self.sel:
            cr.set_source_rgba(1, 1, 1, 0.16)
            rounded(cr, 0, 0, w, h, 7)
            cr.fill()
        cr.set_source_rgba(r / 255, g / 255, b / 255, 1)
        rounded(cr, 2.5, 2.5, w - 5, h - 5, 5)
        cr.fill()
        if self.sel:
            cr.set_source_rgba(1, 1, 1, 0.95)
            cr.set_line_width(1.4)
        else:
            cr.set_source_rgba(0.11, 0.13, 0.16, 1)
            cr.set_line_width(1)
        rounded(cr, 2.5, 2.5, w - 5, h - 5, 5)
        cr.stroke()


class Device:
    def __init__(self):
        self.q = queue.Queue()
        self.dev = None
        self.unit = 0.01
        self.error = None
        threading.Thread(target=self._loop, daemon=True).start()

    def _open(self):
        if self.dev is None:
            try:
                self.dev = mako.Dev()
                mt = mako.max_travel(self.dev)
                if mt:
                    self.unit = mt["unit"]
                self.error = None
            except (SystemExit, OSError) as e:
                self.error = str(e)
                self.dev = None
        return self.dev

    def _loop(self):
        while True:
            fn, args, cb = self.q.get()
            d = self._open()
            try:
                res = fn(d, *args) if d else None
            except (OSError, AttributeError, TypeError, IndexError) as e:
                self.error = str(e)
                self.dev = None
                res = None
            if cb:
                GLib.idle_add(cb, res)

    def call(self, fn, *args, cb=None):
        self.q.put((fn, args, cb))


class Panel(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("mako")
        self.set_default_size(900, 640)
        self.set_size_request(720, 540)

        self.dev = Device()
        self.light = {}
        self.table = bytearray(396)
        self.trig = {}
        self.color = "#ff5fd9"
        self.bg_color = "#000000"
        self.sel = set()
        self.hover = None
        self.painting = False
        self.busy = False
        self.unit = 0.01
        self.rt = False
        self.sync = False

        # единые отступы окна
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=OUTER_SP)
        for edge in ("top", "bottom", "start", "end"):
            getattr(outer, "set_margin_" + edge)(OUTER_M)
        self.set_child(outer)
        outer.append(self._head())
        outer.append(self._board())
        outer.append(self._cols())
        outer.append(self._foot())
        self.reload()

    def _head(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        bar.append(icon_image("Keyboard", 16, "#ff5fd9"))
        t = Gtk.Label(label="mako", xalign=0)
        t.add_css_class("brand")
        bar.append(t)
        sub = Gtk.Label(label="win68 he", xalign=0)
        sub.add_css_class("tag")
        bar.append(sub)
        sp = Gtk.Box()
        sp.set_hexpand(True)
        bar.append(sp)
        self.pill = Gtk.Label(label="…")
        self.pill.add_css_class("pill")
        self.pill.set_valign(Gtk.Align.CENTER)
        bar.append(self.pill)
        self.go = icon_button("Check", "применить", "#180811", "go")
        self.go.set_sensitive(False)
        self.go.connect("clicked", self._apply)
        bar.append(self.go)
        return bar

    def _board(self):
        card = Gtk.Box()
        card.add_css_class("card")
        card.set_vexpand(True)
        self.area = Gtk.DrawingArea()
        self.area.set_hexpand(True)
        self.area.set_draw_func(self._draw)
        m = Gtk.EventControllerMotion()
        m.connect("motion", self._motion)
        m.connect("leave", self._leave)
        self.area.add_controller(m)
        c = Gtk.GestureClick()
        c.set_button(0)
        c.connect("pressed", self._press)
        c.connect("released", self._release)
        self.area.add_controller(c)

        # держим пропорции клавиатуры, иначе карта раздувает окно
        frame = Gtk.AspectFrame(xalign=0.5, yalign=0.5, ratio=(BOARD_W - MIN_X) / (BOARD_H - MIN_Y), obey_child=False)
        frame.set_child(self.area)
        card.append(frame)
        return card

    def _geom(self, w, h):
        pad = 8.0
        s = min((w - pad * 2) / (BOARD_W - MIN_X), (h - pad * 2) / (BOARD_H - MIN_Y))
        ox = (w - (BOARD_W - MIN_X) * s) / 2 - MIN_X * s
        oy = (h - (BOARD_H - MIN_Y) * s) / 2 - MIN_Y * s
        return s, ox, oy

    def _rect(self, k, s, ox, oy):
        return (float(k["x"]) * s + ox, float(k["y"]) * s + oy,
                float(k["width"]) * s, float(k["height"]) * s)

    def _draw(self, area, cr, w, h):
        s, ox, oy = self._geom(w, h)
        cr.set_source_rgb(0.035, 0.039, 0.046)
        cr.paint()
        for k in LAYOUT:
            x, y, kw, kh = self._rect(k, s, ox, oy)
            idx = int(k["index"])
            rgb = self.table[idx * 3:idx * 3 + 3]
            lit = len(rgb) == 3 and any(rgb)
            sel = idx in self.sel
            hov = self.hover == idx

            cr.set_source_rgba(0.05, 0.056, 0.067, 1)
            rounded(cr, x + 1.2, y + 1.2, kw - 2.4, kh - 2.4, 4)
            cr.fill_preserve()
            if lit:
                r, g, b = [c / 255 for c in rgb]
                cr.set_source_rgba(r, g, b, 0.55)
                cr.fill()
            if sel:
                cr.set_source_rgba(1, 0.37, 0.85, 0.2)
                cr.fill()
            elif hov:
                cr.set_source_rgba(0.8, 0.83, 0.9, 0.07)
                cr.fill()

            if sel:
                cr.set_line_width(1.4)
                cr.set_source_rgba(1, 0.37, 0.85, 0.9)
            elif lit:
                r, g, b = [c / 255 for c in rgb]
                cr.set_line_width(0.8)
                cr.set_source_rgba(min(1, r + .22), min(1, g + .22), min(1, b + .22), .8)
            else:
                cr.set_line_width(0.8)
                cr.set_source_rgba(0.09, 0.103, 0.125, 1)
            rounded(cr, x + 1.2, y + 1.2, kw - 2.4, kh - 2.4, 4)
            cr.stroke()

            label = SHORT.get(k["name"], k["name"][0])
            cr.set_font_size(max(5.8, min(7.4, kh * 0.18)))
            if lit:
                cr.set_source_rgba(1, 1, 1, 0.9)
            else:
                cr.set_source_rgba(0.32, 0.35, 0.4, 1)
            ext = cr.text_extents(label)
            cr.move_to(x + (kw - ext.width) / 2 - ext.x_bearing,
                       y + (kh + ext.height) / 2 - ext.y_bearing - 1)
            cr.show_text(label)

    def _hit(self, x, y):
        s, ox, oy = self._geom(self.area.get_width(), self.area.get_height())
        for k in LAYOUT:
            kx, ky, kw, kh = self._rect(k, s, ox, oy)
            if kx <= x <= kx + kw and ky <= y <= ky + kh:
                return int(k["index"])
        return None

    def _motion(self, ctrl, x, y):
        idx = self._hit(x, y)
        if idx != self.hover:
            self.hover = idx
            self.area.queue_draw()
        if self.painting and idx is not None:
            self._paint([idx])

    def _leave(self, ctrl):
        if self.hover is not None:
            self.hover = None
            self.area.queue_draw()

    def _press(self, g, n, x, y):
        idx = self._hit(x, y)
        if idx is None:
            return
        if g.get_current_button() == 3:
            self.table[idx * 3:idx * 3 + 3] = b"\x00\x00\x00"
            self.sel = {idx}
            self._dirty()
            self.area.queue_draw()
            self._sel_changed()
            return
        if g.get_current_event_state() & Gdk.ModifierType.SHIFT_MASK:
            self.sel.add(idx)
        else:
            self.sel = {idx}
        self.painting = True
        self._paint([idx])
        self._sel_changed()

    def _release(self, g, n, x, y):
        self.painting = False

    def _paint(self, idxs):
        r, g, b = hex_rgb(self.color)
        for idx in idxs:
            self.table[idx * 3:idx * 3 + 3] = bytes([r, g, b])
        self._dirty()
        self.area.queue_draw()

    # ---------- низ: слева подсветка, справа клавиши ----------

    def _cols(self):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=OUTER_SP)
        row.set_vexpand(False)
        for col in (self._light_col(), self._keys_col()):
            col.set_hexpand(True)
            col.set_size_request(300, -1)
            row.append(col)
        return row

    def _card(self, spacing=CARD_SP):
        c = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        c.add_css_class("card")
        for edge in ("top", "bottom", "start", "end"):
            getattr(c, "set_margin_" + edge)(CARD_M)
        return c

    def _sec(self, icon, text, right=None):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        row.append(icon_image(icon, 12, "#62686f"))
        l = Gtk.Label(label=text, xalign=0)
        l.add_css_class("sec")
        row.append(l)
        sp = Gtk.Box()
        sp.set_hexpand(True)
        row.append(sp)
        if right is not None:
            right.set_valign(Gtk.Align.CENTER)
            row.append(right)
        return row

    def _row(self, label, widget, width=52):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        l = Gtk.Label(label=label, xalign=0)
        l.add_css_class("hint")
        l.set_size_request(width, -1)
        l.set_valign(Gtk.Align.CENTER)
        box.append(l)
        box.append(widget)
        return box

    def _scale(self, lo, hi, step, val, digits, cb):
        sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
        sc.set_digits(digits)
        sc.set_draw_value(True)
        sc.set_value(val)
        sc.set_hexpand(True)
        sc.set_valign(Gtk.Align.CENTER)
        sc.connect("value-changed", cb)
        return sc

    def _light_col(self):
        c = self._card()

        self.mode_lbl = Gtk.Label(label="", xalign=1)
        self.mode_lbl.add_css_class("val")
        c.append(self._sec("Palette", "подсветка", self.mode_lbl))

        # палитра + свой цвет в одном ряду
        # основной цвет эффекта
        c.append(self._color_line("основной", True))
        # второй цвет эффекта (для дыхания, волны, авроры и тд)
        c.append(self._color_line("второй", False))

        # режим + направление
        mrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.mode_dd = Gtk.DropDown.new_from_strings(
            [MODE_RU["custom"]] + [MODE_RU[m] for m in MODES])
        self.mode_dd.set_hexpand(True)
        self.mode_dd.connect("notify::selected", self._mode)
        mrow.append(self.mode_dd)
        # у этих режимов второй цвет реально используется прошивкой
        self.mode_hint = Gtk.Label(label="", xalign=0)
        self.mode_hint.add_css_class("hint")
        self.dir_dd = Gtk.DropDown.new_from_strings([d[0] for d in DIRECTIONS])
        self.dir_dd.set_size_request(96, -1)
        self.dir_dd.connect("notify::selected", self._direction)
        mrow.append(self.dir_dd)
        c.append(self._row("режим", mrow))
        c.append(self.mode_hint)

        # яркость, скорость, радуга
        self.bright = self._scale(0, 4, 1, 4, 0, self._bright)
        c.append(self._row("яркость", self.bright))
        self.speed = self._scale(0, 4, 1, 4, 0, self._speed)
        c.append(self._row("скорость", self.speed))

        brow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.rainbow = icon_button("Rainbow", "радуга")
        self.rainbow.connect("clicked", self._toggle_rainbow)
        brow.append(self.rainbow)
        onb = icon_button("Power", "залить", )
        onb.set_tooltip_text("покрасить выбранные клавиши")
        onb.connect("clicked", lambda b: self._fill_selected())
        brow.append(onb)
        clr = icon_button("Trash2", "очистить")
        clr.set_tooltip_text("стереть цвета выбранных клавиш")
        clr.connect("clicked", lambda b: self._clear_selected())
        brow.append(clr)
        c.append(brow)
        return c

    def _color_line(self, label, primary):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        l = Gtk.Label(label=label, xalign=0)
        l.add_css_class("hint")
        l.set_size_request(52, -1)
        l.set_valign(Gtk.Align.CENTER)
        box.append(l)
        swatches = []
        current = self.color if primary else self.bg_color
        for name, hexv in PALETTE:
            sw = Swatch(hexv, lambda c, pr=primary: self._take_color(c, pr), size=20)
            sw.set_tooltip_text(name)
            sw.set_selected(hexv == current)
            swatches.append(sw)
            box.append(sw)
        custom = Swatch(current, lambda c: None, size=20)
        custom.set_tooltip_text("свой цвет")
        box.append(custom)
        pick = icon_button("Paintbrush")
        pick.set_tooltip_text("выбрать любой цвет")
        pick.connect("clicked", lambda b, pr=primary: self._color_dialog(pr))
        box.append(pick)
        if primary:
            self.palette = swatches
            self.custom = custom
        else:
            self.palette2 = swatches
            self.custom2 = custom
        return box

    def _keys_col(self):
        c = self._card()

        self.who = Gtk.Label(label="не выбрано", xalign=1)
        self.who.add_css_class("val")
        c.append(self._sec("Gauge", "клавиши", self.who))

        # быстрый выбор групп
        g = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for label, names in GROUP_PRESETS:
            b = Gtk.Button(label=label)
            b.add_css_class("btn")
            b.set_hexpand(True)
            b.connect("clicked", lambda btn, n=names: self._select_group(n))
            g.append(b)
        c.append(self._row("выбрать", g))

        self.travel = self._scale(0.1, 3.4, 0.05, 2.2, 2, self._travel)
        c.append(self._row("ход", self.travel))

        self.rt_btn = icon_button("Zap", "rapid trigger выкл")
        self.rt_btn.set_hexpand(True)
        self.rt_btn.connect("clicked", self._toggle_rt)
        c.append(self.rt_btn)

        self.rt_press = self._scale(0.05, 1.0, 0.05, 0.15, 2, self._rt_changed)
        self.rt_release = self._scale(0.05, 1.0, 0.05, 0.15, 2, self._rt_changed)
        self.press_row = self._row("нажатие", self.rt_press)
        self.release_row = self._row("отпускание", self.rt_release)
        self.press_row.set_sensitive(False)
        self.release_row.set_sensitive(False)
        c.append(self.press_row)
        c.append(self.release_row)

        brow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        allb = icon_button("Layers", "всем")
        allb.set_hexpand(True)
        allb.connect("clicked", self._all)
        brow.append(allb)
        rst = icon_button("RotateCcw", "сброс")
        rst.set_hexpand(True)
        rst.set_tooltip_text("вернуть заводские 1.70 мм")
        rst.connect("clicked", self._reset_trig)
        brow.append(rst)
        c.append(brow)
        return c

    def _foot(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.status = Gtk.Label(label="", xalign=0)
        self.status.add_css_class("hint")
        box.append(self.status)
        sp = Gtk.Box()
        sp.set_hexpand(True)
        box.append(sp)
        for icon, label, cb, tip in (
                ("RefreshCw", "перечитать", lambda b: self.reload(), "читать из клавиатуры"),
                ("Undo2", "бэкап", self._restore, "вернуть исходное"),
                ("Save", "профиль", self._save_profile, "сохранить раскраску в файл"),
                ("Upload", "загрузить", self._load_profile, "загрузить раскраску из файла")):
            btn = icon_button(icon, label)
            btn.set_tooltip_text(tip)
            btn.connect("clicked", cb)
            box.append(btn)
        return box

    # ---------- правки ----------

    def _dirty(self):
        if not self.busy:
            self.go.set_sensitive(True)
            self.status.set_text("не применено")

    def _take_color(self, hexv, primary=True):
        # цвет идёт и в эффект (fg/bg), и в пер-кей таблицу: иначе анимация
        # продолжает светить старым цветом и кажется что ничего не меняется
        if primary:
            self.color = hexv
            self.light["fg"] = hexv
            for sw in self.palette:
                sw.set_selected(sw.color == hexv)
            self.custom.set_selected(False)
        else:
            self.bg_color = hexv
            self.light["bg"] = hexv
            for sw in self.palette2:
                sw.set_selected(sw.color == hexv)
            self.custom2.set_selected(False)
        r, g, b = hex_rgb(hexv)
        for idx in self.sel:
            self.table[idx * 3:idx * 3 + 3] = bytes([r, g, b])
        if self.sel:
            self._dirty()
            self.area.queue_draw()
        else:
            self._dirty()

    def _color_dialog(self, primary=True):
        dlg = Gtk.ColorDialog(title="цвет")
        cur = self.color if primary else self.bg_color
        r, g, b = [c / 255 for c in hex_rgb(cur)]

        def done(dialog, result):
            try:
                c = dialog.choose_rgba_finish(result)
            except GLib.Error:
                return
            if not c:
                return
            hexv = rgb_hex([int(c.red * 255), int(c.green * 255), int(c.blue * 255)])
            sw = self.custom if primary else self.custom2
            sw.color = hexv
            sw.queue_draw()
            sw.set_selected(True)
            for s in (self.palette if primary else self.palette2):
                s.set_selected(False)
            self._take_color(hexv, primary)

        dlg.choose_rgba(self, Gdk.RGBA(r, g, b, 1.0), None, done)

    def _bright(self, sc):
        if self.sync or not self.light:
            return
        self.light["brightness"] = int(sc.get_value())
        self._dirty()

    def _speed(self, sc):
        if self.sync or not self.light:
            return
        self.light["speed"] = int(sc.get_value())
        self._dirty()

    def _mode(self, dd, _p):
        if self.sync or not self.light:
            return
        names = ["custom"] + MODES
        i = dd.get_selected()
        if 0 <= i < len(names):
            self.light["mode"] = names[i]
            self.mode_lbl.set_text(MODE_RU[names[i]])
            self.mode_hint.set_text(MODE_USES.get(names[i], ""))
            self._dirty()

    def _direction(self, dd, _p):
        if self.sync or not self.light:
            return
        i = dd.get_selected()
        if 0 <= i < len(DIRECTIONS):
            self.light["direction"] = DIRECTIONS[i][1]
            self._dirty()

    def _toggle_rainbow(self, btn):
        on = not self.light.get("full_color")
        self.light["full_color"] = 1 if on else 0
        self._paint_rainbow()
        self._dirty()

    def _paint_rainbow(self):
        on = bool(self.light.get("full_color"))
        self.rainbow.set_child(None)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        box.append(icon_image("Rainbow", 12, "#e0d1ef" if on else "#b1b6bd"))
        box.append(Gtk.Label(label="радуга " + ("вкл" if on else "выкл")))
        self.rainbow.set_child(box)
        if on:
            self.rainbow.add_css_class("on")
        else:
            self.rainbow.remove_css_class("on")

    def _fill_selected(self):
        if not self.sel:
            self.status.set_text("сначала выбери клавиши")
            return
        r, g, b = hex_rgb(self.color)
        for idx in self.sel:
            self.table[idx * 3:idx * 3 + 3] = bytes([r, g, b])
        self._dirty()
        self.area.queue_draw()

    def _clear_selected(self):
        if not self.sel:
            return
        for idx in self.sel:
            self.table[idx * 3:idx * 3 + 3] = b"\x00\x00\x00"
        self._dirty()
        self.area.queue_draw()

    def _select_group(self, names):
        if names is None:
            self.sel = {int(k["index"]) for k in LAYOUT}
        else:
            self.sel = {BYNAME[n] for n in names if n in BYNAME}
        self.area.queue_draw()
        self._sel_changed()

    def _travel(self, sc):
        if self.sync or not self.sel:
            return
        val = round(sc.get_value(), 2)
        for idx in self.sel:
            t = self.trig.setdefault(idx, {"mode": 0, "travel": val, "i1": 0.01, "i2": 0.01})
            t["travel"] = val
            if t["mode"] == 0:
                t["i1"] = t["i2"] = 0.01
        self._dirty()

    def _rt_changed(self, sc):
        if self.sync or not self.sel or not self.rt:
            return
        press = round(self.rt_press.get_value(), 2)
        release = round(self.rt_release.get_value(), 2)
        travel = round(self.travel.get_value(), 2)
        for idx in self.sel:
            self.trig[idx] = {"mode": 13, "travel": travel, "i1": press, "i2": release}
        self._dirty()

    def _paint_rt_btn(self):
        self.rt_btn.set_child(None)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        box.append(icon_image("Zap", 12, "#e0d1ef" if self.rt else "#b1b6bd"))
        box.append(Gtk.Label(label="rapid trigger " + ("вкл" if self.rt else "выкл")))
        self.rt_btn.set_child(box)
        if self.rt:
            self.rt_btn.add_css_class("on")
        else:
            self.rt_btn.remove_css_class("on")

    def _toggle_rt(self, btn):
        self.rt = not self.rt
        self._paint_rt_btn()
        for r in (self.press_row, self.release_row):
            r.set_sensitive(self.rt)
        if not self.sel:
            return
        travel = round(self.travel.get_value(), 2)
        press = round(self.rt_press.get_value(), 2)
        release = round(self.rt_release.get_value(), 2)
        for idx in self.sel:
            self.trig[idx] = {"mode": 13 if self.rt else 0, "travel": travel,
                              "i1": press if self.rt else 0.01,
                              "i2": release if self.rt else 0.01}
        self._dirty()

    def _all(self, btn):
        travel = round(self.travel.get_value(), 2)
        press = round(self.rt_press.get_value(), 2)
        release = round(self.rt_release.get_value(), 2)
        for k in LAYOUT:
            self.trig[int(k["index"])] = {"mode": 13 if self.rt else 0, "travel": travel,
                                          "i1": press if self.rt else 0.01,
                                          "i2": release if self.rt else 0.01}
        self._dirty()
        self.status.set_text("ход %.2f мм назначен всем" % travel)

    def _reset_trig(self, btn):
        for k in LAYOUT:
            self.trig[int(k["index"])] = {"mode": 0, "travel": 1.70, "i1": 0.01, "i2": 0.01}
        self.sync = True
        self.travel.set_value(1.70)
        self.sync = False
        self.rt = False
        self._paint_rt_btn()
        self._dirty()
        self.status.set_text("сброс на 1.70 мм")

    def _sel_changed(self):
        if not self.sel:
            self.who.set_text("не выбрано")
            return
        names = [FULLNAME.get(i, str(i)) for i in sorted(self.sel)]
        self.who.set_text(", ".join(names) if len(names) <= 3 else "%d клавиш" % len(names))
        known = [self.trig[i] for i in self.sel if i in self.trig]
        if known:
            self._show_trigger(known[0])
            return
        idx = sorted(self.sel)[0]
        row, col = divmod(idx, 22)

        def work(d, r, c):
            return mako.read_trigger(d, r, c)

        def cb(res):
            if not res:
                return
            self.trig[idx] = {"mode": res["mode"],
                              "travel": round(res["travel"] * self.unit, 2),
                              "i1": round(res["i1"] * self.unit, 2),
                              "i2": round(res["i2"] * self.unit, 2)}
            if self.sel == {idx}:
                self._show_trigger(self.trig[idx])

        self.dev.call(work, row, col, cb=cb)

    def _show_trigger(self, t):
        self.sync = True
        self.travel.set_value(t["travel"])
        self.rt = t["mode"] in (12, 13)
        if self.rt:
            self.rt_press.set_value(t["i1"])
            self.rt_release.set_value(t["i2"])
        self.sync = False
        self._paint_rt_btn()
        for r in (self.press_row, self.release_row):
            r.set_sensitive(self.rt)

    # ---------- клавиатура ----------

    def reload(self):
        self.status.set_text("чтение…")

        def work(d):
            return {"light": mako.read_light(d), "table": perkey.read_table(d, 0),
                    "mt": mako.max_travel(d)}

        def cb(res):
            if not res or not res.get("light"):
                self.pill.set_text("нет связи")
                self.pill.remove_css_class("ok")
                self.pill.add_css_class("err")
                self.status.set_text(self.dev.error or "нет ответа")
                return
            self.pill.set_text("готово")
            self.pill.remove_css_class("err")
            self.pill.add_css_class("ok")
            if res["mt"]:
                self.unit = res["mt"]["unit"]
            self.light = dict(res["light"])
            if res["table"]:
                self.table = bytearray(res["table"])
            self.trig.clear()
            self._sync()
            self.go.set_sensitive(False)
            self.status.set_text("прочитано")

        self.dev.call(work, cb=cb)

    def _sync(self):
        if not self.light:
            return
        self.sync = True
        self.bright.set_value(self.light.get("brightness", 4))
        self.speed.set_value(self.light.get("speed", 4))
        m = self.light.get("mode", "custom")
        names = ["custom"] + MODES
        if m in names:
            self.mode_dd.set_selected(names.index(m))
        self.mode_lbl.set_text(MODE_RU.get(m, m))
        self.mode_hint.set_text(MODE_USES.get(m, ""))
        dcount = {d[1]: i for i, d in enumerate(DIRECTIONS)}
        self.dir_dd.set_selected(dcount.get(self.light.get("direction"), 4))
        self.sync = False
        if self.light.get("fg"):
            self.color = self.light["fg"]
            self.custom.color = self.color
            self.custom.queue_draw()
            for sw in self.palette:
                sw.set_selected(sw.color.lower() == self.color.lower())
        if self.light.get("bg"):
            self.bg_color = self.light["bg"]
            self.custom2.color = self.bg_color
            self.custom2.queue_draw()
            for sw in self.palette2:
                sw.set_selected(sw.color.lower() == self.bg_color.lower())
        self._paint_rainbow()
        self.area.queue_draw()

    def _apply(self, btn):
        self.busy = True
        self.go.set_sensitive(False)
        self.status.set_text("применяю…")
        table = bytes(self.table)
        light = dict(self.light)
        trig = {k: dict(v) for k, v in self.trig.items()}
        unit = self.unit
        # режим берём строго из UI, ничего не подменяем
        target = light.get("mode", "custom")

        def work(d):
            for slot in (0, 1):
                perkey.write_table(d, bytearray(table), slot)
                time.sleep(0.04)
            bright = int(light.get("brightness", 4))
            speed = int(light.get("speed", 4))
            fg = light.get("fg", "#ffffff")
            bg = light.get("bg", "#000000")
            dirv = int(light.get("direction", 4))
            rainbow = int(light.get("full_color", 0))
            for _ in range(4):
                cur = mako.read_light(d) or {}
                if (cur.get("mode") == target and cur.get("brightness") == bright
                        and cur.get("speed") == speed and cur.get("direction") == dirv):
                    break
                mako.write_light(d, {"mode": target, "brightness": bright, "speed": speed,
                                     "fg": fg, "bg": bg, "direction": dirv,
                                     "full_color": rainbow, "power": 0})
                time.sleep(0.08)
            groups = {}
            for idx, t in trig.items():
                key = (t["mode"], round(t["travel"], 2), round(t["i1"], 2), round(t["i2"], 2))
                groups.setdefault(key, []).append(divmod(idx, 22))
            for (mode, travel, i1, i2), targets in groups.items():
                mako.write_trigger(d, targets, mode, travel, i1, i2, unit)
                time.sleep(0.02)
            return {"light": mako.read_light(d), "table": perkey.read_table(d, 0)}

        def cb(res):
            self.busy = False
            if not res or not res.get("light"):
                self.status.set_text("не применилось")
                self.go.set_sensitive(True)
                return
            self.light = dict(res["light"])
            if res.get("table"):
                self.table = bytearray(res["table"])
            self.trig.clear()
            self._sync()
            self.go.set_sensitive(False)
            self.status.set_text("применено · %s" % MODE_RU.get(self.light.get("mode"), "?"))

        self.dev.call(work, cb=cb)

    def _save_profile(self, btn):
        def work(d):
            p = DIR / "profiles"
            p.mkdir(parents=True, exist_ok=True)
            data = {"light": self.light, "table": list(self.table)}
            num = len(list(p.glob("*.json"))) + 1
            (p / ("профиль-%d.json" % num)).write_text(json.dumps(data))
            return str(p / ("профиль-%d.json" % num))

        self.dev.call(work, cb=lambda r: self.status.set_text("сохранено: %s" % r if r else "ошибка"))

    def _load_profile(self, btn):
        self.status.set_text("профили в ~/.local/share/mako/profiles")

    def _restore(self, btn):
        self.status.set_text("бэкап…")

        def work(d):
            p = DIR / "perkey-backup.json"
            if not p.exists():
                return None
            data = json.loads(p.read_text())
            for slot, key in ((0, "set1"), (1, "set2")):
                t = bytearray(396)
                for i, rgb in data[key].items():
                    off = int(i) * 3
                    if off + 2 < 396:
                        t[off:off + 3] = bytes(rgb)
                perkey.write_table(d, t, slot)
                time.sleep(0.05)
            mako.write_light(d, {"mode": "wave", "brightness": 4, "speed": 4,
                                 "fg": "#ff00ff", "bg": "#00ffff", "direction": 4,
                                 "full_color": 0, "power": 0})
            return True

        def cb(res):
            self.status.set_text("бэкап возвращён" if res else "бэкапа нет")
            self.reload()

        self.dev.call(work, cb=cb)


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fun.shpateil.mako")

    def do_activate(self):
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        Panel(self).present()


def main():
    return App().run(sys.argv[:1])


if __name__ == "__main__":
    sys.exit(main())
