"""ClawTap MCP Server — BLE-to-USB HID keyboard bridge."""

import asyncio
import logging
import threading
from concurrent.futures import Future

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clawtap")

# Nordic UART Service
NUS_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
DEVICE_NAME = "ClawTap"  # Also accepts "GhostType" during transition
BLE_MTU = 20

SPECIAL_KEYS = {
    "enter": 0xB0, "return": 0xB0,
    "escape": 0xB1, "esc": 0xB1,
    "backspace": 0xB2, "bs": 0xB2,
    "tab": 0xB3,
    "space": 0x20,
    "insert": 0xD1,
    "delete": 0xD4, "del": 0xD4,
    "home": 0xD2,
    "end": 0xD5,
    "pageup": 0xD3, "pgup": 0xD3,
    "pagedown": 0xD6, "pgdn": 0xD6,
    "up": 0xD8,
    "down": 0xD9,
    "left": 0xDA,
    "right": 0xD7,
    "f1": 0xC2, "f2": 0xC3, "f3": 0xC4, "f4": 0xC5,
    "f5": 0xC6, "f6": 0xC7, "f7": 0xC8, "f8": 0xC9,
    "f9": 0xCA, "f10": 0xCB, "f11": 0xCC, "f12": 0xCD,
}

MODIFIER_KEYS = {
    "ctrl": 0x80, "lctrl": 0x80, "rctrl": 0x84,
    "shift": 0x81, "lshift": 0x81, "rshift": 0x85,
    "alt": 0x82, "lalt": 0x82, "ralt": 0x86,
    "gui": 0x83, "win": 0x83, "lgui": 0x83, "rgui": 0x87,
    "cmd": 0x83, "super": 0x83, "meta": 0x83,
}

ALL_KEYS = {**SPECIAL_KEYS, **MODIFIER_KEYS}

# Russian ЙЦУКЕН → US QWERTY scancode mapping (target computer must have RU layout active)
CYRILLIC_TO_SCANCODE = {
    "й": "q", "ц": "w", "у": "e", "к": "r", "е": "t", "н": "y", "г": "u",
    "ш": "i", "щ": "o", "з": "p", "х": "[", "ъ": "]", "ф": "a", "ы": "s",
    "в": "d", "а": "f", "п": "g", "р": "h", "о": "j", "л": "k", "д": "l",
    "ж": ";", "э": "'", "я": "z", "ч": "x", "с": "c", "м": "v", "и": "b",
    "т": "n", "ь": "m", "б": ",", "ю": ".", "ё": "`",
    "Й": "Q", "Ц": "W", "У": "E", "К": "R", "Е": "T", "Н": "Y", "Г": "U",
    "Ш": "I", "Щ": "O", "З": "P", "Х": "{", "Ъ": "}", "Ф": "A", "Ы": "S",
    "В": "D", "А": "F", "П": "G", "Р": "H", "О": "J", "Л": "K", "Д": "L",
    "Ж": ":", "Э": "\"", "Я": "Z", "Ч": "X", "С": "C", "М": "V", "И": "B",
    "Т": "N", "Ь": "M", "Б": "<", "Ю": ">", "Ё": "~",
}


def text_to_scancodes(text: str) -> bytes:
    """Convert text (ASCII + Cyrillic) to scancode bytes."""
    result = []
    for ch in text:
        if ch in CYRILLIC_TO_SCANCODE:
            result.append(ord(CYRILLIC_TO_SCANCODE[ch]))
        elif ord(ch) < 128:
            result.append(ord(ch))
        # skip unsupported chars
    return bytes(result)


