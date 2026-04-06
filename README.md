# GhostType MCP

BLE-to-USB HID keyboard bridge exposed as an MCP (Model Context Protocol) server.

**Send keystrokes to any computer via Bluetooth** — let AI assistants type on your machine through a hardware bridge.

## Architecture

```
Claude / AI  →  MCP Server (Python)  →  BLE  →  ESP32  →  UART  →  RP2040  →  USB HID  →  Computer
```

## Hardware

- **ESP32-WROOM-32** — BLE receiver, Nordic UART Service
- **RP2040-Zero** (Waveshare) — USB HID keyboard, hardware UART RX

## MCP Tools

| Tool | Description |
|------|-------------|
| `type_text` | Type a string of text |
| `press_key` | Press a special key (enter, escape, f1-f12, arrows, etc.) |
| `combo_keys` | Press a key combination (ctrl+c, alt+tab, win+r, etc.) |
| `health_check` | Check BLE connection status and device availability |

## Setup

```bash
pip install -r requirements.txt
python ghosttype_mcp.py
```

## License

MIT
