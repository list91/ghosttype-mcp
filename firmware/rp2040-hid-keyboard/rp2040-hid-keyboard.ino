// ClawTap — RP2040-Zero UART-to-USB-HID Keyboard
// Принимает текст по аппаратному UART (от ESP32) и печатает как USB HID клавиатура
// Подключение: ESP32 GPIO17 (TX) → RP2040 GP1 (UART0 RX)
//
// Протокол:
//   Обычный символ (0x20-0x7E, 0x08-0x0A, 0xB0-0xDB) → Keyboard.write()
//   Комбинация: 0x01 + count(1-5) + key1 + key2 + ... → press all, delay, releaseAll
//
// Примеры комбинаций (отправляемые байты):
//   Ctrl+C        → 0x01 0x02 0x80 0x63
//   Ctrl+V        → 0x01 0x02 0x80 0x76
//   Ctrl+Alt+Del  → 0x01 0x03 0x80 0x82 0xD4
//   Alt+Tab       → 0x01 0x02 0x82 0xB3
//   Win+R         → 0x01 0x02 0x83 0x72
//
// Коды модификаторов:
//   0x80 = LEFT_CTRL    0x84 = RIGHT_CTRL
//   0x81 = LEFT_SHIFT   0x85 = RIGHT_SHIFT
//   0x82 = LEFT_ALT     0x86 = RIGHT_ALT
//   0x83 = LEFT_GUI     0x87 = RIGHT_GUI

#include <Keyboard.h>

#define COMBO_START 0x01
#define MAX_COMBO 5
#define UART_TIMEOUT_MS 50

void setup() {
  Serial1.setRX(1);
  Serial1.setTX(0);
  Serial1.begin(9600);

  Keyboard.begin();
  delay(1000);
}

uint8_t readByteTimeout() {
  unsigned long start = millis();
  while (!Serial1.available()) {
    if (millis() - start > UART_TIMEOUT_MS) return 0;
  }
  return Serial1.read();
}

void loop() {
  while (Serial1.available()) {
    uint8_t c = Serial1.read();

    if (c == '\r') continue;

    if (c == COMBO_START) {
      // Комбинация: читаем count + клавиши
      uint8_t count = readByteTimeout();
      if (count < 1 || count > MAX_COMBO) continue;

      uint8_t keys[MAX_COMBO];
      for (uint8_t i = 0; i < count; i++) {
        keys[i] = readByteTimeout();
      }

      // Нажать все
      for (uint8_t i = 0; i < count; i++) {
        Keyboard.press(keys[i]);
      }
      delay(20);
      Keyboard.releaseAll();
    } else {
      Keyboard.write(c);
    }

    delay(5);
  }
}
