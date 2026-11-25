#!/usr/bin/python3
# краска отдельных клавиш: чистая таблица + указанные клавиши, режим custom
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mako  # noqa: E402

LAYOUT = HERE.parent / "data" / "layout-win68.json"
TABLE_BYTES = 396
CHUNK = 54


def read_table(d, slot=0, wait=1.0):
    chunks = {}
    d.read(0.03)
    d.send(mako.frame(0x09, 0x80 | slot))
    for b in d.read(wait, cmd=0x09):
        p = b[1:]
        if p[1] != (0x80 | slot):
            continue
        page = (p[2] << 8) | p[3]
        n = p[4]
        if n:
            chunks[page] = list(p[5:5 + n])
    if len(chunks) < 8:
        return None
    table = bytearray()
    for page in range(8):
        table.extend(chunks[page])
    return table[:TABLE_BYTES]


def write_table(d, table, slot=0, gap=0.015):
    for page in range(8):
        d.read(0.015)
        d.send(mako.frame(0x09, slot, page, bytes(table[page * CHUNK:page * CHUNK + CHUNK])))
        time.sleep(gap)


def paint(d, colors_by_index, slot=0, brightness=None):
    table = bytearray(TABLE_BYTES)
    for idx, rgb in colors_by_index.items():
        off = int(idx) * 3
        if off + 2 < TABLE_BYTES:
            table[off:off + 3] = bytes(rgb)
    write_table(d, table, slot)
    time.sleep(0.15)
    st = mako.read_light(d) or {}
    st["mode"] = "custom"
    if brightness is not None:
        st["brightness"] = brightness
    mako.write_light(d, st)
    time.sleep(0.15)
    return read_table(d, slot)


if __name__ == "__main__":
    import json
    keys = json.load(open(LAYOUT))["keys"]
    d = mako.Dev()
    print("узел:", d.node)
    # все выключаем, W A S D красим
    targets = {"W": [255, 0, 60], "A": [60, 255, 0], "S": [0, 120, 255], "D": [255, 220, 0]}
    colors = {}
    for k in keys:
        if k["name"] in targets:
            colors[int(k["index"])] = targets[k["name"]]
    back = paint(d, colors)
    if back is None:
        print("таблица не прочиталась обратно")
    else:
        nz = {i // 3: list(back[i:i + 3]) for i in range(0, len(back), 3) if any(back[i:i + 3])}
        print("в таблице:", nz)
    print("подсветка:", mako.read_light(d))
    d.close()
