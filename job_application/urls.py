from django.urls import path
from .views import (
    JobApplicationListCreateView, JobApplicationDetailView,
    JobApplicationBulkDeleteView, PublishedJobRequisitionsWithShortlistedApplicationsView,
    ResumeScreeningView, JobApplicationsByRequisitionView,
    ResumeParseView,  ScheduleListCreateView, ScheduleDetailView,
)
app_name = 'job_applications'

urlpatterns = [
    path('applications/', JobApplicationListCreateView.as_view(), name='application-list-create'),
    path('applications/<str:id>/', JobApplicationDetailView.as_view(), name='application-detail'),
    path('applications/bulk-delete/', JobApplicationBulkDeleteView.as_view(), name='application-bulk-delete'),
    path('applications/job-requisitions/<str:job_requisition_id>/applications/', JobApplicationsByRequisitionView.as_view(), name='job-applications-by-requisition'),
    path('applications/parse-resume/', ResumeParseView.as_view(), name='resume-parse'),
    path('requisitions/<str:job_requisition_id>/screen-resumes/', ResumeScreeningView.as_view(), name='resume-screening'),
    path('published-requisitions-with-shortlisted/', PublishedJobRequisitionsWithShortlistedApplicationsView.as_view(), name='published-requisitions-with-shortlisted'),
    path('schedules/', ScheduleListCreateView.as_view(), name='schedule-list-create'),  # Handles both listing and creating schedules
    path('schedules/<str:tenant_unique_id>/', ScheduleDetailView.as_view(), name='schedule-detail'),  # Handles retrieve, update, complete, cancel, and delete
]