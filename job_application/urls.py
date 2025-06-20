
from django.urls import path
from .views import JobApplicationListCreateView, JobApplicationDetailView, JobApplicationBulkDeleteView, JobApplicationsByRequisitionView

app_name = 'job_applications'

urlpatterns = [
    path('applications/', JobApplicationListCreateView.as_view(), name='application-list-create'),
    path('applications/<str:id>/', JobApplicationDetailView.as_view(), name='application-detail'),
    path('applications/bulk-delete/', JobApplicationBulkDeleteView.as_view(), name='application-bulk-delete'),
    path('applications/job-requisitions/<str:job_requisition_id>/applications/', JobApplicationsByRequisitionView.as_view(), name='job-applications-by-requisition'),

]
