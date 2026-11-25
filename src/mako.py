#!/usr/bin/python3
# mako -- свой лёгкий софт для dexp mako (aula win68 he, 2e3c:c365)
# подсветка (cmd 07) + точка срабатывания (cmd 21). профили для игр.
import glob
import json
import os
import select
import sys
import time
from pathlib import Path

VID_PID = "00002E3C:0000C365"
REPORT_ID = 0x01
PAYLOAD = 63
DIR = Path.home() / ".local/share/mako"
LIGHT_BAK = DIR / "light-backup.json"
TRIG_BAK = DIR / "triggers-backup.json"
LAYOUT = Path(__file__).resolve().parent.parent / "data" / "layout-win68.json"
PROFILES = DIR / "profiles"

MODES = {
    "static": 0, "breath": 1, "wave": 2, "neon": 3, "radar": 4, "reactive": 6,
    "aurora": 7, "ripple": 8, "twinkle": 9, "custom": 10, "cross": 11,
    "speedres": 12, "autorip": 14, "striation": 15, "fireworks": 16,
}
MODE_BY_BYTE = {v: k for k, v in MODES.items()}


def find_node():
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            uevent = open(os.path.join(path, "device", "uevent")).read()
            desc = open(os.path.join(path, "device", "report_descriptor"), "rb").read()
        except OSError:
            continue
        if VID_PID not in uevent.upper():
            continue
        if b"\x06\x1b\xff\x09\x91" in desc:
            return "/dev/" + os.path.basename(path)
    return None


class Dev:
    def __init__(self):
        node = find_node()
        if not node:
            raise SystemExit("нет hidraw-узла mako (2e3c:c365, ff1b:91)")
        self.node = node
        self.fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def send(self, payload, cmd=None):
        # копируем ВЕСЬ payload: байты 2-3 это page, их терять нельзя
        f = bytearray(PAYLOAD)
        body = bytes(payload)[:PAYLOAD]
        f[:len(body)] = body
        os.write(self.fd, bytes([REPORT_ID]) + bytes(f))

    def read(self, timeout=0.15, cmd=None, op=None, want=None, settle=0.02):
        """Читает до наступления тишины settle или до timeout.
        want: сколько кадров достаточно, чтобы вернуться сразу."""
        out = []
        end = time.time() + timeout
        last = time.time()
        while time.time() < end:
            r, _, _ = select.select([self.fd], [], [], max(0, min(end, last + settle) - time.time()))
            if not r:
                if out:
                    break
                continue
            try:
                b = os.read(self.fd, 64)
            except BlockingIOError:
                continue
            last = time.time()
            if not b:
                continue
            if cmd is not None and b[1] != cmd:
                continue
            if op is not None and b[6] != op:
                continue
            out.append(b)
            if want and len(out) >= want:
                break
        return out

    def ask(self, payload, cmd, op=None, timeout=0.15, tries=3, want=None):
        for _ in range(tries):
            self.drain()
            self.send(payload)
            reps = self.read(timeout, cmd=cmd, op=op, want=want)
            if reps:
                return reps
        return []

    def drain(self, limit=64):
        """сбрасывает всё, что накопилось во входном буфере"""
        n = 0
        while n < limit:
            r, _, _ = select.select([self.fd], [], [], 0)
            if not r:
                break
            try:
                if not os.read(self.fd, 64):
                    break
            except BlockingIOError:
                break
            n += 1
        return n


def frame(cmd, sub=0, page=0, data=b""):
    f = bytearray(PAYLOAD)
    f[0] = cmd
    f[1] = sub
    f[2] = (page >> 8) & 0xFF
    f[3] = page & 0xFF
    f[4] = len(data)
    f[5:5 + len(data)] = data[:PAYLOAD - 5]
    return f


def hall(op, *rest):
    # кадр 21: [21][00][00][00][18][op][args]
    f = bytearray(PAYLOAD)
    f[0] = 0x21
    f[4] = 0x18
    f[5] = op & 0xFF
    f[6:6 + len(rest)] = bytes(rest)[:PAYLOAD - 6]
    return f


def hex2rgb(s):
    s = s.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return [int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)]


def rgb2hex(c):
    return "#%02x%02x%02x" % tuple(c)


# ---------- подсветка ----------

def read_light(d):
    reps = d.ask(frame(0x07, 0x01), cmd=0x07)
    for b in reps:
        if b[5] == 0x0C:
            p = b[6:18]
            return {
                "mode": MODE_BY_BYTE.get(p[0], p[0]),
                "mode_byte": p[0],
                "brightness": p[1],
                "speed": p[2],
                "fg": rgb2hex(p[3:6]),
                "bg": rgb2hex(p[6:9]),
                "direction": p[9],
                "full_color": p[10],
                "power": p[11],
            }
    return None


