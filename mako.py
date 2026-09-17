#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mako - управление rgb подсветкой клавиатуры dexp mako (2e3c:c365)

использование:
  mako key <keyname> <r> <g> <b> [sec]   - покрасить одну клавишу
  mako row <1-5> <r> <g> <b> [sec]       - покрасить ряд
  mako all <r> <g> <b> [sec]             - покрасить все клавиши
  mako rows [sec]                        - все ряды разными цветами
  mako off [sec]                         - выключить подсветку
  mako blink <r> <g> <b> [cycles]        - мигание всей клавиатуры
  mako notify [color] [cycles]           - уведомление (мигание цветом)
  mako list                              - список клавиш
"""
import argparse
import os
import stat
import sys
import time
from pathlib import Path

VID = 0x2E3C
PID = 0xC365
INTERFACE = '02'


def find_hidraw(root='/sys/class/hidraw'):
    for entry in Path(root).glob('hidraw*'):
        device = (entry / 'device').resolve()
        try:
            info = (device / 'uevent').read_text()
        except OSError:
            continue
        interface = device.parent / 'bInterfaceNumber'
        if ('HID_ID=0003:00002E3C:0000C365' in info
                and interface.exists()
                and interface.read_text().strip() == INTERFACE):
            return '/dev/' + entry.name
    raise RuntimeError('интерфейс подсветки mako не найден')


# маппинг клавиш: имя -> (x, y)
KEY_NAMES = {
    # x=0
    'esc': (0, 0), '1': (0, 1), '2': (0, 2), '3': (0, 3), '4': (0, 4),
    '5': (0, 5), '6': (0, 6), '7': (0, 7), '8': (0, 8), '9': (0, 9),
    '0': (0, 10), '-': (0, 11), '=': (0, 12), 'backspace': (0, 13),
    'ins': (0, 14), 'tab': (0, 15), 'q': (0, 16), 'w': (0, 17),
    'e': (0, 18), 'r': (0, 19), 't': (0, 20), 'y': (0, 21),
    # x=1
    'u': (1, 21), 'i': (1, 20), 'o': (1, 19), 'p': (1, 18),
    '[': (1, 17), ']': (1, 16), '\\': (1, 15), 'del': (1, 14),
    'caps': (1, 13), 'a': (1, 12), 's': (1, 11), 'd': (1, 10),
    'f': (1, 9), 'g': (1, 8), 'h': (1, 7), 'j': (1, 6),
    'k': (1, 5), 'l': (1, 4), ';': (1, 3), "'": (1, 2),
    'enter': (1, 1), 'pgup': (1, 0),
    # x=2
    'lshift': (2, 0), 'z': (2, 1), 'x': (2, 2), 'c': (2, 3),
    'v': (2, 4), 'b': (2, 5), 'n': (2, 6), 'm': (2, 7),
    ',': (2, 8), '.': (2, 9), '/': (2, 10), 'rshift': (2, 11),
    'up': (2, 12), 'pgdn': (2, 13), 'lctrl': (2, 14), 'lwin': (2, 15),
    'lalt': (2, 16), 'space': (2, 17), 'ralt': (2, 18),
    'fn': (2, 19), 'rctrl': (2, 20), 'left': (2, 21),
    # x=3
    'down': (3, 21), 'right': (3, 20),
}

# маппинг (x, y) -> (grp, offset) в кадре 0x0f
XY_TO_GRP = {
    (0, 0): (1, 18), (0, 1): (1, 21), (0, 2): (1, 24), (0, 3): (1, 27),
    (0, 4): (1, 30), (0, 5): (1, 33), (0, 6): (1, 36), (0, 7): (1, 39),
    (0, 8): (1, 42), (0, 9): (1, 45), (0, 10): (1, 48), (0, 11): (1, 51),
    (0, 12): (1, 54), (0, 13): (2, 6), (0, 14): (2, 12), (0, 15): (2, 30),
    (0, 16): (2, 33), (0, 17): (2, 36), (0, 18): (2, 39), (0, 19): (2, 42),
    (0, 20): (2, 45), (0, 21): (2, 48),
    (1, 21): (2, 51), (1, 20): (2, 54), (1, 19): (2, 57), (1, 18): (3, 6),
    (1, 17): (3, 9), (1, 16): (3, 12), (1, 15): (3, 18), (1, 14): (3, 24),
    (1, 13): (3, 42), (1, 12): (3, 48), (1, 11): (3, 51), (1, 10): (3, 54),
    (1, 9): (3, 57), (1, 8): (4, 6), (1, 7): (4, 9), (1, 6): (4, 12),
    (1, 5): (4, 15), (1, 4): (4, 18), (1, 3): (4, 21), (1, 2): (4, 24),
    (1, 1): (4, 30), (1, 0): (4, 36),
    (2, 0): (4, 54), (2, 1): (5, 6), (2, 2): (5, 9), (2, 3): (5, 12),
    (2, 4): (5, 15), (2, 5): (5, 18), (2, 6): (5, 21), (2, 7): (5, 24),
    (2, 8): (5, 27), (2, 9): (5, 30), (2, 10): (5, 33), (2, 11): (5, 39),
    (2, 12): (5, 45), (2, 13): (5, 48), (2, 14): (6, 12), (2, 15): (6, 15),
    (2, 16): (6, 18), (2, 17): (6, 30), (2, 18): (6, 39), (2, 19): (6, 45),
    (2, 20): (6, 48), (2, 21): (6, 54),
    (3, 21): (6, 57), (3, 20): (7, 6),
}


def send_packet(pkt):
    path = find_hidraw()
    # без o_creat: отключённая клавиатура не должна превращаться в файл
    fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW)
    try:
        if not stat.S_ISCHR(os.fstat(fd).st_mode):
            raise RuntimeError(f'{path} не является устройством')
        if os.write(fd, bytes(pkt)) != len(pkt):
            raise OSError('неполная запись hid пакета')
    finally:
        os.close(fd)


def init():
    """вход в пер-кей режим, команда 0x17"""
    pkt = bytearray(64)
    pkt[0] = 0x01
    pkt[1] = 0x17
    pkt[5] = 0x01
    pkt[6] = 0x01
    send_packet(pkt)


def build_frame(color_map):
    """кадр 0x0f. color_map: (x, y) -> (r, g, b)"""
    frame = []
    for grp in range(0, 8):
        pkt = bytearray(64)
        pkt[0] = 0x01
        pkt[1] = 0x0f
        pkt[2] = 0x00
        pkt[3] = 0x00
        pkt[4] = grp
        pkt[5] = 0x12 if grp == 7 else 0x36
        for (x, y), (g, off) in XY_TO_GRP.items():
            if g == grp and (x, y) in color_map:
                r, gg, b = color_map[(x, y)]
                pkt[off] = r
                pkt[off + 1] = gg
                pkt[off + 2] = b
        frame.append(bytes(pkt))
    for grp in range(0, 2):
        pkt = bytearray(64)
        pkt[0] = 0x01
        pkt[1] = 0x0f
        pkt[2] = 0x01
        pkt[3] = 0x00
        pkt[4] = grp
        pkt[5] = 0x2d if grp == 1 else 0x36
        frame.append(bytes(pkt))
    return frame


def send_loop(color_map, duration):
    """переотправлять кадр указанное время, потом клавиатура вернётся в свой режим"""
    init()
    frame = build_frame(color_map)
    for _ in range(3):
        for pkt in frame:
            send_packet(pkt)
    start = time.time()
    while time.time() - start < duration:
        for pkt in frame:
            send_packet(pkt)
        time.sleep(0.05)


def cmd_key(name, r, g, b, duration):
    color_map = {KEY_NAMES[name]: (r, g, b)}
    send_loop(color_map, duration)
    print(f'клавиша {name} -> ({r}, {g}, {b}) на {duration}с')


def cmd_row(row, r, g, b, duration):
    names = ROWS[str(row)]
    color_map = {KEY_NAMES[n]: (r, g, b) for n in names}
    send_loop(color_map, duration)
    print(f'ряд {row} -> ({r}, {g}, {b}) на {duration}с')


def cmd_all(r, g, b, duration):
    color_map = {xy: (r, g, b) for xy in XY_TO_GRP}
    send_loop(color_map, duration)
    print(f'все клавиши -> ({r}, {g}, {b}) на {duration}с')


# физические ряды клавиатуры (65% раскладка, правый блок встроен)
ROWS = {
    '1': ['esc', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=', 'backspace', 'ins'],
    '2': ['tab', 'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '[', ']', '\\', 'del'],
    '3': ['caps', 'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';', "'", 'enter', 'pgup'],
    '4': ['lshift', 'z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '/', 'rshift', 'up', 'pgdn'],
    '5': ['lctrl', 'lwin', 'lalt', 'space', 'ralt', 'fn', 'rctrl', 'left', 'down', 'right'],
}


def cmd_rows(duration):
    """покрасить каждый физический ряд в свой цвет"""
    colors = {
        '1': (255, 0, 0),
        '2': (0, 255, 0),
        '3': (0, 0, 255),
        '4': (255, 255, 0),
        '5': (255, 255, 255),
    }
    color_map = {}
    for row, names in ROWS.items():
        for name in names:
            color_map[KEY_NAMES[name]] = colors[row]
    send_loop(color_map, duration)
    print(f'все ряды разными цветами на {duration}с')


def cmd_off(duration):
    cmd_all(0, 0, 0, duration)


def cmd_blink(r, g, b, cycles, on_time=0.4, off_time=0.4):
    """мигание всей клавиатуры цветом"""
    init()
    on_frame = build_frame({xy: (r, g, b) for xy in XY_TO_GRP})
    off_frame = build_frame({xy: (0, 0, 0) for xy in XY_TO_GRP})
    for _ in range(cycles):
        for pkt in on_frame:
            send_packet(pkt)
        time.sleep(on_time)
        for pkt in off_frame:
            send_packet(pkt)
        time.sleep(off_time)
    print(f'мигание ({r}, {g}, {b}) x{cycles}')


NOTIFY_COLORS = {
    'purple': (255, 0, 255),
    'pink': (255, 105, 180),
    'red': (255, 0, 0),
    'green': (0, 255, 0),
    'blue': (0, 0, 255),
    'yellow': (255, 255, 0),
    'white': (255, 255, 255),
    'cyan': (0, 255, 255),
    'orange': (255, 165, 0),
}


def cmd_notify(color, cycles):
    r, g, b = NOTIFY_COLORS[color]
    cmd_blink(r, g, b, cycles)
    print(f'уведомление: {color} x{cycles}')


def cmd_list():
    print('клавиши:')
    for name in sorted(KEY_NAMES.keys()):
        print(f'  {name}')


def uint8(value):
    try:
        v = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f'{value!r} не число')
    if not 0 <= v <= 255:
        raise argparse.ArgumentTypeError(f'{v} вне диапазона 0..255')
    return v


def positive_int(value):
    try:
        v = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f'{value!r} не число')
    if v <= 0:
        raise argparse.ArgumentTypeError(f'{v} должно быть больше 0')
    return v


def main():
    parser = argparse.ArgumentParser(
        prog='mako',
        description='управление rgb подсветкой клавиатуры dexp mako (2e3c:c365)')
    sub = parser.add_subparsers(dest='command', required=True)

    p_key = sub.add_parser('key', help='покрасить одну клавишу')
    p_key.add_argument('keyname', help='имя клавиши, список: mako list')
    p_key.add_argument('rgb', nargs=3, type=uint8, metavar=('R', 'G', 'B'))
    p_key.add_argument('sec', nargs='?', type=positive_int, default=10)

    p_row = sub.add_parser('row', help='покрасить ряд')
    p_row.add_argument('row', choices=ROWS.keys())
    p_row.add_argument('rgb', nargs=3, type=uint8, metavar=('R', 'G', 'B'))
    p_row.add_argument('sec', nargs='?', type=positive_int, default=10)

    p_all = sub.add_parser('all', help='покрасить все клавиши')
    p_all.add_argument('rgb', nargs=3, type=uint8, metavar=('R', 'G', 'B'))
    p_all.add_argument('sec', nargs='?', type=positive_int, default=10)

    p_rows = sub.add_parser('rows', help='все ряды разными цветами')
    p_rows.add_argument('sec', nargs='?', type=positive_int, default=10)

    p_off = sub.add_parser('off', help='выключить подсветку')
    p_off.add_argument('sec', nargs='?', type=positive_int, default=10)

    p_blink = sub.add_parser('blink', help='мигание всей клавиатуры')
    p_blink.add_argument('rgb', nargs=3, type=uint8, metavar=('R', 'G', 'B'))
    p_blink.add_argument('cycles', nargs='?', type=positive_int, default=5)

    p_notify = sub.add_parser('notify', help='уведомление (мигание цветом)')
    p_notify.add_argument('color', nargs='?', choices=NOTIFY_COLORS.keys(), default='purple')
    p_notify.add_argument('cycles', nargs='?', type=positive_int, default=2)

    sub.add_parser('list', help='список клавиш')

    args = parser.parse_args()
    if args.command == 'key':
        if args.keyname.lower() not in KEY_NAMES:
            parser.error(f'неизвестная клавиша: {args.keyname}, список: mako list')
        cmd_key(args.keyname.lower(), *args.rgb, args.sec)
    elif args.command == 'row':
        cmd_row(args.row, *args.rgb, args.sec)
    elif args.command == 'all':
        cmd_all(*args.rgb, args.sec)
    elif args.command == 'rows':
        cmd_rows(args.sec)
    elif args.command == 'off':
        cmd_off(args.sec)
    elif args.command == 'blink':
        cmd_blink(*args.rgb, args.cycles)
    elif args.command == 'notify':
        cmd_notify(args.color, args.cycles)
    elif args.command == 'list':
        cmd_list()


if __name__ == '__main__':
    main()
