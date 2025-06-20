from django.urls import path
from .views import JobRequisitionListCreateView, JobRequisitionDetailView, JobRequisitionBulkDeleteView, JobRequisitionByLinkView

urlpatterns = [
    path('requisitions/', JobRequisitionListCreateView.as_view(), name='requisition-list-create'),
    path('requisitions/<str:id>/', JobRequisitionDetailView.as_view(), name='requisition-detail'),
    path('requisitions/by-link/<str:unique_link>/', JobRequisitionByLinkView.as_view(), name='requisition-by-link'),
    path('requisitions/bulk-delete/', JobRequisitionBulkDeleteView.as_view(), name='requisition-bulk-delete'),
]