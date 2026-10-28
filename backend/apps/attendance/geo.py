import math
from apps.org.geometry import point_in_polygon


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def inside_geofence(gf, lat, lng, centre):
    """Returns (is_inside, distance_to_centre_m)."""
    dist = haversine_m(lat, lng, *centre)
    if gf.kind == "circle":
        return dist <= gf.radius_m, dist
    return point_in_polygon(lat, lng, gf.polygon), dist


def resolve_campus(user, lat, lng):
    """Find an allowed campus building assigned to the staff member's department."""
    from apps.org.models import Campus, Geofence
    if not user.department_id:
        return None, None, None
    campuses = Campus.objects.filter(id__in=user.allowed_campus_ids(), is_active=True) \
                             .prefetch_related("geofences__departments")
    for campus in campuses:
        # The campus is the outer boundary; a building alone is never sufficient.
        if not campus.boundary or not point_in_polygon(lat, lng, campus.boundary):
            continue
        for gf in campus.geofences.all():
            if not gf.is_active or not gf.departments.filter(pk=user.department_id).exists():
                continue
            ok, dist = inside_geofence(gf, lat, lng, (campus.latitude, campus.longitude))
            if ok:
                return campus, gf, dist
    return None, None, None
