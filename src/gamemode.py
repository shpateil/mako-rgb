#!/usr/bin/python3
# gamemode -- игровой режим mako: переключатель триггеров одной командой
#
# первый запуск: всё на минимум + rapid trigger, защитные клавиши на максимум
# второй запуск: всё на заводские 1.70, защитные остаются на максимуме
#
# подсветку не трогает вообще.
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mako  # noqa: E402

STATE = Path.home() / ".local/share/mako/gamemode.json"

# клавиши которые должны продавливаться глубоко: случайное нажатие на них
# в игре стоит дорого (shift сюда не входит, он должен быть быстрым)
LOUD = ["\\|", "Back", "Up", "Down", "Left", "Right"]

# режим игры
GAME_REST = {"travel": 0.10, "mode": 12, "i1": 0.05, "i2": 0.05}
GAME_LOUD = {"travel": 3.40, "mode": 0, "i1": 0.01, "i2": 0.01}

# откат
OFF_REST = {"travel": 1.70, "mode": 0, "i1": 0.01, "i2": 0.01}
OFF_LOUD = {"travel": 3.40, "mode": 0, "i1": 0.01, "i2": 0.01}


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return {"in_game": False}


def save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1))


def find_key(name):
    """находит клавишу по имени или коду, отдаёт (row, col) или None"""
    low = name.lower()
    for k in mako.load_layout():
        if k["name"].lower() == low or k["code"].lower() == low:
            return divmod(int(k["index"]), 22), k["name"]
    return None, None


def apply_group(d, targets, cfg, unit):
    """пишет одну группу и возвращает результат проверки"""
    mako.write_trigger(d, targets, cfg["mode"], cfg["travel"], cfg["i1"], cfg["i2"], unit)
    time.sleep(0.05)
    ok, bad = 0, []
    for row, col in targets:
        t = mako.read_trigger(d, row, col)
        if not t:
            bad.append((row, col, "нет ответа"))
            continue
        travel_ok = abs(t["travel"] * unit - cfg["travel"]) < 0.02
        mode_ok = t["mode"] == cfg["mode"] if cfg["mode"] else t["mode"] == 0
        if travel_ok and mode_ok:
            ok += 1
        else:
            bad.append((row, col, "ход %.2f вместо %.2f" % (t["travel"] * unit, cfg["travel"])))
    return ok, bad


def names_by_pos(positions):
    idx = {divmod(int(k["index"]), 22): k["name"] for k in mako.load_layout()}
    return [idx.get(p, "%d,%d" % p) for p in positions]


def main():
    st = load_state()
    game = not st.get("in_game", False)

    try:
        d = mako.Dev()
    except SystemExit:
        print("не получилось: клавиатура не найдена (2e3c:c365)")
        return 2

    mt = mako.max_travel(d)
    if not mt:
        print("не получилось: клавиатура не ответила на запрос параметров свитча")
        d.close()
        return 2
    unit = mt["unit"]

    keys = mako.load_layout()
    loud_pos, loud_found, loud_missing = [], [], []
    for name in LOUD:
        pos, real = find_key(name)
        if pos:
            loud_pos.append(pos)
            loud_found.append(real)
        else:
            loud_missing.append(name)

    rest_pos = [divmod(int(k["index"]), 22) for k in keys
                if divmod(int(k["index"]), 22) not in loud_pos]

    if game:
        rest_cfg, loud_cfg = GAME_REST, GAME_LOUD
        title = "игровой режим включён"
    else:
        rest_cfg, loud_cfg = OFF_REST, OFF_LOUD
        title = "игровой режим выключен"

    print("%s" % title)
    print("")

    rest_ok, rest_bad = apply_group(d, rest_pos, rest_cfg, unit)
    loud_ok, loud_bad = apply_group(d, loud_pos, loud_cfg, unit)

    def describe(cfg):
        if cfg["mode"] == 12:
            return "%.2f мм + rapid trigger %.2f/%.2f мм" % (
                cfg["travel"], cfg["i1"], cfg["i2"])
        return "%.2f мм, rapid trigger выкл" % cfg["travel"]

    print("остальные %d клавиш: %s" % (len(rest_pos), describe(rest_cfg)))
    print("  подтверждено %d из %d" % (rest_ok, len(rest_pos)))
    print("глубокие %d клавиш (%s): %s" % (
        len(loud_pos), ", ".join(loud_found), describe(loud_cfg)))
    print("  подтверждено %d из %d" % (loud_ok, len(loud_pos)))

    if loud_missing:
        print("")
        print("не нашёл такие клавиши: %s" % ", ".join(loud_missing))

    problems = rest_bad + loud_bad
    if problems:
        print("")
        print("не получилось на %d клавишах:" % len(problems))
        idx = {divmod(int(k["index"]), 22): k["name"] for k in mako.load_layout()}
        for row, col, why in problems[:10]:
            print("  %-8s %s" % (idx.get((row, col), "%d,%d" % (row, col)), why))
        if len(problems) > 10:
            print("  и ещё %d" % (len(problems) - 10))
    else:
        print("")
        print("всё применилось, проверено чтением с клавиатуры")

    d.close()
    st["in_game"] = game
    save_state(st)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
