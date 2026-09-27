import argparse
import contextlib
import io
import itertools
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mako


class TestKeys(unittest.TestCase):
    def test_all_rows_covered(self):
        for row, names in mako.ROWS.items():
            for name in names:
                self.assertIn(name, mako.KEY_NAMES, name)

    def test_unique_xy(self):
        xy = list(mako.KEY_NAMES.values())
        self.assertEqual(len(xy), len(set(xy)), 'дубликат (x, y) в KEY_NAMES')

    def test_xy_to_grp_covers_keys(self):
        for name, xy in mako.KEY_NAMES.items():
            self.assertIn(xy, mako.XY_TO_GRP, name)

    def test_list(self):
        out = io.StringIO()
        with redirect_stdout(out):
            mako.cmd_list()
        self.assertIn('  esc', out.getvalue())
        self.assertIn('  space', out.getvalue())


class TestProtocol(unittest.TestCase):
    def test_init_packet(self):
        pkt = bytearray(64)
        pkt[0] = 0x01
        pkt[1] = 0x17
        pkt[5] = 0x01
        pkt[6] = 0x01
        sent = []
        with mock.patch.object(mako, 'send_packet', side_effect=sent.append):
            mako.init()
        self.assertEqual(len(sent), 1)
        self.assertEqual(bytes(sent[0]), bytes(pkt))

    def test_frame_shape(self):
        frame = mako.build_frame({(0, 0): (1, 2, 3)})
        # 8 групп half=0 + 2 группы half=1
        self.assertEqual(len(frame), 10)
        for pkt in frame:
            self.assertEqual(len(pkt), 64)
            self.assertEqual(pkt[0], 0x01)
            self.assertEqual(pkt[1], 0x0f)
        # esc (0,0) -> grp 1, offset 18
        self.assertEqual(frame[1][4], 1)
        self.assertEqual(frame[1][18:21], bytes([1, 2, 3]))
        # half=1 группы без цветов
        self.assertEqual(frame[8][2], 0x01)
        self.assertEqual(frame[9][2], 0x01)

    def test_init_before_loop(self):
        sent = []
        with mock.patch.object(mako, 'send_packet', side_effect=sent.append):
            with mock.patch.object(mako.time, 'sleep'):
                with mock.patch.object(mako.time, 'time', side_effect=[0, 11]):
                    mako.send_loop({(0, 0): (9, 9, 9)}, 10)
        self.assertEqual(sent[0][1], 0x17, 'первый пакет не 0x17')
        self.assertTrue(any(p[1] == 0x0f for p in sent), 'нет кадра 0x0f')

    def test_no_global_0x07(self):
        # 0x07 гасит клавиатуру целиком, посылать его нельзя. проверка
        # отрицательная, поэтому сама по себе вхолостую: если blink вообще
        # ничего не отправит, тест останется зелёным. поэтому сначала
        # утверждаем что кадры 0x0f ушли, и только потом проверяем отсутствие 0x07
        sent = []
        with mock.patch.object(mako, 'send_packet', side_effect=sent.append):
            with mock.patch.object(mako.time, 'sleep'):
                with mock.patch.object(mako.time, 'time', side_effect=[0, 11]):
                    mako.send_loop({(0, 0): (9, 9, 9)}, 10)
                    blink_start = len(sent)
                    mako.cmd_blink(255, 0, 255, 2)

        frames = [p for p in sent if p[1] == 0x0f]
        self.assertTrue(frames, 'ни одного кадра 0x0f не отправлено')
        blink = sent[blink_start:]
        self.assertTrue(blink, 'blink ничего не отправил, проверка 0x07 вхолостую')
        self.assertTrue(any(p[1] == 0x0f for p in blink),
                        'blink не отправил ни одного кадра 0x0f')
        # в каждом кадре 0x0f цвет мигания должен реально стоять
        self.assertTrue(any(p[18:21] == bytes([255, 0, 255]) for p in blink if p[1] == 0x0f),
                        'цвет 255,0,255 не попал ни в один кадр')
        for p in sent:
            self.assertNotEqual(p[1], 0x07, 'команда 0x07 запрещена')


