from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.attendance import views as v
from apps.accounts import views as av
from apps.audit import views as audit_views
from apps.org import views as org_views
from apps.core import views as core_views

router = DefaultRouter()
router.register("campuses", v.CampusViewSet)
router.register("geofences", v.GeofenceViewSet)
router.register("leave", v.LeaveApprovalViewSet)
router.register("official-duty", v.OfficialDutyViewSet)
router.register("recurring-leave", v.RecurringLeaveViewSet)
router.register("holidays", v.HolidayViewSet)
router.register("staff", av.StaffViewSet)
router.register("roles", av.RoleViewSet)
router.register("departments", org_views.DepartmentViewSet)

api = [
    path("auth/login/", v.LoginView.as_view()),
    path("auth/mfa/verify/", v.MFAVerifyLogin.as_view()),
    path("auth/password-reset/", av.PasswordResetRequest.as_view()),
    path("auth/change-password/", av.ChangePassword.as_view()),
    path("auth/logout/", v.LogoutView.as_view()),
    path("auth/me/", v.MeView.as_view()),

    path("reports/export/", v.ReportExport.as_view()),
    path("reports/scope/", v.ReportScope.as_view()),

    path("staff/device/register/options/", v.DeviceRegisterOptions.as_view()),
    path("staff/mfa/setup/", v.MFASetup.as_view()),
    path("staff/mfa/confirm/", v.MFAConfirmSetup.as_view()),
    path("staff/device/register/verify/", v.DeviceRegisterVerify.as_view()),
    path("staff/devices/", v.DeviceList.as_view()),
    path("staff/devices/<int:pk>/revoke/", v.DeviceRevoke.as_view()),
    path("admin/device-removals/", v.DeviceRemovalQueue.as_view()),
    path("admin/device-removals/<int:pk>/decide/", v.DeviceRemovalDecide.as_view()),

    path("attendance/challenge/", v.Challenge.as_view()),
    path("attendance/check-in/", v.CheckIn.as_view()),
    path("attendance/check-out/", v.CheckOut.as_view()),
    path("attendance/today/", v.Today.as_view()),
    path("attendance/history/", v.History.as_view()),

    path("activities/today/", v.TodayActivities.as_view()),
    path("activities/<int:pk>/", v.ActivityDetail.as_view()),
    path("activities/<int:pk>/attachments/", v.AttachmentUpload.as_view()),
    path("activities/categories/", v.Categories.as_view()),

    path("admin/dashboard/", v.AdminDashboard.as_view()),
    path("admin/attendance/", v.AdminLive.as_view()),
    path("admin/settings/", core_views.SystemSettingsView.as_view()),
    path("admin/corrections/", v.CorrectionQueue.as_view()),
    path("admin/corrections/<int:pk>/decide/", v.CorrectionDecide.as_view()),
    path("admin/review-queue/", v.ReviewQueue.as_view()),
    path("admin/review-queue/<int:pk>/decide/", v.ReviewDecide.as_view()),
    path("admin/department-review/", v.DepartmentReviewQueue.as_view()),
    path("admin/department-review/<str:kind>/<int:pk>/decide/", v.DepartmentReviewDecide.as_view()),

    path("attendance/correction/", v.CorrectionRequest.as_view()),
    path("attendance/correction/mine/", v.MyCorrections.as_view()),
    path("staff/leave/", v.MyLeave.as_view()),
    path("staff/official-duty/", v.MyOfficialDuty.as_view()),
    path("staff/recurring-leave/", v.MyRecurringLeave.as_view()),

    path("admin/staff/import/preview/", av.StaffImportPreview.as_view()),
    path("admin/staff/import/commit/", av.StaffImportCommit.as_view()),
    path("admin/permissions/", av.PermissionList.as_view()),

    path("admin/audit-logs/", audit_views.AuditLogList.as_view()),
    # Keep the router last: its detail route can otherwise interpret named endpoints
    # (such as /admin/settings/) as a staff primary key.
    path("admin/", include(router.urls)),
]

urlpatterns = [path("django-admin/", admin.site.urls), path("api/", include(api))]
