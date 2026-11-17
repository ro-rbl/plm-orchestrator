// AnkiOverdrive.swift: the Anki Overdrive / Drive car protocol as ready-made values (a building block from plm;
// it compiles as it is, so change your own files, not this one). Use it with BLECentral.swift. The numbers are
// from Anki's published SDK (github.com/anki/drive-sdk, protocol.h and vehicle_gatt_profile.h).
//
//     let ble = BLECentral(services: [AnkiOverdrive.service])       // lists only Anki cars
//     ble.onReady = { carID in                                      // carID is a UUID (BLEDevice.id)
//         ble.write(AnkiOverdrive.sdkModeOn(), to: carID, characteristic: AnkiOverdrive.writeCharacteristic)
//     }                                                             // send SDK mode once a car is ready, before driving
//     ble.write(AnkiOverdrive.setSpeed(mmPerSecond: 500), to: carID, characteristic: AnkiOverdrive.writeCharacteristic)
//     ble.write(AnkiOverdrive.stop(), to: carID, characteristic: AnkiOverdrive.writeCharacteristic)
//     ble.onReceive = { carID, characteristic, data in
//         if let position = AnkiOverdrive.position(from: data) { ... position.speedMMPerSecond ... }
//     }
//
// Every command function returns Data to pass to BLECentral.write. Never build the command bytes by hand.
// AnkiOverdrive is a namespace, not an object: never write AnkiOverdrive() or keep one in a property.

import CoreBluetooth
import Foundation

enum AnkiOverdrive {
    static let service = CBUUID(string: "BE15BEEF-6186-407E-8381-0BD89C4D8DF4")
    /// The car notifies on this one (BLECentral subscribes by itself).
    static let readCharacteristic = CBUUID(string: "BE15BEE0-6186-407E-8381-0BD89C4D8DF4")
    /// Commands are written to this one.
    static let writeCharacteristic = CBUUID(string: "BE15BEE1-6186-407E-8381-0BD89C4D8DF4")

    /// Must be sent first after a car is ready, or the car ignores driving commands.
    static func sdkModeOn() -> Data { Data([0x03, 0x90, 0x01, 0x01]) }

    /// Drive at a speed (about 300 to 1000 mm/s is usual). 0 stops the car.
    static func setSpeed(mmPerSecond: Int, acceleration: Int = 1000) -> Data {
        Data([0x06, 0x24]) + int16(mmPerSecond) + int16(acceleration) + Data([0x00])
    }

    static func stop() -> Data { setSpeed(mmPerSecond: 0, acceleration: 2000) }

    /// Tell the car where it is across the track; send 0 once before the first lane change.
    static func setOffsetFromRoadCenter(mm: Float) -> Data { Data([0x05, 0x2C]) + float32(mm) }

    /// Move sideways to an offset from the road centre (about -68 to 68 mm).
    static func changeLane(toOffsetMM offset: Float, horizontalSpeed: Int = 300, horizontalAcceleration: Int = 300) -> Data {
        Data([0x0B, 0x25]) + int16(horizontalSpeed) + int16(horizontalAcceleration) + float32(offset) + Data([0x00, 0x00])
    }

    static func ping() -> Data { Data([0x01, 0x16]) }
    static func batteryLevelRequest() -> Data { Data([0x01, 0x1A]) }
    static func versionRequest() -> Data { Data([0x01, 0x18]) }
    static func disconnect() -> Data { Data([0x01, 0x0D]) }

    struct Position {
        let locationID: Int
        let roadPieceID: Int
        let offsetFromRoadCenterMM: Float
        let speedMMPerSecond: Int
    }

    /// The car's position update (message 0x27), or nil when the data is another message.
    static func position(from data: Data) -> Position? {
        let bytes = [UInt8](data)
        guard bytes.count >= 10, bytes[1] == 0x27 else { return nil }
        let offset = Float(bitPattern: UInt32(bytes[4]) | UInt32(bytes[5]) << 8 | UInt32(bytes[6]) << 16 | UInt32(bytes[7]) << 24)
        return Position(locationID: Int(bytes[2]), roadPieceID: Int(bytes[3]), offsetFromRoadCenterMM: offset,
                        speedMMPerSecond: Int(bytes[8]) | Int(bytes[9]) << 8)
    }

    /// The battery level from its response (message 0x1B), or nil when the data is another message.
    static func batteryLevel(from data: Data) -> Int? {
        let bytes = [UInt8](data)
        guard bytes.count >= 4, bytes[1] == 0x1B else { return nil }
        return Int(bytes[2]) | Int(bytes[3]) << 8
    }

    /// True when the car reports it left the track or lost its position (message 0x2B).
    static func isDelocalized(_ data: Data) -> Bool { data.count >= 2 && data[data.startIndex + 1] == 0x2B }

    private static func int16(_ value: Int) -> Data {
        let v = UInt16(truncatingIfNeeded: max(-32768, min(32767, value)))
        return Data([UInt8(v & 0xFF), UInt8(v >> 8)])
    }

    private static func float32(_ value: Float) -> Data {
        let bits = value.bitPattern
        return Data([UInt8(bits & 0xFF), UInt8((bits >> 8) & 0xFF), UInt8((bits >> 16) & 0xFF), UInt8(bits >> 24)])
    }
}
