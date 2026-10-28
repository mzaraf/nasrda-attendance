"""Small geometry helpers for campus and building geofences.

Coordinates are stored as [latitude, longitude]. These functions intentionally
avoid a GIS dependency while still ensuring building polygons remain wholly
inside their campus polygon.
"""


def point_on_segment(point, start, end, epsilon=1e-10):
    py, px = point
    ay, ax = start
    by, bx = end
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if abs(cross) > epsilon:
        return False
    return min(ax, bx) - epsilon <= px <= max(ax, bx) + epsilon and min(ay, by) - epsilon <= py <= max(ay, by) + epsilon


def point_in_polygon(lat, lng, polygon):
    """Return True when a point is inside or on the edge of a polygon."""
    point = (lat, lng)
    inside = False
    last = len(polygon) - 1
    for index, current in enumerate(polygon):
        previous = polygon[last]
        if point_on_segment(point, current, previous):
            return True
        cy, cx = current
        py, px = previous
        if (cy > lat) != (py > lat) and lng < (px - cx) * (lat - cy) / (py - cy) + cx:
            inside = not inside
        last = index
    return inside


def _orientation(a, b, c):
    value = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])
    if abs(value) < 1e-10:
        return 0
    return 1 if value > 0 else 2


def segments_intersect(a, b, c, d):
    """Includes touching edges; buildings touching a campus edge are rejected."""
    o1, o2 = _orientation(a, b, c), _orientation(a, b, d)
    o3, o4 = _orientation(c, d, a), _orientation(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    return ((o1 == 0 and point_on_segment(c, a, b)) or
            (o2 == 0 and point_on_segment(d, a, b)) or
            (o3 == 0 and point_on_segment(a, c, d)) or
            (o4 == 0 and point_on_segment(b, c, d)))


def polygon_within_polygon(inner, outer):
    """True only when the entire inner polygon is strictly within the outer one."""
    if len(inner) < 3 or len(outer) < 3:
        return False
    if not all(point_in_polygon(lat, lng, outer) for lat, lng in inner):
        return False
    for index, start in enumerate(inner):
        end = inner[(index + 1) % len(inner)]
        for outer_index, outer_start in enumerate(outer):
            outer_end = outer[(outer_index + 1) % len(outer)]
            if segments_intersect(start, end, outer_start, outer_end):
                return False
    return True
