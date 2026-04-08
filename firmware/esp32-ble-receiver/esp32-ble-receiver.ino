// ClawTap — ESP32 BLE Receiver
// Принимает текст по BLE (Nordic UART Service) и отправляет на Serial2 TX
// Подключение: ESP32 GPIO17 (TX2) → RP2040 GP1 (UART0 RX)

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#define SERVICE_UUID        "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHAR_RX_UUID        "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHAR_TX_UUID        "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

#define SERIAL_TX_PIN 17
#define SERIAL_RX_PIN 16
#define LED_PIN 2

BLECharacteristic *pTxCharacteristic;
bool deviceConnected = false;
bool oldDeviceConnected = false;

class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *pServer) override {
    deviceConnected = true;
    digitalWrite(LED_PIN, HIGH);
  }
  void onDisconnect(BLEServer *pServer) override {
    deviceConnected = false;
    digitalWrite(LED_PIN, LOW);
    // НЕ вызываем startAdvertising() здесь — BLE-стек ещё не завершил cleanup
  }
};

class RxCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *pCharacteristic) override {
    String value = pCharacteristic->getValue();
    if (value.length() > 0) {
      Serial2.print(value);
    }
  }
};

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, SERIAL_RX_PIN, SERIAL_TX_PIN);

  BLEDevice::init("ClawTap");
  BLEServer *pServer = BLEDevice::createServer();
  pServer->setCallbacks(new ServerCallbacks());

  BLEService *pService = pServer->createService(SERVICE_UUID);

  pTxCharacteristic = pService->createCharacteristic(
    CHAR_TX_UUID, BLECharacteristic::PROPERTY_NOTIFY
  );
  pTxCharacteristic->addDescriptor(new BLE2902());

  BLECharacteristic *pRxCharacteristic = pService->createCharacteristic(
    CHAR_RX_UUID, BLECharacteristic::PROPERTY_WRITE
  );
  pRxCharacteristic->setCallbacks(new RxCallbacks());

  pService->start();

  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->start();

  Serial.println("ClawTap BLE ready, waiting for connection...");
}

void loop() {
  // Restart advertising после disconnect с задержкой
  if (!deviceConnected && oldDeviceConnected) {
    delay(500);  // дать BLE-стеку завершить cleanup
    BLEDevice::startAdvertising();
    Serial.println("Advertising restarted");
    oldDeviceConnected = false;
  }
  if (deviceConnected && !oldDeviceConnected) {
    oldDeviceConnected = true;
  }
  delay(10);
}
