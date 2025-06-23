
from django.urls import path
from .views import (
    JobApplicationListCreateView, JobApplicationDetailView, 
    JobApplicationBulkDeleteView,PublishedJobRequisitionsWithShortlistedApplicationsView,
    ResumeScreeningView, JobApplicationsByRequisitionView,ScheduleCancelView,ResumeParseView,
    ScheduleCreateView, ScheduleListView, ScheduleDetailView, ScheduleCompleteView,
)

app_name = 'job_applications'

urlpatterns = [
    path('applications/', JobApplicationListCreateView.as_view(), name='application-list-create'),
    path('applications/<str:id>/', JobApplicationDetailView.as_view(), name='application-detail'),
    path('applications/bulk-delete/', JobApplicationBulkDeleteView.as_view(), name='application-bulk-delete'),
    path('applications/job-requisitions/<str:job_requisition_id>/applications/', JobApplicationsByRequisitionView.as_view(), name='job-applications-by-requisition'),


    path('applications/parse-resume/', ResumeParseView.as_view(), name='resume-parse'),
    #path('requisitions/<str:job_requisition_id>/applications/', JobApplicationsByRequisitionView.as_view(), name='job-applications-by-requisition'),
    path('requisitions/<str:job_requisition_id>/screen-resumes/', ResumeScreeningView.as_view(), name='resume-screening'),
    path('published-requisitions-with-shortlisted/', PublishedJobRequisitionsWithShortlistedApplicationsView.as_view(), name='published-requisitions-with-shortlisted'),


    path('schedules/', ScheduleListView.as_view(), name='schedule-list'),
    path('schedules/create/', ScheduleCreateView.as_view(), name='schedule-create'),
    path('schedules/<str:pk>/', ScheduleDetailView.as_view(), name='schedule-detail'),
    path('schedules/<str:pk>/complete/', ScheduleCompleteView.as_view(), name='schedule-complete'),
    path('schedules/<str:pk>/cancel/', ScheduleCancelView.as_view(), name='schedule-cancel'),
]