class TestValidation(unittest.TestCase):
    def test_uint8_range(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            mako.uint8('256')
        with self.assertRaises(argparse.ArgumentTypeError):
            mako.uint8('-1')
        with self.assertRaises(argparse.ArgumentTypeError):
            mako.uint8('abc')
        self.assertEqual(mako.uint8('0'), 0)
        self.assertEqual(mako.uint8('255'), 255)

    def test_positive_time(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            mako.positive_int('0')
        with self.assertRaises(argparse.ArgumentTypeError):
            mako.positive_int('-5')
        with self.assertRaises(argparse.ArgumentTypeError):
            mako.positive_int('abc')
        self.assertEqual(mako.positive_int('1'), 1)

    # эти три проверяют разбор argv. ожидаем что main() выйдет через SystemExit
    # на этапе парсинга, до обращения к железу. send_packet замокан на случай
    # если валидация всё же не сработает: без мока тест дёрнул бы живую
    # клавиатуру вместо того чтобы просто упасть

    def _run_argv(self, argv):
        sent = []
        err = io.StringIO()
        with mock.patch('sys.argv', argv):
            with mock.patch.object(mako, 'send_packet', side_effect=sent.append):
                with mock.patch.object(mako.time, 'sleep'):
                    # send_loop крутится по time.time(), без мока он ушёл бы
                    # в реальный десятисекундный цикл и тест повис бы вместо
                    # того чтобы упасть. счётчик делает цикл конечным
                    ticks = itertools.count(0, 0.5)
                    with mock.patch.object(mako.time, 'time',
                                           side_effect=lambda: next(ticks)):
                        with contextlib.redirect_stderr(err):
                            with self.assertRaises(SystemExit):
                                mako.main()
        return sent, err.getvalue()

    def test_rgb_parsing(self):
        sent, err = self._run_argv(['mako', 'all', '300', '0', '0'])
        self.assertIn('0..255', err, 'нет сообщения о диапазоне')
        self.assertEqual(sent, [], 'валидация не остановила запись в ленту')

    def test_unknown_key(self):
        sent, err = self._run_argv(['mako', 'key', 'nokey', '1', '2', '3'])
        self.assertIn('неизвестная клавиша', err)
        self.assertEqual(sent, [], 'валидация не остановила запись в ленту')

    def test_unknown_color(self):
        sent, err = self._run_argv(['mako', 'notify', 'gold'])
        self.assertIn('invalid choice', err)
        self.assertEqual(sent, [], 'валидация не остановила запись в ленту')


class TestDeviceSafety(unittest.TestCase):
    def _fake_sysfs(self, tmp, iface, name='hidraw1'):
        # раскладка повторяет настоящий sysfs:
        # /sys/class/hidraw/hidrawN -> ../../devices/.../0003:2E3C:C365.000X/hidraw/hidrawN
        # внутри class-узла симлинк device на hid-устройство
        # bInterfaceNumber лежит в родиле этого устройства, рядом с другими b* атрибутами
        # имя каталога устройства уникально на каждый интерфейс, как в sysfs
        # число 000X вытаскиваем из имени узла, чтобы интерфейсы не сливались
        suffix = '0001' if name == 'hidraw1' else name.replace('hidraw', '000')
        devdir = (tmp / 'devices' / 'pci0000:00' / 'usb1' / '1-2'
                  / f'1-2:1.{iface}' / f'0003:2E3C:C365.{suffix}')
        devdir.mkdir(parents=True)
        (devdir / 'uevent').write_text('DRIVER=hid-generic HID_ID=0003:00002E3C:0000C365\n')
        (devdir.parent / 'bInterfaceNumber').write_text(iface + '\n')

        entry = tmp / name
        entry.mkdir()
        os.symlink(os.path.relpath(devdir, entry), entry / 'device')
        return tmp

    def test_find_hidraw(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fake_sysfs(Path(tmp), '02')
            self.assertEqual(mako.find_hidraw(root), '/dev/hidraw1')

    def test_find_hidraw_wrong_interface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fake_sysfs(Path(tmp), '00')
            with self.assertRaises(RuntimeError):
                mako.find_hidraw(root)

    def test_find_hidraw_no_device(self):
        # пустое дерево: ни одного hidraw, должен быть честный отказ
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                mako.find_hidraw(Path(tmp))

    def test_find_hidraw_picks_backlight(self):
        # три интерфейса, подсветка не первая по порядку: 01 должен быть отброшен
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fake_sysfs(root, '00', name='hidraw1')
            self._fake_sysfs(root, '01', name='hidraw2')
            self._fake_sysfs(root, '02', name='hidraw3')
            self.assertEqual(mako.find_hidraw(root), '/dev/hidraw3')

    # ниже тесты записи. find_hidraw тут обязателен: send_packet зовёт его
    # до os.open, и без мока тест падает на машине без клавиатуры

    def test_send_rejects_regular_file(self):
        # обычный файл вместо hidraw не должен получить запись
        with mock.patch.object(mako, 'find_hidraw', return_value='/dev/hidraw9'):
            with mock.patch.object(mako.os, 'open', return_value=42):
                with mock.patch.object(mako.os, 'fstat') as fake_fstat:
                    fake_fstat.return_value.st_mode = stat.S_IFREG | 0o644
                    with mock.patch.object(mako.os, 'close'):
                        with mock.patch.object(mako.os, 'write') as fake_write:
                            with self.assertRaises(RuntimeError):
                                mako.send_packet(bytearray(64))
                            fake_write.assert_not_called()

    def test_send_full_write(self):
        with mock.patch.object(mako, 'find_hidraw', return_value='/dev/hidraw9'):
            with mock.patch.object(mako.os, 'open', return_value=42):
                with mock.patch.object(mako.os, 'fstat') as fake_fstat:
                    fake_fstat.return_value.st_mode = stat.S_IFCHR | 0o600
                    with mock.patch.object(mako.os, 'close'):
                        with mock.patch.object(mako.os, 'write', return_value=10) as fake_write:
                            mako.send_packet(bytearray(10))
                            fake_write.assert_called_once()

    def test_send_partial_write(self):
        with mock.patch.object(mako, 'find_hidraw', return_value='/dev/hidraw9'):
            with mock.patch.object(mako.os, 'open', return_value=42):
                with mock.patch.object(mako.os, 'fstat') as fake_fstat:
                    fake_fstat.return_value.st_mode = stat.S_IFCHR | 0o600
                    with mock.patch.object(mako.os, 'close'):
                        with mock.patch.object(mako.os, 'write', return_value=5):
                            with self.assertRaises(OSError):
                                mako.send_packet(bytearray(64))

    def test_send_no_o_creat(self):
        # без O_NOFOLLOW|O_CREAT отключённая клавиатура превратилась бы в файл
        with mock.patch.object(mako, 'find_hidraw', return_value='/dev/hidraw9'):
            with mock.patch.object(mako.os, 'open', return_value=42) as fake_open:
                with mock.patch.object(mako.os, 'fstat') as fake_fstat:
                    fake_fstat.return_value.st_mode = stat.S_IFCHR | 0o600
                    with mock.patch.object(mako.os, 'close'):
                        with mock.patch.object(mako.os, 'write', return_value=64):
                            mako.send_packet(bytearray(64))
                            flags = fake_open.call_args[0][1]
        self.assertFalse(flags & os.O_CREAT, 'O_CREAT нельзя при записи в hidraw')
        self.assertTrue(flags & os.O_NOFOLLOW, 'O_NOFOLLOW обязателен')


if __name__ == '__main__':
    unittest.main()
