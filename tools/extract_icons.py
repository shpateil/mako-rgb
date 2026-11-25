#!/usr/bin/python3
# вытаскивает path-данные lucide в json. в минифицированном файле иконки это
# переменные (Keyboard:ri), а их значения массивы вида [[...]] дальше в коде.
import json
import re
from pathlib import Path

SRC = Path.home() / "web-packs/icons/lucide/lucide.min.js"
OUT = Path.home() / "projects/mako/data/icons.json"

WANT = [
    "Keyboard", "Palette", "Zap", "SlidersHorizontal", "Sparkles", "Sun", "Moon",
    "Check", "X", "RefreshCw", "RotateCcw", "Undo2", "ChevronDown", "Gauge",
    "Timer", "Activity", "Layers", "Paintbrush", "Droplet", "Rainbow",
    "Lightbulb", "Power", "Save", "Upload", "Download", "Trash2",
    "MousePointerClick", "ArrowLeftRight", "Circle", "Square", "Feather",
]


def find_var(src, name):
    """находит имя переменной-алиаса: Keyboard:ri  ->  ri"""
    m = re.search(r"[{,]" + name + r":([A-Za-z0-9_$]+)", src)
    return m.group(1) if m else None


def extract_array(src, var):
    """находит <var>=[[...]] и вытаскивает массив с балансировкой скобок"""
    m = re.search(r"[;,{]" + re.escape(var) + r"=(\[)", src)
    if not m:
        return None
    start = m.start(1)
    depth = 0
    for i in range(start, min(start + 6000, len(src))):
        ch = src[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                raw = src[start:i + 1]
                fixed = re.sub(r"([{,]\s*)([a-zA-Z][a-zA-Z0-9]*)\s*:", r'\1"\2":', raw)
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    return None
    return None


def main():
    src = SRC.read_text(encoding="utf-8")
    icons = {}
    for name in WANT:
        var = find_var(src, name)
        if not var:
            print("нет алиаса:", name)
            continue
        data = extract_array(src, var)
        if not data:
            print("нет данных:", name, "var=", var)
            continue
        icons[name] = data
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(icons, separators=(",", ":")))
    print("сохранил", len(icons), "иконок,", OUT.stat().st_size, "байт")
    print("keyboard:", json.dumps(icons.get("Keyboard"))[:220])


if __name__ == "__main__":
    main()
