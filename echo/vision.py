"""Line of sight helpers."""

from .consts import GRID_H, GRID_W


def line_tiles(a, b):
    """Bresenham line from a to b, both ends included."""
    (x0, y0), (x1, y1) = a, b
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x1 > x0 else -1
    sy = 1 if y1 > y0 else -1
    err = dx - dy
    out = []
    while True:
        out.append((x0, y0))
        if (x0, y0) == (x1, y1):
            return out
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


def clear_line(a, b, blocks):
    """True when no tile strictly between a and b blocks sight."""
    pts = line_tiles(a, b)
    return not any(blocks(x, y) for x, y in pts[1:-1])


def visible_tiles(origin, radius, blocks):
    ox, oy = origin
    out = set()
    limit = radius * radius + radius
    for y in range(max(0, oy - radius), min(GRID_H, oy + radius + 1)):
        for x in range(max(0, ox - radius), min(GRID_W, ox + radius + 1)):
            if (x - ox) ** 2 + (y - oy) ** 2 > limit:
                continue
            if clear_line(origin, (x, y), blocks):
                out.add((x, y))
    return out
