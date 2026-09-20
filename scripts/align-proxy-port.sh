#!/bin/bash
# Свести порты прокси к тому, который слушает ваш клиент.
#
# Зачем: при смене прокси-клиента его ядро поднимается на другом порту, а ярлыки браузера,
# службы и скрипты продолжают ходить на старый — интернет «пропадает» при живом клиенте.
# Скрипт находит старый порт в настройках и заменяет его на новый, делая копии файлов.
#
# Запуск:  ./align-proxy-port.sh [--restart-agent]
#   --restart-agent — перезапустить службу агента Hermes, чтобы она перечитала настройки
#
# ---- настройки конкретной машины (правьте под себя) ----
OLD_PORT=7890                 # порт прежнего клиента
NEW_PORT=9697                 # порт, который слушает текущий клиент
AGENT_DROPIN="$HOME/.config/systemd/user/hermes-gateway.service.d/proxy.conf"
AGENT_UNIT="hermes-gateway"
BROWSER_DESKTOPS=("/usr/share/applications/chromium.desktop")
# свои скрипты, где порт прописан константой (можно дополнить или оставить пустым)
USER_SCRIPTS=("$HOME/.local/bin/dg" "$HOME/.local/bin/app-carousel-v.py")
# --------------------------------------------------------

set -u
RESTART_AGENT=0
[ "${1:-}" = "--restart-agent" ] && RESTART_AGENT=1

changed=0
backup_and_replace() {
  local file="$1"
  [ -f "$file" ] || return 1
  grep -q "127.0.0.1:$OLD_PORT" "$file" 2>/dev/null || return 1
  cp "$file" "$file.bak-$(date +%Y%m%d-%H%M)"
  sed -i "s|127.0.0.1:$OLD_PORT|127.0.0.1:$NEW_PORT|g" "$file"
  echo "  обновлён: $file"
  changed=$((changed + 1))
  return 0
}

echo "=== 1. ярлыки браузеров (нужен root) ==="
for desk in "${BROWSER_DESKTOPS[@]}"; do
  if grep -q "127.0.0.1:$OLD_PORT" "$desk" 2>/dev/null; then
    sudo cp "$desk" "$desk.bak-$(date +%Y%m%d-%H%M)"
    sudo sed -i "s|127.0.0.1:$OLD_PORT|127.0.0.1:$NEW_PORT|g" "$desk"
    echo "  обновлён: $desk"
    changed=$((changed + 1))
  fi
done

echo
echo "=== 2. настройки агента (прокси у службы) ==="
backup_and_replace "$AGENT_DROPIN" || echo "  $AGENT_DROPIN — не найден или уже настроен"

echo
echo "=== 3. свои скрипты и виджеты ==="
for f in "${USER_SCRIPTS[@]}"; do
  backup_and_replace "$f" || true
done

echo
echo "=== 4. что ещё осталось со старым портом ==="
grep -rIl "127.0.0.1:$OLD_PORT" \
  "$HOME/.hermes" "$HOME/.config" "$HOME/.local/bin" "$HOME"/*.py "$HOME"/Desktop 2>/dev/null \
  | grep -v '\.bak-' | head -10 | sed 's/^/  осталось: /' || echo "  чисто"

if [ "$RESTART_AGENT" = "1" ]; then
  echo
  echo "=== 5. перезапуск службы агента ==="
  systemctl --user daemon-reload
  systemctl --user restart "$AGENT_UNIT"
  sleep 20
  echo "  состояние: $(systemctl --user is-active "$AGENT_UNIT")"
  PID=$(systemctl --user show "$AGENT_UNIT" -p MainPID --value)
  tr '\0' '\n' < "/proc/$PID/environ" 2>/dev/null | grep -i '^TELEGRAM_PROXY' | sed 's/^/  /'
fi

echo
echo "=== 6. проверка ==="
echo "  слушаются порты: $(ss -tln | grep -E ":($OLD_PORT|$NEW_PORT)" | awk '{print $4}' | tr '\n' ' ')"
for url in https://www.youtube.com https://api.telegram.org; do
  printf "  %-28s → " "$url"
  curl -s -o /dev/null -w "%{http_code}\n" --max-time 15 -x "http://127.0.0.1:$NEW_PORT" "$url" 2>/dev/null || echo "нет ответа"
done
echo
echo "  изменилось файлов: $changed"
echo "  ВАЖНО: браузер нужно перезапустить — уже открытое окно держит старый порт в памяти."
