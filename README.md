# ClawTap MCP

BLE-to-USB HID keyboard bridge exposed as an [MCP](https://modelcontextprotocol.io/) server.

**Send keystrokes to any computer via Bluetooth** — let AI assistants type on your machine through a hardware bridge.

## Architecture

```
Claude / AI  →  MCP Server (Python)  →  BLE  →  ESP32  →  UART  →  RP2040  →  USB HID  →  Computer
```

## Prerequisites

- **Bluetooth adapter** on the host machine (built-in or USB dongle)
- **Python 3.10+**
- **Hardware** (see below)

## Install MCP Server

```bash
# Claude Code / Claude Desktop
claude mcp add clawtap -- uvx clawtap-mcp

# Or manually
pip install clawtap-mcp
```

## Hardware Setup

### Components

| Component | Role | Price |
|-----------|------|-------|
| ESP32-WROOM-32 | BLE receiver | ~$4 |
| Waveshare RP2040-Zero | USB HID keyboard | ~$3 |
| 3 DuPont wires | Connection | ~$0 |

### Wiring

```
ESP32              RP2040-Zero
─────              ───────────
GPIO17 (TX) ─────► GP1 (UART0 RX)
GND ─────────────► GND
VIN ◄──────────── 5V (VBUS)
```

RP2040-Zero plugs into the target computer via USB-C. ESP32 is powered from RP2040's 5V pin.

### Firmware

#### ESP32 (BLE receiver)

```bash
# Install ESP32 core
arduino-cli core install esp32:esp32

# Compile and upload (ESP32 connected via USB)
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/esp32-ble-receiver/
arduino-cli upload --fqbn esp32:esp32:esp32 --port COMx firmware/esp32-ble-receiver/
```

The ESP32 advertises as **"ClawTap"** over BLE using Nordic UART Service.

#### RP2040-Zero (USB HID keyboard)

```bash
# Install RP2040 core
arduino-cli core install rp2040:rp2040 \
  --additional-urls https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json

# Compile
arduino-cli compile --fqbn rp2040:rp2040:waveshare_rp2040_zero firmware/rp2040-hid-keyboard/

# Flash: hold BOOT button, plug USB-C, copy .uf2 to RPI-RP2 drive
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `type_text` | Type ASCII text as HID keystrokes |
| `press_key` | Press a special key (enter, escape, f1-f12, arrows, etc.) |
| `combo_keys` | Press a key combination up to 5 keys (ctrl+c, alt+tab, win+r) |
| `health_check` | Check BLE connection status and device availability |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ClawTap not found` | Ensure ESP32 is powered and not connected to another BLE client. Press RESET on ESP32. |
| Text appears as wrong characters | Switch keyboard layout on target computer (e.g. EN for English text) |
| BLE disconnects frequently | Keep ESP32 within 10m range. Check power supply stability. |
| RP2040 not recognized as keyboard | Re-flash firmware. Try different USB port. |

## License

MIT
