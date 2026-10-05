import math


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def point_in_polygon(lat, lng, poly):
    """Ray casting. poly = [[lat, lng], ...]"""
    inside, n, j = False, len(poly), len(poly) - 1
    for i in range(n):
        yi, xi = poly[i]
        yj, xj = poly[j]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def inside_geofence(gf, lat, lng, centre):
    """Returns (is_inside, distance_to_centre_m)."""
    dist = haversine_m(lat, lng, *centre)
    if gf.kind == "circle":
        return dist <= gf.radius_m, dist
    return point_in_polygon(lat, lng, gf.polygon), dist


def resolve_campus(user, lat, lng):
    """First allowed campus whose active geofence contains the point, else None."""
    from apps.org.models import Campus
    campuses = Campus.objects.filter(id__in=user.allowed_campus_ids(), is_active=True) \
                             .prefetch_related("geofences")
    for campus in campuses:
        for gf in campus.geofences.all():
            if not gf.is_active:
                continue
            ok, dist = inside_geofence(gf, lat, lng, (campus.latitude, campus.longitude))
            if ok:
                return campus, dist
    return None, None