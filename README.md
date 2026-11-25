# mako

лёгкий софт для клавиатуры dexp mako (= aula win68 he, usb 2e3c:c365) под linux.
без зависимостей: системный python3, hidraw напрямую.

## игровой режим

```bash
dm1     # первый раз — режим игры, второй раз — откат
```

| клавиши | в игре | откат |
|---|---|---|
| остальные 62 | 0.10 мм + RT 0.05/0.05 | 1.70 мм, RT выкл |
| `\` `backspace` `up` `down` `left` `right` | 3.40 мм, RT выкл | 3.40 мм, RT выкл |

shift (оба) идёт в низкие: должен срабатывать мгновенно.

подсветку не трогает. после каждого запуска печатает что выставилось и проверяет
обратным чтением, отдельно сообщает если что-то не подтвердилось.

## панель

`mako` в меню приложений, либо `python3 ~/projects/mako/src/panel.py`.
карта 68 клавиш, покраска мышкой, палитра и свой цвет, два цвета эффекта,
режимы, направление, скорость, яркость, радуга, rapid trigger с раздельными
нажатием и отпусканием. правки идут в черновик и уходят в клавиатуру только
по кнопке «применить». запускать лучше в отдельном рабочем столе.

## команды

```
makoctl info                     identity, подсветка, ход свитча
makoctl light                    показать подсветку
makoctl light ff5fd9             цвет
makoctl light ff5fd9 wave b3 s2  цвет + режим + яркость + скорость
makoctl backup                   бэкап подсветки и всех 68 триггеров
makoctl restore                  вернуть из бэкапа
makoctl trig list                все клавиши: режим и ход
makoctl trig get w
makoctl trig set w 0.5           ход 0.5мм
makoctl trig set w 1.2 0.3 0.3   rapid trigger
makoctl game on|off              wasd: 0.6мм + RT 0.15 / обратно 1.7
makoctl profile <имя> [save]     профили подсветки
```

## протокол

разобран не мной, источники:
- https://github.com/elberacasa/omakboard — notes/protocol-aula-ff1b.md
- https://github.com/MrWhosNexus/Aether-HE — GPL3, реестр плат
- https://github.com/marcodkts/aula-he-linux-fix — udev для WebHID

транспорт: hidraw узел с usage page 0xff1b usage 0x91, report id 1, 63 байта.
кадр: [cmd][sub][page hi][page lo][len][payload].

грабля: у команды 0x21 (hall effect / точка срабатывания) подкоманда лежит в байте 5, не в байте 1.
поля ответа считать от b[1:] (первый байт это report id).

## состояние

~/.local/share/mako/: light-backup.json, triggers-backup.json, profiles/, light-log.txt