def write_light(d, st):
    p = bytes([
        MODES.get(st["mode"], 0) if isinstance(st["mode"], str) else st["mode"],
        st["brightness"], st["speed"],
        *hex2rgb(st["fg"]), *hex2rgb(st["bg"]),
        st["direction"], st["full_color"], st["power"],
    ])
    d.send(frame(0x07, 0x00, 0, p))


def light_apply(d, st=None, color=None, mode=None, brightness=None, speed=None):
    cur = read_light(d) if st is None else dict(st)
    if not cur:
        raise SystemExit("не смог прочитать текущую подсветку")
    if color:
        cur["fg"] = color if color.startswith("#") else "#" + color
    if mode is not None:
        cur["mode"] = mode
    if brightness is not None:
        cur["brightness"] = int(brightness)
    if speed is not None:
        cur["speed"] = int(speed)
    write_light(d, cur)
    time.sleep(0.12)
    return read_light(d)


# ---------- триггеры ----------

def max_travel(d):
    reps = d.ask(hall(0x04), cmd=0x21, op=0x04)
    for b in reps:
        p = b[1:]  # без report id, поля как в описании протокола
        mx = (p[9] << 8) | p[6]
        unit = p[7] or 10
        return {"max": mx, "unit": unit / 100.0, "min": p[10]}
    return None


def read_trigger(d, row, col):
    reps = d.ask(hall(0x05, row, col), cmd=0x21, op=0x05)
    for b in reps:
        p = b[1:]
        return {
            "mode": p[6],
            "travel": (p[11] << 8) | p[7],
            "i1": (p[13] << 8) | p[9],
            "i2": (p[14] << 8) | p[10],
        }
    return None


def write_trigger(d, targets, mode, travel, i1, i2, unit):
    masks = bytearray(22)
    for row, col in targets:
        masks[col] |= 1 << row
    t = max(0, int(round(travel / unit)))
    a = max(0, int(round(i1 / unit)))
    b = max(0, int(round(i2 / unit)))
    vals = bytes([t & 0xFF, t & 0xFF, a & 0xFF, b & 0xFF,
                  (t >> 8) & 0xFF, (t >> 8) & 0xFF, (a >> 8) & 0xFF, (b >> 8) & 0xFF])
    d.read(0.03)
    d.send(hall(mode, *masks, *vals))
    d.read(0.35, cmd=0x21)


def load_layout():
    return json.load(open(LAYOUT))["keys"]


def key_pos(name):
    name = name.lower()
    for k in load_layout():
        if k["name"].lower() == name or k["code"].lower() == name:
            return divmod(int(k["index"]), 22)
    raise SystemExit("нет такой клавиши: " + name)


def mm(t, unit):
    return round(t * unit, 2)


# ---------- команды ----------

def cmd_info(d):
    d.read(0.05)
    d.send(frame(0x0D))
    ident = [b[5:].split(b"\x00")[0].decode("ascii", "replace")
             for b in d.read(0.8, cmd=0x0D)]
    print("узел:", d.node)
    print("устройство:", " | ".join(ident))
    st = read_light(d)
    mt = max_travel(d)
    print("подсветка:", json.dumps(st, ensure_ascii=False))
    print("ход свитча: %s мм, шаг %.2f" % (mm(mt["max"], mt["unit"]), mt["unit"]) if mt else "ход не прочитан")


def save_backup(d, path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1))


def cmd_backup(d):
    st = read_light(d)
    save_backup(d, LIGHT_BAK, st)
    print("подсветка →", LIGHT_BAK)
    mt = max_travel(d)
    trig = {"max_travel": mt, "keys": {}}
    for k in load_layout():
        row, col = divmod(int(k["index"]), 22)
        t = read_trigger(d, row, col)
        if t:
            trig["keys"][k["name"]] = t
    save_backup(d, TRIG_BAK, trig)
    print("триггеры (%d клавиш) →" % len(trig["keys"]), TRIG_BAK)


def cmd_light(d, args):
    if not args:
        print(json.dumps(read_light(d), ensure_ascii=False, indent=1))
        return
    color = None
    mode = None
    bright = None
    speed = None
    for a in args:
        if a.startswith("#") or (len(a) in (3, 6) and all(c in "0123456789abcdefABCDEF" for c in a)):
            color = a if a.startswith("#") else "#" + a
        elif a in MODES:
            mode = a
        elif a.startswith("b") and a[1:].isdigit():
            bright = int(a[1:])
        elif a.startswith("s") and a[1:].isdigit():
            speed = int(a[1:])
        else:
            print("не понял аргумент:", a)
            return
    st = light_apply(d, color=color, mode=mode, brightness=bright, speed=speed)
    print(json.dumps(st, ensure_ascii=False))


def cmd_light_restore(d):
    st = json.loads(LIGHT_BAK.read_text())
    light_apply(d, st=st)
    print("подсветка возвращена:", json.dumps(st, ensure_ascii=False))


