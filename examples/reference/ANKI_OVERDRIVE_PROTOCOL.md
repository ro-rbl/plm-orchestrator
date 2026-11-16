# Anki Overdrive / Drive Bluetooth LE protocol (reference for project mode)

Put this file in a project folder used with `/project`: the coder reads it and uses these values instead of guessing.

Source: Anki's published SDK, https://github.com/anki/drive-sdk (Apache-2.0), files
`include/ankidrive/vehicle_gatt_profile.h` and `include/ankidrive/protocol.h`, read on 2026-11-15. Everything in
this file is from those two headers unless a line says "not verified".

## Service and characteristics

| What | UUID |
|---|---|
| Vehicle service (scan for this) | `BE15BEEF-6186-407E-8381-0BD89C4D8DF4` |
| Read characteristic (the car notifies on it) | `BE15BEE0-6186-407E-8381-0BD89C4D8DF4` |
| Write characteristic (commands go here) | `BE15BEE1-6186-407E-8381-0BD89C4D8DF4` |

Not verified here: whether commands must be written with or without response. Try without response first; if the
car ignores commands, use with response.

## Message format

Every message is at most 20 bytes: `[size, msg_id, payload...]`. `size` counts the bytes after itself (msg_id plus
payload). Multi-byte numbers are little-endian; floats are 32-bit IEEE little-endian.

## Commands to the car

| Command | Bytes |
|---|---|
| SDK mode on (send first, right after connecting, or the car ignores driving commands) | `03 90 01 01` (size 3, id 0x90, on = 1, flags = 0x01 override localization) |
| Set speed | `06 24 <speed int16 mm/s> <accel int16 mm/s^2> 00` (last byte: respect road piece speed limit, 0 = no) |
| Stop | set speed with speed 0 |
| Change lane | `0B 25 <horizontal speed uint16 mm/s> <horizontal accel uint16 mm/s^2> <offset from road centre float mm> 00 00` (last two: hop intent, tag) |
| Set offset from road centre (tell the car where it is; send `0.0` before the first lane change) | `05 2C <offset float mm>` |
| Cancel lane change | `01 26` |
| Turn | `03 32 <type> <trigger>`; type 0 none, 1 left, 2 right, 3 U-turn, 4 U-turn jump; trigger 0 now, 1 at the next intersection |
| Ping | `01 16` (answer id 0x17) |
| Version request | `01 18` (answer id 0x19, uint16 version) |
| Battery level request | `01 1A` (answer id 0x1B, uint16 battery level) |
| Disconnect | `01 0D` |

Example: 500 mm/s with 1000 mm/s^2 acceleration is `06 24 F4 01 E8 03 00`.

Not verified here: sensible speed limits. Community projects use roughly 300 to 1000 mm/s.

## Messages from the car (notifications on the read characteristic)

| id | Meaning | Payload after `[size, id]` |
|---|---|---|
| 0x27 | position update | location_id uint8, road_piece_id uint8, offset_from_road_center float mm, speed uint16 mm/s, parsing_flags uint8, last_recv_lane_change_cmd_id uint8, last_exec_lane_change_cmd_id uint8, last_desired_lane_change_speed uint16, last_desired_speed uint16 |
| 0x29 | transition update (the car crossed onto the next track piece) | see `protocol.h` |
| 0x2A | intersection update | see `protocol.h` |
| 0x2B | the car is delocalized (it left the track or lost its position) | none |
| 0x2D | offset from road centre update | offset float mm, lane change id uint8 |
| 0x17, 0x19, 0x1B | ping, version, battery responses | see above |

## What the headers do not say

The headers describe no proximity, collision or floor sensors. The position messages come from the car reading
codes on the track (location_id, road_piece_id). Anything else about the car's sensors is not in this source.
