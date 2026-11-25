#!/usr/bin/python3
# дамп реальной геометрии виджетов панели: размеры, отступы, что не влезает
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

import panel  # noqa: E402


def walk(w, depth=0):
    out = [(depth, w)]
    c = w.get_first_child()
    while c:
        out.extend(walk(c, depth + 1))
        c = c.get_next_sibling()
    return out


def dump(win):
    alloc = win.get_width(), win.get_height()
    print("ОКНО: %d x %d" % alloc)
    rows = []
    for depth, w in walk(win):
        try:
            ok, r = w.compute_bounds(w.get_parent()) if w.get_parent() else (False, None)
        except Exception:
            ok, r = False, None
        if not ok or r is None:
            continue
        name = type(w).__name__
        css = " ".join(w.get_css_classes())
        txt = ""
        if isinstance(w, Gtk.Label):
            txt = w.get_text()[:20]
        rows.append((depth, name, css, txt,
                     r.origin.x, r.origin.y, r.size.width, r.size.height))
    for depth, name, css, txt, x, y, w, h in rows:
        flag = ""
        if w < 1 or h < 1:
            flag = "  <<< СХЛОПНУТ"
        print("%s%-13s %-20s %-22r x=%5.0f y=%5.0f w=%5.0f h=%4.0f%s"
              % ("  " * depth, name, css, txt, x, y, w, h, flag))


class App(Gtk.Application):
    def do_activate(self):
        prov = Gtk.CssProvider()
        prov.load_from_data(panel.CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gtk.Widget.get_display(self.get_active_window() or Gtk.Window()),
            prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        win = panel.Panel(self)
        win.present()

        def go():
            print("размер окна по умолчанию:", win.get_default_size())
            print("минимальный размер:", win.get_size_request())
            dump(win)
            self.quit()
            return False

        GLib.timeout_add(900, go)
        return False


def main():
    app = App(application_id="fun.shpateil.mako.geom")
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
