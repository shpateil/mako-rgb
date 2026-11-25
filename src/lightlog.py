#!/usr/bin/python3
# логгер подсветки: раз в секунду читает состояние и пишет только изменения
# ничего не записывает в клавиатуру, только читает (cmd 07 01)
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mako  # noqa: E402

LOG = Path.home() / ".local/share/mako/light-log.txt"


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    prev = None
    dev = None
    while True:
        try:
            if dev is None:
                dev = mako.Dev()
                with open(LOG, "a") as f:
                    f.write(f"--- подключился {dev.node} {time.strftime('%F %T')}\n")
            st = mako.read_light(dev)
            if st is None:
                # узел мог отвалиться, переподключимся
                dev.close()
                dev = None
                time.sleep(1)
                continue
            if st != prev:
                line = time.strftime("%F %T") + " " + json.dumps(st, ensure_ascii=False)
                with open(LOG, "a") as f:
                    f.write(line + "\n")
                if prev is not None:
                    print(line, flush=True)
                prev = st
        except (OSError, SystemExit):
            if dev:
                try:
                    dev.close()
                except OSError:
                    pass
            dev = None
            time.sleep(1)
            continue
        time.sleep(1)


if __name__ == "__main__":
    main()
