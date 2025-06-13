# apps/talent_engine/urls.py
from django.urls import path
from .views import JobRequisitionListCreateView, JobRequisitionDetailView, JobRequisitionBulkDeleteView

urlpatterns = [
    path('requisitions/', JobRequisitionListCreateView.as_view(), name='requisition-list-create'),
    path('requisitions/<uuid:id>/', JobRequisitionDetailView.as_view(), name='requisition-detail'),
    path('requisitions/bulk-delete/', JobRequisitionBulkDeleteView.as_view(), name='requisition-bulk-delete'),
]