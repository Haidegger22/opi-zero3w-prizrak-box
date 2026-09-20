#!/bin/bash
# Запуск Prizrak-Box так, чтобы он открывался из меню на Orange Pi Zero 3W.
#
# Две причины, почему это нужно:
#   1. На плате лежит графическая обёртка PowerVR (libEGL в /usr/local/lib), которую
#      движок интерфейса не принимает — приложение падает при запуске. Лечится запуском
#      с системным Mesa: LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu (+ софтовый рендер).
#   2. Окно объявляет минимум 960x660, а рабочая область экрана 1024x560 — низ интерфейса
#      уезжает за край. Скрипт снимает жёсткий минимум и подгоняет окно под экран.
#
# Установка: положить рядом win-fit.py и сослаться на этот скрипт в ярлыке меню:
#   Exec=<путь>/prizrak-launch.sh %u
#
# ---- настройки конкретной машины (правьте под себя) ----
APP_BIN="/usr/bin/prizrak-box"
WINDOW_NAME="Prizrak-Box"
MESA_LIB_PATH="/usr/lib/aarch64-linux-gnu"   # системный Mesa вместо обёртки из /usr/local/lib
WIN_W=1024
WIN_H=560
WIN_X=0
WIN_Y=40
# --------------------------------------------------------

export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export LD_LIBRARY_PATH="$MESA_LIB_PATH"
export LIBGL_ALWAYS_SOFTWARE=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# уже запущен — просто поднимаем окно
if pgrep -f "$APP_BIN" >/dev/null; then
  WID=$(xdotool search --name "$WINDOW_NAME" 2>/dev/null | tail -1)
  [ -n "$WID" ] && xdotool windowactivate --sync "$WID" 2>/dev/null
  exit 0
fi

setsid nohup "$APP_BIN" "$@" >/tmp/prizrak-app.log 2>&1 &

# ждём появления окна (плата небыстрая) и подгоняем его под экран
for _ in $(seq 1 45); do
  xdotool search --name "$WINDOW_NAME" >/dev/null 2>&1 && break
  sleep 2
done
sleep 5
python3 "$SCRIPT_DIR/win-fit.py" "$WINDOW_NAME" "$WIN_W" "$WIN_H" "$WIN_X" "$WIN_Y"
exit 0
