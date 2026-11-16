// BLECentral.swift: Bluetooth LE from the Mac, iPad or iPhone side, on Apple's CoreBluetooth (a building block
// from plm; it compiles as it is, so change your own files, not this one). It scans, connects to several devices
// at once, writes data and receives notifications.
//
//     @StateObject private var ble = BLECentral()              // or BLECentral(services: [CBUUID(string: "...")])
//     ble.onReceive = { deviceID, characteristic, data in ... } // called on the main queue
//     ble.startScanning()                                       // ble.devices fills in; show it in a List
//     ble.connect(device.id)                                    // several devices can be connected together
//     ble.write(Data([0x01, 0x02]), to: device.id, characteristic: CBUUID(string: "..."))
//
// Everything here runs on the main queue. The app's Info.plist needs NSBluetoothAlwaysUsageDescription (plm adds it).

import Combine
import CoreBluetooth
import Foundation

struct BLEDevice: Identifiable, Equatable {
    let id: UUID
    var name: String
    var rssi: Int          // signal strength in dBm, closer to 0 is stronger
    var connected: Bool
    var ready: Bool        // connected and its characteristics are known: write() works now
}

final class BLECentral: NSObject, ObservableObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    @Published var devices: [BLEDevice] = []
    @Published var isScanning = false
    @Published var bluetoothOn = false
    @Published var lastError: String?

    /// Data a connected device sent: (device id, characteristic, data).
    var onReceive: ((UUID, CBUUID, Data) -> Void)?
    /// A device finished connecting and can be written to.
    var onReady: ((UUID) -> Void)?

    private var central: CBCentralManager!
    private let services: [CBUUID]?
    private var peripherals: [UUID: CBPeripheral] = [:]
    private var characteristics: [UUID: [CBUUID: CBCharacteristic]] = [:]
    private var wantsScan = false

    /// services: only devices that advertise one of these are listed; nil lists every device.
    init(services: [CBUUID]? = nil) {
        self.services = services
        super.init()
        central = CBCentralManager(delegate: self, queue: nil)
    }

    func startScanning() {
        wantsScan = true
        guard central.state == .poweredOn else { return }  // starts by itself once Bluetooth is on
        central.scanForPeripherals(withServices: services, options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
        isScanning = true
    }

    func stopScanning() {
        wantsScan = false
        if central.state == .poweredOn { central.stopScan() }
        isScanning = false
    }

    func connect(_ id: UUID) {
        guard let peripheral = peripherals[id] else { return }
        central.connect(peripheral, options: nil)
    }

    func disconnect(_ id: UUID) {
        guard let peripheral = peripherals[id] else { return }
        central.cancelPeripheralConnection(peripheral)
    }

    /// Sends data to a connected device. Returns false when the device or the characteristic isn't ready.
    @discardableResult
    func write(_ data: Data, to id: UUID, characteristic: CBUUID, withResponse: Bool = false) -> Bool {
        guard let peripheral = peripherals[id], peripheral.state == .connected,
              let target = characteristics[id]?[characteristic] else { return false }
        peripheral.writeValue(data, for: target, type: withResponse ? .withResponse : .withoutResponse)
        return true
    }

    // MARK: CBCentralManagerDelegate

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        bluetoothOn = central.state == .poweredOn
        if central.state == .poweredOn {
            if wantsScan { startScanning() }
        } else {
            isScanning = false
            if central.state == .unauthorized { lastError = "Bluetooth permission was denied for this app." }
            if central.state == .poweredOff { lastError = "Bluetooth is turned off." }
        }
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                        advertisementData: [String: Any], rssi RSSI: NSNumber) {
        let id = peripheral.identifier
        peripherals[id] = peripheral
        let advertised = advertisementData[CBAdvertisementDataLocalNameKey] as? String
        let name = peripheral.name ?? advertised ?? "Unnamed device"
        if let index = devices.firstIndex(where: { $0.id == id }) {
            devices[index].name = name
            devices[index].rssi = RSSI.intValue
        } else {
            devices.append(BLEDevice(id: id, name: name, rssi: RSSI.intValue, connected: false, ready: false))
        }
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        update(peripheral.identifier) { $0.connected = true }
        peripheral.delegate = self
        peripheral.discoverServices(nil)
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        lastError = error?.localizedDescription ?? "Could not connect."
        update(peripheral.identifier) { $0.connected = false; $0.ready = false }
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        characteristics[peripheral.identifier] = nil
        update(peripheral.identifier) { $0.connected = false; $0.ready = false }
    }

    // MARK: CBPeripheralDelegate

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        for service in peripheral.services ?? [] {
            peripheral.discoverCharacteristics(nil, for: service)
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        let id = peripheral.identifier
        for characteristic in service.characteristics ?? [] {
            characteristics[id, default: [:]][characteristic.uuid] = characteristic
            if characteristic.properties.contains(.notify) || characteristic.properties.contains(.indicate) {
                peripheral.setNotifyValue(true, for: characteristic)
            }
        }
        let wasReady = devices.first(where: { $0.id == id })?.ready ?? false
        update(id) { $0.ready = true }
        if !wasReady { onReady?(id) }
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard let data = characteristic.value else { return }
        onReceive?(peripheral.identifier, characteristic.uuid, data)
    }

    private func update(_ id: UUID, _ change: (inout BLEDevice) -> Void) {
        guard let index = devices.firstIndex(where: { $0.id == id }) else { return }
        change(&devices[index])
    }
}
