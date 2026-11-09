"""Line drawings in Braille characters (2 x 4 dots each), for showing a CAD part in any terminal."""

import math

DOTS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))  # [row][col] bit of U+2800


AZIMUTH, ELEVATION = math.radians(35), math.radians(25)  # turned and tilted, so a cube's corners don't overlap


def isometric(point):
    """Screen (x, y) of a 3D point seen from the front-right and above; screen y grows downward."""
    x, y, z = point
    xr = x * math.cos(AZIMUTH) - y * math.sin(AZIMUTH)
    yr = x * math.sin(AZIMUTH) + y * math.cos(AZIMUTH)
    return xr, -(z * math.cos(ELEVATION) + yr * math.sin(ELEVATION))


def draw(polylines, cols=40, rows=18):
    """The polylines' isometric view, fitted into cols x rows characters, as a list of strings."""
    flat = [[isometric(p) for p in line] for line in polylines if line]
    pts = [p for line in flat for p in line]
    if not pts:
        return []
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    w, h = cols * 2 - 1, rows * 4 - 1
    span = max(max(xs) - min(xs), (max(ys) - min(ys)) * w / h, 1e-9)
    scale = w / span
    ox = (w - (max(xs) - min(xs)) * scale) / 2 - min(xs) * scale
    oy = (h - (max(ys) - min(ys)) * scale) / 2 - min(ys) * scale
    grid = [[0] * cols for _ in range(rows)]

    def dot(x, y):
        if 0 <= x <= w and 0 <= y <= h:
            grid[y // 4][x // 2] |= DOTS[y % 4][x % 2]

    for line in flat:
        for (x0, y0), (x1, y1) in zip(line, line[1:]):
            a = (round(x0 * scale + ox), round(y0 * scale + oy))
            b = (round(x1 * scale + ox), round(y1 * scale + oy))
            n = max(abs(b[0] - a[0]), abs(b[1] - a[1]), 1)
            for i in range(n + 1):
                dot(round(a[0] + (b[0] - a[0]) * i / n), round(a[1] + (b[1] - a[1]) * i / n))
    return ["".join(chr(0x2800 + c) for c in row).rstrip("⠀") for row in grid]
