from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.accounts.scope import HasAnyPerm
from .models import AuditLog
from .services import describe_audit_event


class AuditLogList(APIView):
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.audit_view"]

    def get(self, request):
        qs = AuditLog.objects.select_related("user").order_by("-created_at")
        if a := request.query_params.get("action"):
            qs = qs.filter(action__icontains=a)
        if u := request.query_params.get("user"):
            qs = qs.filter(user__ippis_number=u)
        if d := request.query_params.get("date"):
            qs = qs.filter(created_at__date=d)
        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except (TypeError, ValueError):
            page = 1
        page_size = 100
        total = qs.count()
        entries = qs[(page - 1) * page_size:page * page_size]
        return Response({"count": total, "page": page, "page_size": page_size, "results": [{
            "id": e.pk, "created_at": e.created_at, "user": e.user.ippis_number if e.user_id else "system",
            "action": e.action,
            # Translate historic technical/blank entries when displayed without modifying
            # the immutable audit record itself.
            "description": describe_audit_event(e.action, e.description, e.previous_value, e.new_value),
            "ip_address": e.ip_address,
        } for e in entries]})
