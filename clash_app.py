#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clash Meta Config Manager
GUI-приложение с треем, локальным сервером и конвертером конфигов.
Написано на PySide6 + qtawesome.

Зависимости:
    pip install PySide6 requests pyyaml qtawesome
"""

import sys
import os
import re
import threading
import socket
import http.server
import argparse
import winreg
import json
import ctypes
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QFrame, QDialog,
    QMessageBox, QSystemTrayIcon, QMenu, QProgressBar,
    QScrollArea, QStackedWidget,
)
from PySide6.QtGui import (
    QIcon, QPixmap, QColor, QPainter, QFont, QAction, QTextCursor,
)
from PySide6.QtCore import Qt, QSize, QThread, Signal, QTimer, QRect

import requests
import yaml
import qtawesome as qta

# ─────────────────────────────────────────────
# Константы
# ─────────────────────────────────────────────

APP_NAME = "Clash Config Manager"
APP_VERSION = "2.0"
DEFAULT_PORT = 8080
AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent

CONFIG_FILE   = APP_DIR / "app_config.json"
OUTPUT_FILE   = APP_DIR / "clean.yaml"
SUB_CACHE_FILE = APP_DIR / "sub_cache.json"

SUPPORTED_TYPES       = {"vless", "vmess", "ss", "trojan", "hysteria2", "tuic", "wireguard"}
SUPPORTED_GROUP_TYPES = {"select", "url-test", "fallback", "load-balance"}
HIDDIFY_EXCLUDE       = "naive|shadowtls|ssh|mieru|xhttp|shadowsocks+shadowtls"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CHINESE_TO_RUSSIAN = {
    "节点选择": "Выбор",        "自动选择": "Авто",          "故障转移": "Отказоустойчивость",
    "负载均衡": "Балансировка", "全球直连": "Прямое",        "广告拦截": "Реклама",
    "漏网之鱼": "Остальное",    "香港节点": "Гонконг",       "日本节点": "Япония",
    "新加坡节点": "Сингапур",   "台湾节点": "Тайвань",       "美国节点": "США",
    "韩国节点": "Корея",        "英国节点": "Великобритания","德国节点": "Германия",
    "法国节点": "Франция",      "俄罗斯节点": "Россия",      "荷兰节点": "Нидерланды",
    "加拿大节点": "Канада",     "澳大利亚节点": "Австралия", "印度节点": "Индия",
    "土耳其节点": "Турция",     "巴西节点": "Бразилия",      "阿根廷节点": "Аргентина",
    "其他节点": "Прочие",       "低倍率节点": "Низкий множитель",
    "高倍率节点": "Высокий множитель",
    "专线节点": "Выделенная линия", "游戏节点": "Игры",
    "流媒体": "Стриминг",       "解锁": "Разблокировка",     "国际流媒体": "Стриминг",
}

LOCAL_RULES = [
    "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
    "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
    "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
    "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
    "IP-CIDR,169.254.0.0/16,DIRECT,no-resolve",
    "DOMAIN-SUFFIX,localhost,DIRECT",
    "DOMAIN-SUFFIX,local,DIRECT",
    "DOMAIN-SUFFIX,lan,DIRECT",
]

COLORS = {
    "bg":        "#0f1117",
    "bg2":       "#1a1d27",
    "bg3":       "#22263a",
    "accent":    "#4f8ef7",
    "accent2":   "#6c63ff",
    "success":   "#2ecc71",
    "warning":   "#f39c12",
    "danger":    "#e74c3c",
    "text":      "#e8eaf0",
    "text2":     "#8892a4",
    "border":    "#2d3350",
    "input_bg":  "#161925",
    "btn":       "#2a2f45",
    "btn_hover": "#363c57",
}

# ─────────────────────────────────────────────
# Хелперы для qtawesome иконок
# ─────────────────────────────────────────────

def _ico(name: str, color: str = COLORS["text"], size: int = 16) -> QIcon:
    """Создаёт QIcon через qtawesome с нужным цветом."""
    return qta.icon(name, color=color)


def _px(name: str, color: str = COLORS["text"], size: int = 16) -> QPixmap:
    """Создаёт QPixmap через qtawesome с нужным цветом и размером."""
    return qta.icon(name, color=color).pixmap(QSize(size, size))


# ─────────────────────────────────────────────
# Иконка приложения (icon.ico) — только для
# окна, трея, панели задач. qtawesome НЕ трогает.
# ─────────────────────────────────────────────

def _make_fallback_pixmap(size: int) -> QPixmap:
    """Синий квадрат с «C» — если icon.ico не найден."""
    px = QPixmap(size, size)
    px.fill(QColor(COLORS["accent"]))
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setFont(QFont("Arial", int(size * 0.55), QFont.Bold))
    p.setPen(QColor("#ffffff"))
    p.drawText(QRect(0, 0, size, size), Qt.AlignCenter, "C")
    p.end()
    return px


def load_app_icon() -> QIcon:
    """
    Загружает главный значок приложения из файла icon.png
    (используется для заголовка окна и ярлыка программы).
    """
    base = os.path.dirname(__file__)
    icon_path = os.path.join(base, "icon.png")
    if os.path.exists(icon_path):
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon = QIcon()
            icon.addPixmap(pixmap)
            return icon
    # если этого файла нет, пробуем icon.png
    icon_path = os.path.join(base, "icon.png")
    if os.path.exists(icon_path):
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon = QIcon()
            icon.addPixmap(pixmap)
            return icon
    return QIcon(_make_fallback_pixmap(256))


def load_taskbar_icon() -> QIcon:
    """
    Иконка для панели задач (Windows). Используется файл
    "icon.png" рядом со скриптом.
    """
    icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
    if os.path.exists(icon_path):
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon = QIcon()
            icon.addPixmap(pixmap)
            return icon
    return QIcon(_make_fallback_pixmap(256))


def load_tray_icon() -> QIcon:
    """
    Иконка для системного трея  загружается из файла icon.png.
    """
    icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
    
    if os.path.exists(icon_path):
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon = QIcon()
            icon.addPixmap(pixmap)
            return icon
    
    # Если иконка не найдена, используем fallback
    return QIcon(_make_fallback_pixmap(48))


# ─────────────────────────────────────────────
# Глобальное состояние
# ─────────────────────────────────────────────

_sub_header    = ""
_sub_info: dict = {}
_http_server   = None
_server_running = False

# ─────────────────────────────────────────────
# Настройки
# ─────────────────────────────────────────────

def load_settings() -> dict:
    defaults = {"url": "", "port": DEFAULT_PORT, "autostart": False}
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                defaults.update(json.load(f))
    except Exception:
        pass
    return defaults


def save_settings(settings: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ─────────────────────────────────────────────
# Автозапуск Windows
# ─────────────────────────────────────────────

def set_autostart(enable: bool) -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE)
        if enable:
            exe = f'"{sys.executable}" "{os.path.abspath(__file__)}" --minimized'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def get_autostart() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


# ─────────────────────────────────────────────
# Утилиты обработки конфига
# ─────────────────────────────────────────────

def remove_emoji(text: str) -> str:
    pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF\U00002700-\U000027BF\U0001F900-\U0001F9FF"
        "\U00002600-\U000026FF\U00002B00-\U00002BFF\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF\U0000FE00-\U0000FE0F\U0001F004\U0001F0CF]+",
        flags=re.UNICODE,
    )
    return pattern.sub("", text).strip()


def remove_chinese(text: str) -> str:
    return re.sub(r"[\u4e00-\u9fff\u3400-\u4dbf]+", "", text).strip()


def clean_name(name: str) -> str:
    return re.sub(r"\s{2,}", " ", remove_emoji(name)).strip()


def translate_group_name(name: str) -> str:
    stripped = name.strip()
    if stripped in CHINESE_TO_RUSSIAN:
        return CHINESE_TO_RUSSIAN[stripped]
    for cn, ru in CHINESE_TO_RUSSIAN.items():
        if cn in stripped:
            result = re.sub(r"\s{2,}", " ",
                remove_chinese(remove_emoji(stripped.replace(cn, ru)))).strip()
            return result if result else ru
    result = re.sub(r"\s{2,}", " ", remove_chinese(remove_emoji(stripped))).strip()
    return result if result else stripped


def parse_subscription_info(header_value: str) -> dict:
    info = {}
    if not header_value:
        return info
    for part in header_value.split(";"):
        part = part.strip()
        if "=" in part:
            key, _, val = part.partition("=")
            key = key.strip().lower()
            try:
                info[key] = int(val.strip())
            except ValueError:
                info[key] = val.strip()
    return info


def format_bytes(num_bytes: int) -> str:
    if num_bytes >= 1024 ** 3:
        return f"{num_bytes / 1024**3:.2f} GB"
    elif num_bytes >= 1024 ** 2:
        return f"{num_bytes / 1024**2:.2f} MB"
    elif num_bytes >= 1024:
        return f"{num_bytes / 1024:.2f} KB"
    return f"{num_bytes} B"


def prepare_url(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    if "/clashmeta/" in parsed.path:
        params["exclude"] = [HIDDIFY_EXCLUDE]
        return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))
    return url


def normalize_proxy(proxy: dict) -> dict:
    proxy.pop("transport", None)
    return proxy


def filter_proxies(proxies: list) -> tuple:
    kept, removed = [], {}
    for proxy in proxies:
        if not isinstance(proxy, dict):
            continue
        pt = str(proxy.get("type", "")).lower()
        if pt in SUPPORTED_TYPES:
            if "name" in proxy:
                proxy["name"] = clean_name(str(proxy["name"]))
            kept.append(normalize_proxy(proxy))
        else:
            removed[pt] = removed.get(pt, 0) + 1
    return kept, removed


def process_groups(groups: list, valid_proxy_names: set) -> list:
    if not groups:
        return []
    rename_map = {
        str(g.get("name", "")): translate_group_name(str(g.get("name", "")))
        for g in groups if isinstance(g, dict)
    }
    all_new = set(rename_map.values())
    processed = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        gt = str(group.get("type", "")).lower()
        if gt not in SUPPORTED_GROUP_TYPES:
            continue
        old_name = str(group.get("name", ""))
        new_list = []
        for item in group.get("proxies", []) or []:
            s = str(item)
            if s in valid_proxy_names:
                new_list.append(s)
            elif s in rename_map:
                new_list.append(rename_map[s])
            elif s in all_new:
                new_list.append(s)
            elif s in ("DIRECT", "REJECT"):
                new_list.append(s)
        if gt in ("fallback", "url-test", "load-balance"):
            new_list = [p for p in new_list if p not in ("DIRECT", "REJECT")]
        if any(p not in ("DIRECT", "REJECT") for p in new_list):
            g2 = dict(group)
            g2["name"] = rename_map.get(old_name, old_name)
            g2["proxies"] = new_list
            processed.append(g2)
    return processed


def find_main_group(groups: list) -> str:
    for g in groups:
        if g.get("name") == "Выбор":
            return "Выбор"
    for g in groups:
        if g.get("type") == "select":
            return g["name"]
    return groups[0]["name"] if groups else "Выбор"


def process_config(data: dict):
    result = {}
    for key in ("port", "socks-port", "mixed-port", "redir-port", "allow-lan",
                "bind-address", "mode", "log-level", "external-controller",
                "dns", "tun", "ipv6", "unified-delay", "tcp-concurrent",
                "global-client-fingerprint", "geodata-mode", "geox-url",
                "geo-auto-update", "geo-update-interval"):
        if key in data:
            result[key] = data[key]

    clean_proxies, removed = filter_proxies(data.get("proxies", []) or [])
    result["proxies"] = clean_proxies
    valid_names = {str(p["name"]) for p in clean_proxies if "name" in p}
    clean_groups = process_groups(data.get("proxy-groups", []) or [], valid_names)
    result["proxy-groups"] = clean_groups
    main_group = find_main_group(clean_groups)
    result["rules"] = list(LOCAL_RULES) + [f"MATCH,{main_group}"]
    return result, removed, len(clean_proxies), len(clean_groups), main_group


# ─────────────────────────────────────────────
# HTTP-сервер
# ─────────────────────────────────────────────

def find_free_port(preferred: int = DEFAULT_PORT) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                return port
    return preferred


def start_server(port: int):
    global _http_server, _server_running
    directory = str(APP_DIR)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

        def end_headers(self):
            if _sub_header:
                self.send_header("subscription-userinfo", _sub_header)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Disposition", "inline")
            super().end_headers()

        def log_message(self, fmt, *args):
            pass

    _http_server = http.server.HTTPServer(("localhost", port), Handler)
    _server_running = True
    _http_server.serve_forever()


def stop_server():
    global _http_server, _server_running
    if _http_server:
        _http_server.shutdown()
        _http_server = None
    _server_running = False


# ─────────────────────────────────────────────
# Поток конвертации
# ─────────────────────────────────────────────

class ConvertWorker(QThread):
    log_message    = Signal(str, str)
    finished       = Signal()
    sub_info_ready = Signal(dict, str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        global _sub_header, _sub_info
        try:
            self.log_message.emit("Начинаю обработку...", "accent")
            download_url = prepare_url(self.url)
            if download_url != self.url:
                self.log_message.emit("Hiddify: добавлен фильтр протоколов", "info")

            self.log_message.emit("Скачиваю конфиг...", "info")
            resp = requests.get(download_url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            text = resp.text
            self.log_message.emit(f"Скачано: {len(text):,} символов", "success")

            sub_hdr = resp.headers.get("subscription-userinfo", "")
            if not sub_hdr:
                for alt in ("x-subscription-userinfo", "profile-userinfo"):
                    sub_hdr = resp.headers.get(alt, "")
                    if sub_hdr:
                        break
            _sub_header = sub_hdr
            _sub_info   = parse_subscription_info(sub_hdr)

            self.log_message.emit("Парсю YAML...", "info")
            data = yaml.safe_load(text)
            if not isinstance(data, dict):
                raise ValueError("Не Clash YAML — ожидался словарь")

            self.log_message.emit("Фильтрую протоколы и группы...", "info")
            clean_config, removed, proxy_cnt, group_cnt, main_group = process_config(data)

            if removed:
                removed_str = ", ".join(f"{t}({n})" for t, n in sorted(removed.items()))
                self.log_message.emit(f"Удалены протоколы: {removed_str}", "warning")

            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            header_comment = (
                f"# Очищенный конфиг Clash Meta\n"
                f"# Источник: {self.url}\n"
                f"# Обработано: {now}\n\n"
            )
            yaml_text = yaml.dump(clean_config, allow_unicode=True, sort_keys=False,
                                  width=4096, default_flow_style=False)
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write(header_comment + yaml_text)

            self.log_message.emit(f"✓ Сохранено: {OUTPUT_FILE.name}", "success")
            self.log_message.emit(
                f"✓ Прокси: {proxy_cnt}  Группы: {group_cnt}  Главная: {main_group}", "success"
            )
            self.sub_info_ready.emit(_sub_info, _sub_header)

        except requests.exceptions.ConnectionError:
            self.log_message.emit("❌ Ошибка подключения. Проверьте URL и интернет.", "error")
        except requests.exceptions.Timeout:
            self.log_message.emit("❌ Сервер не ответил за 20 секунд.", "error")
        except requests.exceptions.HTTPError as e:
            self.log_message.emit(f"❌ HTTP ошибка: {e}", "error")
        except yaml.YAMLError as e:
            self.log_message.emit(f"❌ Невалидный YAML: {e}", "error")
        except Exception as e:
            self.log_message.emit(f"❌ Ошибка: {e}", "error")
        finally:
            self.finished.emit()


# ─────────────────────────────────────────────
# Глобальный стиль
# ─────────────────────────────────────────────

GLOBAL_STYLE = f"""
QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
}}
QMainWindow {{ background-color: {COLORS['bg']}; }}
QDialog     {{ background-color: {COLORS['bg2']}; }}
QPushButton {{
    background-color: {COLORS['btn']};
    color: {COLORS['text']};
    border: none; border-radius: 6px;
    padding: 8px 16px; font-size: 10pt;
}}
QPushButton:hover    {{ background-color: {COLORS['btn_hover']}; }}
QPushButton:disabled {{ background-color: {COLORS['btn']}; color: {COLORS['text2']}; }}
QPushButton#accent {{
    background-color: {COLORS['accent']};
    color: white; font-weight: bold;
}}
QPushButton#accent:hover    {{ background-color: #3a7be0; }}
QPushButton#accent:disabled {{ background-color: {COLORS['btn']}; color: {COLORS['text2']}; }}
QLineEdit {{
    background-color: {COLORS['input_bg']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px; padding: 8px 10px; font-size: 10pt;
    selection-background-color: {COLORS['accent']};
}}
QLineEdit:focus     {{ border: 1px solid {COLORS['accent']}; }}
QLineEdit:read-only {{ color: {COLORS['accent']}; }}
QTextEdit {{
    background-color: {COLORS['input_bg']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px; padding: 6px;
    font-family: "Consolas", monospace; font-size: 9pt;
    selection-background-color: {COLORS['accent']};
}}
QScrollBar:vertical {{
    background: {COLORS['bg3']}; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['border']}; border-radius: 4px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {COLORS['text2']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QProgressBar {{
    background-color: {COLORS['bg3']}; border: none; border-radius: 3px; height: 4px;
}}
QProgressBar::chunk {{ background-color: {COLORS['accent']}; border-radius: 3px; }}
QFrame#card {{
    background-color: {COLORS['bg2']};
    border: 1px solid {COLORS['border']}; border-radius: 8px;
}}
QMenu {{
    background-color: {COLORS['bg2']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px; padding: 4px; color: {COLORS['text']};
}}
QMenu::item {{ padding: 6px 20px; border-radius: 4px; }}
QMenu::item:selected {{ background-color: {COLORS['btn_hover']}; }}
QMenu::separator {{ height: 1px; background-color: {COLORS['border']}; margin: 4px 0; }}
"""


# ─────────────────────────────────────────────
# Диалог: информация о подписке
# ─────────────────────────────────────────────

class SubInfoDialog(QDialog):
    def __init__(self, parent, info: dict):
        super().__init__(parent)
        self.setWindowTitle("Информация о подписке")
        self.setWindowIcon(load_app_icon())   # icon.ico
        self.setFixedSize(400, 290)
        self.setModal(False)
        self._build_ui(info)

    def _build_ui(self, info: dict):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)

        # Заголовок с иконкой qta
        hdr = QHBoxLayout()
        ico = QLabel()
        ico.setPixmap(_px("fa5s.chart-bar", COLORS["accent"], 20))
        ico.setStyleSheet("background: transparent;")
        hdr.addWidget(ico)
        title = QLabel("  Подписка")
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {COLORS['text']};")
        hdr.addWidget(title)
        hdr.addStretch()
        lay.addLayout(hdr)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {COLORS['border']};")
        lay.addWidget(sep)

        if not info:
            lbl = QLabel("Нет данных.\nСначала выполните конвертацию.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {COLORS['text2']};")
            lay.addWidget(lbl, 1)
        else:
            expire = info.get("expire", 0)
            if expire:
                try:
                    dt    = datetime.fromtimestamp(expire)
                    days  = (dt - datetime.now()).days
                    color = COLORS["danger"] if days <= 7 else COLORS["success"]

                    r1 = QHBoxLayout()
                    i1 = QLabel(); i1.setPixmap(_px("fa5s.calendar-alt", COLORS["text"], 14))
                    i1.setStyleSheet("background: transparent;")
                    r1.addWidget(i1)
                    r1.addWidget(QLabel(f"  Действует до: {dt.strftime('%Y-%m-%d')}"))
                    r1.addStretch()
                    lay.addLayout(r1)

                    r2 = QHBoxLayout()
                    i2 = QLabel(); i2.setPixmap(_px("fa5s.hourglass-half", color, 14))
                    i2.setStyleSheet("background: transparent;")
                    r2.addWidget(i2)
                    days_lbl = QLabel(f"  Осталось: {days} дней")
                    days_lbl.setStyleSheet(
                        f"font-size: 11pt; font-weight: bold; color: {color};"
                    )
                    r2.addWidget(days_lbl)
                    r2.addStretch()
                    lay.addLayout(r2)
                except Exception:
                    pass

            total = info.get("total", 0)
            if total:
                used  = info.get("upload", 0) + info.get("download", 0)
                pct   = min(used / total * 100, 100)
                color = (
                    COLORS["danger"]  if pct >= 100 else
                    COLORS["warning"] if pct >= 80  else
                    COLORS["success"]
                )
                r3 = QHBoxLayout()
                i3 = QLabel(); i3.setPixmap(_px("fa5s.wifi", color, 14))
                i3.setStyleSheet("background: transparent;")
                r3.addWidget(i3)
                t_lbl = QLabel(
                    f"  Трафик: {format_bytes(used)} / {format_bytes(total)} ({pct:.1f}%)"
                )
                t_lbl.setStyleSheet(f"font-size: 9pt; color: {color};")
                r3.addWidget(t_lbl)
                r3.addStretch()
                lay.addLayout(r3)

                pb = QProgressBar()
                pb.setValue(int(pct))
                pb.setTextVisible(False)
                pb.setFixedHeight(6)
                pb.setStyleSheet(
                    f"QProgressBar {{ background-color: {COLORS['bg3']}; border: none; border-radius: 3px; }}"
                    f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}"
                )
                lay.addWidget(pb)

        lay.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("accent")
        ok_btn.clicked.connect(self.accept)
        lay.addWidget(ok_btn)


# ─────────────────────────────────────────────
# Главное окно
# ─────────────────────────────────────────────

class ClashApp(QMainWindow):
    def __init__(self, start_minimized: bool = False):
        super().__init__()

        self.settings = load_settings()
        saved_port = self.settings.get("port", DEFAULT_PORT)
        self.port  = find_free_port(saved_port)
        if self.port != saved_port:
            self.settings["port"] = self.port
            save_settings(self.settings)

        self.server_url    = f"http://localhost:{self.port}/clean.yaml"
        self.is_converting = False
        self._worker: ConvertWorker | None  = None
        self._sub_dialog: SubInfoDialog | None = None
        self._autostart_state = get_autostart()

        # Ссылки на виджеты настроек
        self._toggle_btn: QPushButton | None       = None
        self._copy_btn_settings: QPushButton | None = None
        self._url_display: QLineEdit | None         = None

        self._setup_window()
        self._build_ui()
        self._setup_tray()
        self._start_server_thread()

        if start_minimized:
            QTimer.singleShot(100, self._hide_to_tray)
        if self.settings.get("url"):
            QTimer.singleShot(500, self._auto_convert_on_start)

    # ── Окно ──────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle("Clash Config Manager")
        self.resize(700, 660)
        self.setMinimumSize(580, 520)
        # Иконка из icon.ico — устанавливаем все размеры
        self.setWindowIcon(load_app_icon())
        geo = QApplication.primaryScreen().availableGeometry()
        self.move((geo.width() - 700) // 2, (geo.height() - 660) // 2)

    def closeEvent(self, event):
        event.ignore()
        self._hide_to_tray()

    # ── Построение UI ─────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_header())
        root.addWidget(self._hline())

        self._stacked = QStackedWidget()
        self._stacked.addWidget(self._make_main_page())      # 0
        self._stacked.addWidget(self._make_settings_page())  # 1
        self._stacked.currentChanged.connect(self._on_stack_changed)
        root.addWidget(self._stacked, 1)

        root.addWidget(self._make_bottom_bar())

    # ── Заголовок ────────────────────────────

    def _make_header(self) -> QWidget:
        hdr = QWidget()
        hdr.setStyleSheet(f"background-color: {COLORS['bg2']};")
        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(20, 14, 20, 14)

        # Иконка из icon.ico (крупная — 48px)
        ico_lbl = QLabel()
        ico_lbl.setPixmap(load_app_icon().pixmap(QSize(48, 48)))
        ico_lbl.setFixedSize(52, 52)
        ico_lbl.setStyleSheet("background: transparent;")
        lay.addWidget(ico_lbl)
        lay.addSpacing(10)

        # Название + версия
        col = QVBoxLayout()
        col.setSpacing(0)
        t = QLabel("Clash Config Manager")
        t.setStyleSheet(
            f"font-size: 15pt; font-weight: bold; color: {COLORS['text']}; background: transparent;"
        )
        v = QLabel(f"v{APP_VERSION}")
        v.setStyleSheet(f"font-size: 8pt; color: {COLORS['text2']}; background: transparent;")
        col.addWidget(t)
        col.addWidget(v)
        lay.addLayout(col)
        lay.addStretch()

        # Статус сервера — иконка qta + текст
        self._server_status_ico = QLabel()
        self._server_status_ico.setPixmap(_px("fa5s.circle", COLORS["success"], 10))
        self._server_status_ico.setStyleSheet("background: transparent;")

        self._server_label = QLabel(f"localhost:{self.port}")
        self._server_label.setStyleSheet(
            f"font-size: 9pt; color: {COLORS['success']}; background: transparent;"
        )
        self._server_label.setCursor(Qt.PointingHandCursor)
        self._server_label.mousePressEvent = lambda _e: self._copy_url()

        srv_box = QWidget()
        srv_box.setStyleSheet("background: transparent;")
        srv_lay = QHBoxLayout(srv_box)
        srv_lay.setContentsMargins(0, 0, 0, 0)
        srv_lay.setSpacing(5)
        srv_lay.addWidget(self._server_status_ico)
        srv_lay.addWidget(self._server_label)
        lay.addWidget(srv_box)
        lay.addSpacing(10)

        # Кнопка Настройки / Назад
        self._header_action_btn = QPushButton()
        self._header_action_btn.setIcon(_ico("fa5s.cog", COLORS["text"]))
        self._header_action_btn.setIconSize(QSize(15, 15))
        self._header_action_btn.setText("  Настройки")
        self._header_action_btn.setFixedWidth(120)
        self._header_action_btn.setMinimumHeight(34)
        self._header_action_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['btn']}; color: {COLORS['text']}; "
            f"border: none; border-radius: 6px; font-size: 9pt; padding: 4px 10px; text-align: left; }}"
            f"QPushButton:hover {{ background-color: {COLORS['btn_hover']}; }}"
        )
        self._header_action_btn.setCursor(Qt.PointingHandCursor)
        self._header_action_btn.clicked.connect(self._open_settings)
        lay.addWidget(self._header_action_btn)
        return hdr

    # ── Главная страница ──────────────────────

    def _make_main_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        w = QWidget()
        w.setStyleSheet(f"background-color: {COLORS['bg']};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        # ── URL блок ──
        url_card = QFrame()
        url_card.setObjectName("card")
        ul = QVBoxLayout(url_card)
        ul.setContentsMargins(16, 14, 16, 14)
        ul.setSpacing(8)

        url_hdr = QHBoxLayout()
        url_ico = QLabel(); url_ico.setPixmap(_px("fa5s.link", COLORS["text2"], 13))
        url_ico.setStyleSheet("background: transparent;")
        url_hdr.addWidget(url_ico)
        url_hdr.addWidget(self._small_label("  URL подписки"))
        url_hdr.addStretch()
        ul.addLayout(url_hdr)

        row = QHBoxLayout()
        self._url_edit = QLineEdit(self.settings.get("url", ""))
        self._url_edit.setPlaceholderText("https://...")
        row.addWidget(self._url_edit)

        paste_btn = QPushButton()
        paste_btn.setIcon(_ico("fa5s.clipboard", COLORS["text"]))
        paste_btn.setIconSize(QSize(15, 15))
        paste_btn.setFixedWidth(42)
        paste_btn.setToolTip("Вставить из буфера")
        paste_btn.clicked.connect(self._paste_url)
        row.addWidget(paste_btn)
        ul.addLayout(row)
        lay.addWidget(url_card)

        # ── Кнопка конвертации ──
        self._convert_btn = QPushButton()
        self._convert_btn.setIcon(_ico("fa5s.sync-alt", "white"))
        self._convert_btn.setIconSize(QSize(16, 16))
        self._convert_btn.setText("  Конвертировать")
        self._convert_btn.setObjectName("accent")
        self._convert_btn.setMinimumHeight(46)
        self._convert_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['accent']}; color: white; "
            f"border: none; border-radius: 8px; font-size: 11pt; font-weight: bold; padding: 10px 20px; text-align: center; }}"
            f"QPushButton:hover {{ background-color: #3a7be0; }}"
            f"QPushButton:disabled {{ background-color: {COLORS['btn']}; color: {COLORS['text2']}; }}"
        )
        self._convert_btn.clicked.connect(self._start_convert)
        lay.addWidget(self._convert_btn)

        # ── Прогресс ──
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.hide()
        lay.addWidget(self._progress)

        # ── Блок подписки ──
        sub_card = QFrame()
        sub_card.setObjectName("card")
        sl = QVBoxLayout(sub_card)
        sl.setContentsMargins(16, 12, 16, 12)
        sl.setSpacing(6)

        sub_hdr = QHBoxLayout()
        sub_ico = QLabel(); sub_ico.setPixmap(_px("fa5s.id-card", COLORS["text2"], 13))
        sub_ico.setStyleSheet("background: transparent;")
        sub_hdr.addWidget(sub_ico)
        sub_hdr.addWidget(self._small_label("  Информация о подписке"))
        sub_hdr.addStretch()
        sl.addLayout(sub_hdr)

        self._sub_info_label = QLabel(
            "Нажмите «Конвертировать» чтобы получить данные о подписке"
        )
        self._sub_info_label.setWordWrap(True)
        self._sub_info_label.setStyleSheet(
            f"font-size: 9pt; color: {COLORS['text2']}; background: transparent;"
        )
        sl.addWidget(self._sub_info_label)
        lay.addWidget(sub_card)

        # ── Лог ──
        log_w = QWidget()
        log_w.setStyleSheet(f"background-color: {COLORS['bg']};")
        ll = QVBoxLayout(log_w)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(4)

        log_hdr = QHBoxLayout()
        log_ico = QLabel(); log_ico.setPixmap(_px("fa5s.terminal", COLORS["text2"], 13))
        log_ico.setStyleSheet("background: transparent;")
        log_hdr.addWidget(log_ico)
        log_hdr.addWidget(self._small_label("  Лог"))
        log_hdr.addStretch()

        clear_btn = QPushButton()
        clear_btn.setIcon(_ico("fa5s.trash-alt", COLORS["text2"]))
        clear_btn.setIconSize(QSize(13, 13))
        clear_btn.setText("  очистить")
        clear_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {COLORS['text2']}; "
            f"border: none; font-size: 8pt; }}"
            f"QPushButton:hover {{ color: {COLORS['text']}; }}"
        )
        clear_btn.clicked.connect(self._clear_log)
        log_hdr.addWidget(clear_btn)
        ll.addLayout(log_hdr)

        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMinimumHeight(170)
        ll.addWidget(self._log_edit)
        lay.addWidget(log_w)

        scroll.setWidget(w)
        return scroll

    # ── Страница настроек ─────────────────────

    def _make_settings_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        w = QWidget()
        w.setStyleSheet(f"background-color: {COLORS['bg']};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        # Заголовок
        t_row = QHBoxLayout()
        t_ico = QLabel(); t_ico.setPixmap(_px("fa5s.cog", COLORS["text"], 18))
        t_ico.setStyleSheet("background: transparent;")
        t_row.addWidget(t_ico)
        title = QLabel("  Настройки")
        title.setStyleSheet(
            f"font-size: 13pt; font-weight: bold; color: {COLORS['text']}; background: transparent;"
        )
        t_row.addWidget(title)
        t_row.addStretch()
        lay.addLayout(t_row)
        lay.addWidget(self._hline())

        # ── ЗАПУСК ──
        lay.addWidget(self._section_label("ЗАПУСК"))
        lay.addWidget(self._hline())

        autostart_card = QFrame()
        autostart_card.setObjectName("card")
        ac = QHBoxLayout(autostart_card)
        ac.setContentsMargins(14, 14, 14, 14)

        lcol = QVBoxLayout()
        lcol.setSpacing(3)

        lbl_row = QHBoxLayout()
        a_ico = QLabel(); a_ico.setPixmap(_px("fa5s.rocket", COLORS["text"], 14))
        a_ico.setStyleSheet("background: transparent;")
        lbl_row.addWidget(a_ico)
        m_lbl = QLabel("  Автозапуск с Windows")
        m_lbl.setStyleSheet(f"font-weight: bold; color: {COLORS['text']}; background: transparent;")
        lbl_row.addWidget(m_lbl)
        lbl_row.addStretch()
        lcol.addLayout(lbl_row)

        s_lbl = QLabel("Запускать свёрнутым в трей при входе в систему")
        s_lbl.setStyleSheet(f"font-size: 8pt; color: {COLORS['text2']}; background: transparent;")
        lcol.addWidget(s_lbl)

        rcol = QVBoxLayout()
        rcol.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._toggle_btn = QPushButton(
            "Включён ✓" if self._autostart_state else "Отключён"
        )
        self._toggle_btn.setFixedWidth(110)
        self._toggle_btn.setStyleSheet(self._toggle_style(self._autostart_state))
        self._toggle_btn.clicked.connect(self._toggle_autostart)
        rcol.addWidget(self._toggle_btn)

        ac.addLayout(lcol, 1)
        ac.addLayout(rcol)
        lay.addWidget(autostart_card)
        lay.addSpacing(8)

        # ── СЕРВЕР ──
        lay.addWidget(self._section_label("СЕРВЕР"))
        lay.addWidget(self._hline())

        srv_card = QFrame()
        srv_card.setObjectName("card")
        sc = QVBoxLayout(srv_card)
        sc.setContentsMargins(14, 12, 14, 12)

        srv_title_row = QHBoxLayout()
        srv_t_ico = QLabel(); srv_t_ico.setPixmap(_px("fa5s.server", COLORS["text"], 14))
        srv_t_ico.setStyleSheet("background: transparent;")
        srv_title_row.addWidget(srv_t_ico)
        srv_title_row.addWidget(QLabel("  URL для Clash Verge / Clash Party"))
        srv_title_row.addStretch()
        sc.addLayout(srv_title_row)

        url_row = QHBoxLayout()
        self._url_display = QLineEdit(self.server_url)
        self._url_display.setReadOnly(True)
        self._url_display.setStyleSheet(
            f"background-color: {COLORS['input_bg']}; color: {COLORS['accent']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 6px; "
            f"padding: 6px 8px; font-family: Consolas;"
        )
        url_row.addWidget(self._url_display)

        self._copy_btn_settings = QPushButton()
        self._copy_btn_settings.setIcon(_ico("fa5s.copy", COLORS["text"]))
        self._copy_btn_settings.setIconSize(QSize(14, 14))
        self._copy_btn_settings.setText("  Копировать")
        self._copy_btn_settings.setFixedWidth(130)
        self._copy_btn_settings.clicked.connect(self._copy_server_url_settings)
        url_row.addWidget(self._copy_btn_settings)
        sc.addLayout(url_row)
        lay.addWidget(srv_card)
        lay.addSpacing(8)

        # ── О ПРОГРАММЕ ──
        lay.addWidget(self._section_label("О ПРОГРАММЕ"))
        lay.addWidget(self._hline())

        about_row = QHBoxLayout()
        ab_ico = QLabel(); ab_ico.setPixmap(_px("fa5s.info-circle", COLORS["text2"], 14))
        ab_ico.setStyleSheet("background: transparent;")
        about_row.addWidget(ab_ico)
        about_lbl = QLabel(f"  {APP_NAME}  v{APP_VERSION}")
        about_lbl.setStyleSheet(f"font-size: 9pt; color: {COLORS['text2']}; background: transparent;")
        about_row.addWidget(about_lbl)
        about_row.addStretch()
        lay.addLayout(about_row)

        lay.addStretch()
        scroll.setWidget(w)
        return scroll

    # ── Нижняя панель ─────────────────────────

    def _make_bottom_bar(self) -> QWidget:
        wrapper = QWidget()
        wrapper.setStyleSheet(f"background-color: {COLORS['bg2']};")
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)
        wl.addWidget(self._hline())

        bar = QWidget()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(20, 10, 20, 10)
        bl.addStretch()

        # tray_btn = QPushButton()
        # tray_btn.setIcon(_ico("fa5s.arrow-down", COLORS["text"]))
        # tray_btn.setIconSize(QSize(14, 14))
        # tray_btn.setText("  В трей")
        # tray_btn.clicked.connect(self._hide_to_tray)
        # bl.addWidget(tray_btn)

        copy_btn = QPushButton()
        copy_btn.setIcon(_ico("fa5s.copy", "white"))
        copy_btn.setIconSize(QSize(15, 15))
        copy_btn.setText("  Копировать ссылку")
        copy_btn.setObjectName("accent")
        copy_btn.setMinimumHeight(38)
        copy_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['accent']}; color: white; "
            f"border: none; border-radius: 6px; font-size: 10pt; font-weight: bold; padding: 6px 16px; }}"
            f"QPushButton:hover {{ background-color: #3a7be0; }}"
        )
        copy_btn.clicked.connect(self._copy_url)
        bl.addWidget(copy_btn)

        wl.addWidget(bar)
        return wrapper

    # ── Мелкие хелперы ────────────────────────

    @staticmethod
    def _small_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 9pt; font-weight: bold; color: {COLORS['text2']}; background: transparent;"
        )
        return lbl

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 9pt; font-weight: bold; color: {COLORS['text2']}; "
            f"background: transparent; letter-spacing: 1px;"
        )
        return lbl

    @staticmethod
    def _hline() -> QFrame:
        f = QFrame()
        f.setFixedHeight(1)
        f.setStyleSheet(f"background-color: {COLORS['border']};")
        return f

    # ── Стек ──────────────────────────────────

    def _open_settings(self):
        self._stacked.setCurrentIndex(1)

    def _back_to_main(self):
        self._stacked.setCurrentIndex(0)

    def _on_stack_changed(self, index: int):
        try:
            self._header_action_btn.clicked.disconnect()
        except Exception:
            pass
        if index == 0:
            self._header_action_btn.setIcon(_ico("fa5s.cog", COLORS["text"]))
            self._header_action_btn.setText("  Настройки")
            self._header_action_btn.setFixedWidth(120)
            self._header_action_btn.clicked.connect(self._open_settings)
            self.setWindowTitle("Clash Config Manager")
        else:
            self._header_action_btn.setIcon(_ico("fa5s.arrow-left", COLORS["text"]))
            self._header_action_btn.setText("  Назад")
            self._header_action_btn.setFixedWidth(95)
            self._header_action_btn.clicked.connect(self._back_to_main)
            self.setWindowTitle("Clash Config Manager — Настройки")

    # ── Трей ──────────────────────────────────

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(self)
        # Иконка трея — из icon.ico (НЕ qtawesome), максимально крупная
        self._tray.setIcon(load_tray_icon())
        self._tray.setToolTip(APP_NAME)

        menu = QMenu()
        items = [
            ("fa5s.window-maximize", "Открыть",    self._show_window),
            ("fa5s.chart-bar",       "Подписка",   self._show_sub_popup),
            ("fa5s.cog",             "Настройки",  self._open_settings),
        ]
        for icon_name, label, slot in items:
            act = QAction(_ico(icon_name, COLORS["text"]), label, self)
            act.triggered.connect(slot)
            menu.addAction(act)

        menu.addSeparator()
        quit_act = QAction(_ico("fa5s.sign-out-alt", COLORS["danger"]), "Выход", self)
        quit_act.triggered.connect(self._quit_app)
        menu.addAction(quit_act)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        # любые клики просто показывают главное окно
        if reason in (
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
            # QSystemTrayIcon.ActivationReason.Context,
        ):
            self._show_window()

    # ── Управление окном ──────────────────────

    def _hide_to_tray(self):
        self.hide()
        self._log("Свёрнуто в трей. Двойной клик — открыть.", "info")

    def _show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_app(self):
        stop_server()
        self._tray.hide()
        QApplication.quit()

    # ── UI-методы ────────────────────────────

    def _log(self, msg: str, level: str = "info"):
        COLOR_MAP = {
            "info":    COLORS["text2"],
            "success": COLORS["success"],
            "warning": COLORS["warning"],
            "error":   COLORS["danger"],
            "accent":  COLORS["accent"],
        }
        color  = COLOR_MAP.get(level, COLORS["text2"])
        ts     = datetime.now().strftime("%H:%M:%S")
        cursor = self._log_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = cursor.charFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(f"[{ts}] {msg}\n")
        self._log_edit.setTextCursor(cursor)
        self._log_edit.ensureCursorVisible()

    def _clear_log(self):
        self._log_edit.clear()

    def _paste_url(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self._url_edit.setText(text)

    def _copy_url(self):
        QApplication.clipboard().setText(self.server_url)
        self._log(f"Ссылка скопирована: {self.server_url}", "success")
        # Временно меняем иконку статуса на галочку
        self._server_status_ico.setPixmap(_px("fa5s.check-circle", COLORS["success"], 10))
        self._server_label.setText("Скопировано!")
        QTimer.singleShot(2000, lambda: (
            self._server_status_ico.setPixmap(_px("fa5s.circle", COLORS["success"], 10)),
            self._server_label.setText(f"localhost:{self.port}"),
        ))

    def _toggle_style(self, state: bool) -> str:
        if state:
            return (
                f"QPushButton {{ background-color: {COLORS['accent']}; color: white; "
                f"border: none; border-radius: 6px; padding: 6px 14px; font-weight: bold; }}"
                f"QPushButton:hover {{ background-color: #3a7be0; }}"
            )
        return (
            f"QPushButton {{ background-color: {COLORS['btn']}; color: {COLORS['text2']}; "
            f"border: none; border-radius: 6px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background-color: {COLORS['btn_hover']}; }}"
        )

    def _toggle_autostart(self):
        new_state = not self._autostart_state
        if set_autostart(new_state):
            self._autostart_state = new_state
            if self._toggle_btn:
                self._toggle_btn.setText("Включён ✓" if new_state else "Отключён")
                self._toggle_btn.setStyleSheet(self._toggle_style(new_state))
            self._log(f"Автозапуск {'включён' if new_state else 'отключён'}", "success")
        else:
            self._log("Не удалось изменить автозапуск", "warning")

    def _copy_server_url_settings(self):
        QApplication.clipboard().setText(self.server_url)
        if self._copy_btn_settings:
            self._copy_btn_settings.setIcon(_ico("fa5s.check", COLORS["success"]))
            self._copy_btn_settings.setText("  Скопировано")
            QTimer.singleShot(2000, lambda: (
                self._copy_btn_settings.setIcon(_ico("fa5s.copy", COLORS["text"])),
                self._copy_btn_settings.setText("  Копировать"),
            ))

    # ── Диалоги ───────────────────────────────

    def _show_sub_popup(self):
        if self._sub_dialog and self._sub_dialog.isVisible():
            self._sub_dialog.raise_()
            self._sub_dialog.activateWindow()
            return
        self._sub_dialog = SubInfoDialog(self, _sub_info)
        self._sub_dialog.show()

    # ── Конвертация ───────────────────────────

    def _auto_convert_on_start(self):
        url = self.settings.get("url", "").strip()
        if not url:
            return
        self._url_edit.setText(url)
        if OUTPUT_FILE.exists():
            self._log(f"Конфиг найден: {OUTPUT_FILE.name}", "success")
            self._log(f"Сервер отдаёт: {self.server_url}", "accent")
            self._load_existing_config_info()
            self._log("Обновляю конфиг в фоне...", "info")
        else:
            self._log("Первый запуск — конвертирую конфиг...", "info")
        self._start_convert(silent=True)

    def _load_existing_config_info(self):
        try:
            if SUB_CACHE_FILE.exists():
                with open(SUB_CACHE_FILE, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                global _sub_header, _sub_info
                _sub_header = cached.get("header", "")
                _sub_info   = cached.get("info", {})
                if _sub_info:
                    self._update_sub_info_ui()
                    self._log("Данные подписки загружены из кеша", "info")
        except Exception:
            pass

    def _save_sub_cache(self):
        try:
            with open(SUB_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"header": _sub_header, "info": _sub_info}, f, ensure_ascii=False)
        except Exception:
            pass

    def _start_convert(self, silent: bool = False):
        if self.is_converting:
            return
        url = self._url_edit.text().strip()
        if not url:
            if not silent:
                QMessageBox.warning(self, "Нет URL", "Введите ссылку на подписку")
            return
        if not url.startswith("https://"):
            if not silent:
                QMessageBox.critical(self, "Ошибка", "URL должен начинаться с https://")
            return

        self.settings["url"] = url
        save_settings(self.settings)

        self.is_converting = True
        self._convert_btn.setIcon(_ico("fa5s.spinner", "white"))
        self._convert_btn.setText("  Обработка...")
        self._convert_btn.setEnabled(False)
        self._progress.show()

        self._worker = ConvertWorker(url)
        self._worker.log_message.connect(self._log)
        self._worker.sub_info_ready.connect(self._on_sub_info_ready)
        self._worker.finished.connect(self._convert_done)
        self._worker.start()

    def _on_sub_info_ready(self, info: dict, header: str):
        global _sub_header, _sub_info
        _sub_header = header
        _sub_info   = info
        self._save_sub_cache()
        self._update_sub_info_ui()
        self._log(f"✓ Ссылка для Clash Verge: {self.server_url}", "accent")

    def _convert_done(self):
        self.is_converting = False
        self._progress.hide()
        self._convert_btn.setIcon(_ico("fa5s.sync-alt", "white"))
        self._convert_btn.setText("  Конвертировать")
        self._convert_btn.setEnabled(True)

    def _update_sub_info_ui(self):
        info = _sub_info
        if not info:
            self._sub_info_label.setText("Сервер не вернул данные о подписке")
            self._sub_info_label.setStyleSheet(
                f"font-size: 9pt; color: {COLORS['text2']}; background: transparent;"
            )
            return

        upload   = info.get("upload", 0)
        download = info.get("download", 0)
        total    = info.get("total", 0)
        expire   = info.get("expire", 0)
        parts    = []
        color    = COLORS["success"]

        if total:
            used  = upload + download
            pct   = min(used / total * 100, 100)
            color = (
                COLORS["danger"]  if pct >= 100 else
                COLORS["warning"] if pct >= 80  else
                COLORS["success"]
            )
            parts.append(f"Трафик: {format_bytes(used)} / {format_bytes(total)} ({pct:.1f}%)")

        if expire:
            try:
                dt   = datetime.fromtimestamp(expire)
                days = (dt - datetime.now()).days
                dstr = dt.strftime("%Y-%m-%d")
                if days < 0:
                    dday, color = f"истекла {abs(days)} дн. назад", COLORS["danger"]
                elif days == 0:
                    dday, color = "истекает сегодня!", COLORS["danger"]
                elif days <= 7:
                    dday, color = f"осталось {days} дн.", COLORS["warning"]
                else:
                    dday, color = f"осталось {days} дн.", COLORS["success"]
                parts.append(f"Подписка: до {dstr} — {dday}")
            except Exception:
                pass

        if parts:
            self._sub_info_label.setText("   •   ".join(parts))
            self._sub_info_label.setStyleSheet(
                f"font-size: 9pt; color: {color}; background: transparent;"
            )
        self._update_tray_tooltip()

    def _update_tray_tooltip(self):
        info = _sub_info
        if not info:
            self._tray.setToolTip(APP_NAME)
            return
        parts = [APP_NAME]
        if info.get("expire"):
            try:
                dt   = datetime.fromtimestamp(info["expire"])
                days = (dt - datetime.now()).days
                parts.append(f"Подписка: {dt.strftime('%Y-%m-%d')} (ещё {days} дн.)")
            except Exception:
                pass
        if info.get("total"):
            used = info.get("upload", 0) + info.get("download", 0)
            parts.append(f"Трафик: {format_bytes(used)} / {format_bytes(info['total'])}")
        self._tray.setToolTip("\n".join(parts))

    # ── HTTP-сервер ───────────────────────────

    def _start_server_thread(self):
        threading.Thread(target=start_server, args=(self.port,), daemon=True).start()
        self._log(f"Сервер запущен: {self.server_url}", "success")
        if OUTPUT_FILE.exists():
            self._log(
                f"Конфиг готов: clean.yaml ({OUTPUT_FILE.stat().st_size // 1024} KB)", "success"
            )
        else:
            self._log("Конфиг не найден — нажмите Конвертировать", "warning")
        self._log("Вставьте эту ссылку в Clash Verge/Party → Profiles → Remote", "accent")


# ─────────────────────────────────────────────
# Точка входа
# ─────────────────────────────────────────────

def main():
    # ──────────────────────────────────────────────────────────────
    # Активация High DPI для четких иконок на 4K мониторах
    # ──────────────────────────────────────────────────────────────
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except (AttributeError, OSError):
        pass  # Старые версии Windows могут не поддерживать это
    
    # Устанавливаем High DPI pixmaps для PySide6
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--minimized", action="store_true")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(GLOBAL_STYLE)
    
    # ──────────────────────────────────────────────────────────────
    # Правильный ярлык на панели задач (не заменяется на Python лого)
    # ──────────────────────────────────────────────────────────────
    try:
        app_id = f"com.clashmanager.app.{APP_VERSION}"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (AttributeError, OSError):
        pass  # Старые версии Windows могут не поддерживать это

    # Устанавливаем иконку панели задач отдельно (обычно берется из taskbar-загрузчика)
    app.setWindowIcon(load_taskbar_icon())
    # Для отдельных окон (диалоги, главное) используется load_app_icon()

    window = ClashApp(start_minimized=args.minimized)
    if not args.minimized:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()