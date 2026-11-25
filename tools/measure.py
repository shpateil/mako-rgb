#!/usr/bin/python3
# кто требует большие размеры: минимальный и натуральный размер каждого ребенка
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

import panel  # noqa: E402


def walk(w, depth=0):
    yield depth, w
    c = w.get_first_child()
    while c:
        yield from walk(c, depth + 1)
        c = c.get_next_sibling()


def measure(win):
    print("окно:", win.get_width(), "x", win.get_height())
    for depth, w in walk(win):
        if depth > 4:
            continue
        name = type(w).__name__
        css = " ".join(w.get_css_classes())
        mw, mh, nw, nh = 0, 0, 0, 0
        try:
            ok, mw, mh, _, _ = w.measure(Gtk.Orientation.HORIZONTAL, -1)
            ok2, nw, nh, _, _ = w.measure(Gtk.Orientation.VERTICAL, -1)
        except Exception:
            pass
        txt = w.get_text()[:18] if isinstance(w, Gtk.Label) else ""
        print("%s%-14s %-14s %-18r min_w=%4d min_h=%4d nat_h=%4d"
              % ("  " * depth, name, css, txt, mw, mh, nh))


class App(Gtk.Application):
    def do_activate(self):
        prov = Gtk.CssProvider()
        prov.load_from_data(panel.CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gtk.Widget.get_display(Gtk.Window()), prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        win = panel.Panel(self)
        win.present()

        def go():
            measure(win)
            self.quit()
            return False

        GLib.timeout_add(900, go)


if __name__ == "__main__":
    sys.exit(App(application_id="fun.shpateil.mako.measure").run([sys.argv[0]]))