def cmd_trig(d, args):
    mt = max_travel(d)
    if not mt:
        raise SystemExit("не прочитал параметры свитча")
    unit = mt["unit"]
    if not args or args[0] == "list":
        for k in load_layout():
            row, col = divmod(int(k["index"]), 22)
            t = read_trigger(d, row, col)
            if t:
                print(f"{k['name']:10} mode={t['mode']:2} travel={mm(t['travel'], unit)}mm")
        return
    if args[0] == "get":
        row, col = key_pos(args[1])
        t = read_trigger(d, row, col)
        print(args[1], "mode=%s travel=%smm" % (t["mode"], mm(t["travel"], unit)))
        return
    # trig set w 0.5 [i1 i2 mode]
    keys, nums = [], []
    for a in args[1:]:
        try:
            nums.append(float(a))
        except ValueError:
            keys.append(a)
    pos = [key_pos(k) for k in keys]
    travel = nums[0] if nums else 1.2
    i1 = nums[1] if len(nums) > 1 else 0.01
    i2 = nums[2] if len(nums) > 2 else i1
    mode = int(nums[3]) if len(nums) > 3 else (12 if i1 > 0.02 else 0)
    if not pos:
        # без имени клавиши меняем всю клавиатуру
        pos = [divmod(int(k["index"]), 22) for k in load_layout()]
    write_trigger(d, pos, mode, travel, i1, i2, unit)
    for (row, col), k in zip(pos, keys):
        t = read_trigger(d, row, col)
        print(f"{k:10} mode={t['mode']:2} travel={mm(t['travel'], unit)}mm "
              f"i1={mm(t['i1'], unit)} i2={mm(t['i2'], unit)}")


def cmd_trig_restore(d):
    data = json.loads(TRIG_BAK.read_text())
    mt = max_travel(d) or data["max_travel"]
    unit = mt["unit"]
    for name, t in data["keys"].items():
        row, col = key_pos(name)
        write_trigger(d, [(row, col)], t["mode"], t["travel"] * unit,
                      t["i1"] * unit, t["i2"] * unit, unit)
    print("все триггеры возвращены из бэкапа")


def cmd_profile(d, args):
    if not args:
        print("профили:", ", ".join(p.stem for p in sorted(PROFILES.glob("*.json"))) or "нет")
        return
    name = args[0]
    path = PROFILES / (name + ".json")
    if len(args) > 1 and args[1] == "save":
        st = read_light(d)
        PROFILES.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(st, indent=1))
        print("сохранил профиль", name)
        return
    if not path.exists():
        raise SystemExit("нет профиля " + name)
    st = json.loads(path.read_text())
    print("применил:", json.dumps(light_apply(d, st=st), ensure_ascii=False))


def cmd_game(d, args):
    # game on|off: короткий ход для игр, обратно 1.7мм
    mt = max_travel(d)
    unit = mt["unit"]
    wasd = [key_pos(k) for k in ("w", "a", "s", "d")]
    if args and args[0] == "off":
        for row, col in wasd:
            write_trigger(d, [(row, col)], 0, 1.7, 0.01, 0.01, unit)
        print("wasd: ход 1.70мм, rapid trigger выключен")
    else:
        for row, col in wasd:
            write_trigger(d, [(row, col)], 12, 0.6, 0.15, 0.15, unit)
        print("wasd: ход 0.60мм + rapid trigger 0.15мм")
    for row, col in wasd:
        t = read_trigger(d, row, col)
        print("  mode=%s travel=%smm" % (t["mode"], mm(t["travel"], unit)))


def usage():
    print("""mako -- софт для dexp mako (aula win68 he)

  mako info                     что за клава, identity, текущая подсветка
  mako light                    показать подсветку
  mako light ff5fd9             цвет
  mako light ff5fd9 wave b3     цвет + режим + яркость
  mako light static #3cec80
  mako backup                   бэкап подсветки и всех триггеров
  mako restore                  вернуть подсветку и триггеры из бэкапа
  mako trig list                все клавиши: режим и ход
  mako trig get w
  mako trig set w 0.5           ход 0.5мм на W
  mako trig set w 1.2 0.3 0.3   rapid trigger: ход 1.2, чувств 0.3
  mako game on|off              игровой режим для WASD
  mako profile                  список профилей подсветки
  mako profile <имя> save       сохранить текущую подсветку как профиль
  mako profile <имя>            применить профиль""")
    print("\nрежимы:", ", ".join(MODES))


def main():
    if len(sys.argv) < 2:
        usage()
        return 0
    c = sys.argv[1]
    a = sys.argv[2:]
    with Dev() as d:
        if c == "info":
            cmd_info(d)
        elif c == "light":
            cmd_light(d, a)
        elif c == "backup":
            cmd_backup(d)
        elif c == "restore":
            cmd_light_restore(d)
            cmd_trig_restore(d)
        elif c == "trig":
            cmd_trig(d, a)
        elif c == "game":
            cmd_game(d, a)
        elif c == "profile":
            cmd_profile(d, a)
        else:
            usage()
    return 0


if __name__ == "__main__":
    sys.exit(main())