class BLEThread:
    """Runs bleak in a dedicated asyncio event loop on a separate thread."""

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._client = None
        self._address: str | None = None
        self._lock = threading.Lock()

    def start(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_coro(self, coro, timeout=30):
        if not self._loop:
            self.start()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def discover(self) -> str | None:
        from bleak import BleakScanner

        async def _discover():
            logger.info("Scanning for ClawTap...")
            devices = await BleakScanner.discover(timeout=10.0)
            for d in devices:
                if d.name and (d.name.lower() in ("clawtap", "ghosttype")):
                    logger.info(f"Found: {d.name} @ {d.address}")
                    self._address = d.address
                    return d.address
            return None

        return self._run_coro(_discover())

    def connect(self) -> bool:
        from bleak import BleakClient

        if self._client and self._client.is_connected:
            return True

        if not self._address:
            if not self.discover():
                return False

        async def _connect():
            self._client = BleakClient(self._address, timeout=10.0)
            await self._client.connect()
            # Wait for service discovery
            await asyncio.sleep(1)
            logger.info(f"Connected to {self._address}")

        try:
            self._run_coro(_connect())
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._client = None
            return False

    def disconnect(self):
        if self._client:
            async def _disconnect():
                if self._client.is_connected:
                    await self._client.disconnect()
            try:
                self._run_coro(_disconnect())
            except Exception:
                pass
            self._client = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    def send(self, data: bytes) -> bool:
        with self._lock:
            if not self.connect():
                return False

            async def _send():
                for i in range(0, len(data), BLE_MTU):
                    chunk = data[i:i + BLE_MTU]
                    await self._client.write_gatt_char(NUS_RX_UUID, chunk)
                    if i + BLE_MTU < len(data):
                        await asyncio.sleep(0.05)

            try:
                self._run_coro(_send())
                return True
            except Exception as e:
                logger.error(f"Send failed: {e}")
                self._client = None
                # Retry once
                if self.connect():
                    try:
                        self._run_coro(_send())
                        return True
                    except Exception:
                        self._client = None
                return False


ble = BLEThread()
ble.start()

mcp = FastMCP("clawtap")


@mcp.tool()
async def type_text(text: str) -> str:
    """Type text as HID keystrokes. Supports ASCII + Cyrillic.
    Use \\n for Enter, \\t for Tab.
    Cyrillic requires RU keyboard layout active on target computer.
    Example: type_text("hello\\nworld"), type_text("привет мир")
    """
    data = text_to_scancodes(text)
    if not data:
        return "Error: no supported characters in text"

    has_cyrillic = any(ch in CYRILLIC_TO_SCANCODE for ch in text)
    ok = ble.send(data)
    if ok:
        msg = f"Typed {len(data)} characters"
        if has_cyrillic:
            msg += " (Cyrillic — ensure RU layout is active on target)"
        return msg
    return "Error: failed to send — check BLE connection"


@mcp.tool()
async def press_key(key: str, count: int = 1) -> str:
    """Press a special key. count: 1-50.
    Keys: enter escape backspace tab delete insert home end
          pageup pagedown up down left right f1-f12 space
    """
    key_lower = key.lower().strip()
    if key_lower not in SPECIAL_KEYS:
        available = ", ".join(sorted(SPECIAL_KEYS.keys()))
        return f"Unknown key '{key}'. Available: {available}"

    count = max(1, min(count, 50))
    code = SPECIAL_KEYS[key_lower]
    data = bytes([code] * count)

    ok = ble.send(data)
    if ok:
        return f"Pressed {key} x{count}"
    return "Error: failed to send — check BLE connection"


@mcp.tool()
async def combo_keys(keys: list[str]) -> str:
    """Press up to 5 keys simultaneously.
    Modifiers: ctrl shift alt win  |  Plus: any special key or ASCII char.
    Ex: ["ctrl","c"] ["ctrl","shift","s"] ["alt","tab"] ["win","r"]
    """
    if len(keys) < 1 or len(keys) > 5:
        return "Error: combo requires 1-5 keys"

    key_bytes = []
    for k in keys:
        k_lower = k.lower().strip()
        if k_lower in ALL_KEYS:
            key_bytes.append(ALL_KEYS[k_lower])
        elif len(k) == 1 and 0x20 <= ord(k) <= 0x7E:
            key_bytes.append(ord(k))
        else:
            return f"Unknown key '{k}'."

    data = bytes([0x01, len(key_bytes)] + key_bytes)

    ok = ble.send(data)
    if ok:
        return f"Combo: {' + '.join(keys)}"
    return "Error: failed to send — check BLE connection"


@mcp.tool()
async def health_check() -> str:
    """Check BLE connection state and device availability."""
    info = {"connected": ble.is_connected, "address": ble._address}

    if not ble.is_connected:
        addr = ble.discover()
        if addr:
            info["device_found"] = True
            ok = ble.connect()
            info["reconnected"] = ok
        else:
            info["device_found"] = False
            return f"ClawTap not found. Ensure ESP32 is powered. Status: {info}"

    info["status"] = "ok"
    return f"ClawTap connected and ready. {info}"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
