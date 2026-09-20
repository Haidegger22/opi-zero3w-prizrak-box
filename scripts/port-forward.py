#!/usr/bin/env python3
"""Проброс локального порта: 127.0.0.1:7890 → 127.0.0.1:9697.

Зачем: прокси-клиент слушает свой порт (9697), а приложения и скрипты, настроенные
раньше, ходят на старый (7890) — и остаются без интернета. Проброс закрывает вопрос
разом, не требуя правок в каждом приложении — включая Flatpak-приложения, которые
не видят переменные окружения хоста.

ВАЖНО про таймауты: у долгих соединений (Telegram long-poll, WebSocket, стримы) бывают
паузы в десятки секунд. Если оставить у сокета рабочий таймаут, такой поток обрывается
на первой же паузе — поэтому после установки соединения таймаут снимается (settimeout(None)),
а ограничение по времени применяется только к самому подключению.

Настройки — константами ниже. Запуск: python3 port-forward.py
"""
import logging
import socket
import sys
import threading

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 7890        # порт, на который ходят приложения
TARGET_HOST = "127.0.0.1"
TARGET_PORT = 9697        # порт, который реально слушает прокси-клиент
CONNECT_TIMEOUT = 15      # только на подключение, не на обмен данными
BUFFER = 65536

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s",
                    stream=sys.stdout)


def pipe(src: socket.socket, dst: socket.socket) -> None:
    """Перекачка данных в одну сторону до закрытия соединения."""
    try:
        while True:
            data = src.recv(BUFFER)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for sock in (src, dst):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def handle(client: socket.socket, addr) -> None:
    try:
        upstream = socket.create_connection((TARGET_HOST, TARGET_PORT),
                                            timeout=CONNECT_TIMEOUT)
    except OSError as e:
        logging.warning("нет соединения с %s:%s (%s), клиент %s отброшен",
                        TARGET_HOST, TARGET_PORT, e, addr)
        client.close()
        return

    # снимаем таймаут: иначе длинные паузы в обмене (long-poll, стримы) рвут соединение
    client.settimeout(None)
    upstream.settimeout(None)

    threads = [
        threading.Thread(target=pipe, args=(client, upstream), daemon=True),
        threading.Thread(target=pipe, args=(upstream, client), daemon=True),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for sock in (client, upstream):
        try:
            sock.close()
        except OSError:
            pass


def main() -> int:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((LISTEN_HOST, LISTEN_PORT))
    except OSError as e:
        logging.error("не удалось занять %s:%s — %s", LISTEN_HOST, LISTEN_PORT, e)
        return 1
    server.listen(64)
    logging.info("проброс запущен: %s:%s → %s:%s (таймаут только на подключение)",
                 LISTEN_HOST, LISTEN_PORT, TARGET_HOST, TARGET_PORT)
    try:
        while True:
            client, addr = server.accept()
            threading.Thread(target=handle, args=(client, addr), daemon=True).start()
    except KeyboardInterrupt:
        logging.info("остановлено вручную")
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
