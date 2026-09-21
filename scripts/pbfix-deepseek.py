#!/usr/bin/env python3
"""Правило «DeepSeek идёт напрямую» в ядре Prizrak-Box (mihomo).

Собирает полный конфиг ядра (основа — шаблон клиента, сверху — прокси и группы активного
профиля, tun — из текущего состояния ядра), ставит правило `DOMAIN-SUFFIX,deepseek.com,DIRECT`
первым, применяет конфиг атомарно и возвращает ранее выбранную ноду.

Если правило уже в ядре — ничего не меняет (можно ставить по таймеру).

    python3 pbfix-deepseek.py            # применить (или ничего не делать, если уже есть)
    python3 pbfix-deepseek.py --check    # только показать правила ядра
"""
import glob, json, os, pathlib, re, subprocess, sys, urllib.request
import yaml

APP = pathlib.Path(os.environ.get("PB_HOME") or (pathlib.Path.home() / "Prizrak-Box-V3"))
CONTROLLER = os.environ.get("PB_CONTROLLER", "http://127.0.0.1:9686")
RULE = "DOMAIN-SUFFIX,deepseek.com,DIRECT"
GROUP = os.environ.get("PB_GROUP", "→ Remnawave")          # группа с узлами ВПН
OUT = APP / "pbfix-runtime.yaml"
OUT_PLAIN = APP / "pbfix-runtime-plain.yaml"               # то же без правила, для откатa


def controller_secret():
    """Ключ управления ядром лежит в базе клиента (поле вида Rule_No1SecretKey_pb"<ключ>")."""
    if os.environ.get("PB_SECRET"):
        return os.environ["PB_SECRET"]
    data = ""
    for candidate in (APP / "px-server.db", APP / "cache.db"):
        if not candidate.exists():
            continue
        try:
            data += subprocess.run(["strings", str(candidate)], capture_output=True,
                                   text=True, timeout=15).stdout
        except Exception:
            data += candidate.read_bytes().decode("utf-8", "ignore")
    m = re.search(r"SecretKey_pb[\"']?([A-Za-z0-9+/=_-]{6,})", data)
    if not m:
        raise SystemExit("не нашёл ключ управления ядром в базе клиента; задайте PB_SECRET")
    return m.group(1)


SECRET = controller_secret()


def api(path, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(CONTROLLER + path, data=data, method=method,
                                 headers={"Authorization": "Bearer " + SECRET,
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        body = r.read()
    return json.loads(body) if body else {}


def rule_present(rules):
    return any(str(r.get("payload")) == "deepseek.com" and r.get("proxy") == "DIRECT" for r in rules)


def active_profile():
    files = [f for f in glob.glob(str(APP / "profiles" / "*.yaml")) if ".bak-" not in f]
    if not files:
        raise SystemExit("не нашёл активный профиль в " + str(APP / "profiles"))
    return max(files, key=lambda f: pathlib.Path(f).stat().st_mtime)


def main():
    rules = (api("/rules").get("rules") or [])
    if "--check" in sys.argv:
        for r in rules:
            print("  -", r.get("type"), r.get("payload"), "->", r.get("proxy"))
        print("правило DeepSeek напрямую:", "на месте" if rule_present(rules) else "ОТСУТСТВУЕТ")
        return 0 if rule_present(rules) else 1

    if rule_present(rules):
        print("правило DeepSeek напрямую уже в ядре — ничего не меняю")
        return 0

    live = api("/configs")
    template = yaml.safe_load((APP / "template/Template_2.yaml").read_text(encoding="utf-8"))
    profile = yaml.safe_load(pathlib.Path(active_profile()).read_text(encoding="utf-8"))

    cfg = dict(template)                                   # база: tun, dns, sniffer, провайдеры правил
    cfg.update({"mixed-port": live.get("mixed-port", 9697), "allow-lan": live.get("allow-lan", True),
                "mode": live.get("mode", "rule"), "log-level": live.get("log-level", "info"),
                "ipv6": live.get("ipv6", False),
                "external-controller": CONTROLLER.replace("http://", ""), "secret": SECRET})
    tun = dict(cfg.get("tun") or {})
    tun.update({k: v for k, v in (live.get("tun") or {}).items() if v is not None})
    cfg["tun"] = tun
    cfg["proxies"] = profile.get("proxies") or cfg.get("proxies")
    cfg["proxy-groups"] = profile.get("proxy-groups") or cfg.get("proxy-groups")

    rest = [r for r in (profile.get("rules") or []) if not str(r).startswith("DOMAIN-SUFFIX,deepseek.com")]
    cfg["rules"] = [RULE] + rest
    OUT.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    cfg["rules"] = rest
    OUT_PLAIN.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    before = (api("/proxies").get("proxies") or {}).get(GROUP, {}).get("now")
    api("/configs?force=true", method="PUT", payload={"path": str(OUT)})
    after = (api("/proxies").get("proxies") or {}).get(GROUP, {}).get("now")
    if before and after != before:                         # вернуть прежнюю ноду
        try:
            api("/proxies/" + GROUP, method="PUT", payload={"name": before})
            after = before
        except Exception:
            pass
    rules = api("/rules").get("rules") or []
    ok = rule_present(rules)
    print("конфиг применён. Правило DeepSeek напрямую:", "на месте" if ok else "НЕ ПРИМЕНИЛОСЬ")
    print("нода:", after, "| правила:", [str(r.get("payload")) or r.get("type") for r in rules][:4])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
