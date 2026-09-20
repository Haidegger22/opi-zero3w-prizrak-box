#!/usr/bin/env python3
"""Подгонка окна приложения под небольшой экран (X11).

Зачем: многие GUI-клиенты объявляют минимальный размер окна больше рабочей области
экрана (например, 960x660 при доступных 1024x560), из-за чего низ интерфейса уезжает
за край. Скрипт снимает у окна жёсткий минимум и ставит нужный размер.

Важно: некоторые приложения возвращают свой минимум обратно сразу после изменения —
тогда уменьшить окно не получится, и это ограничение самого приложения.

Запуск: win-fit.py "<Имя окна>" [ширина] [высота] [x] [y]
"""
import subprocess
import sys
import time

from Xlib import Xutil, display


def find_window(name):
    """Самое крупное окно, в имени которого встречается name."""
    try:
        ids = subprocess.run(["xdotool", "search", "--name", name],
                             capture_output=True, text=True, timeout=15).stdout.split()
    except Exception:
        return None
    best = None
    for wid in ids:
        try:
            geo = subprocess.run(["xdotool", "getwindowgeometry", wid],
                                 capture_output=True, text=True, timeout=15).stdout
        except Exception:
            continue
        for line in geo.splitlines():
            if "Geometry" in line:
                try:
                    w, h = (int(v) for v in line.split()[-1].split("x"))
                except ValueError:
                    continue
                if w > 300 and (best is None or w * h > best[1]):
                    best = (int(wid), w * h)
    return best[0] if best else None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    name = sys.argv[1]
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
    height = int(sys.argv[3]) if len(sys.argv) > 3 else 560
    x = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    y = int(sys.argv[5]) if len(sys.argv) > 5 else 40

    wid = find_window(name)
    if not wid:
        print(f"окно с именем '{name}' не найдено")
        return 1

    d = display.Display()
    win = d.create_resource_object("window", wid)
    try:
        win.set_wm_normal_hints(flags=Xutil.PMinSize, min_width=200, min_height=200)
        d.sync()
        print("минимум окна снят")
    except Exception as e:  # noqa: BLE001 — причина не критична, дальше просто пробуем размер
        print("не удалось снять минимум:", e)

    subprocess.run(["xdotool", "windowmap", str(wid)], timeout=15)
    subprocess.run(["xdotool", "windowsize", str(wid), str(width), str(height)], timeout=15)
    subprocess.run(["xdotool", "windowmove", str(wid), str(x), str(y)], timeout=15)
    time.sleep(1)

    geo = subprocess.run(["xdotool", "getwindowgeometry", str(wid)],
                         capture_output=True, text=True, timeout=15).stdout
    size = [line.split()[-1] for line in geo.splitlines() if "Geometry" in line]
    print(f"окно {wid}: размер {size[0] if size else '?'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
