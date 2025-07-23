from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    JobRequisitionListCreateView,JobRequisitionDetailView,
    JobRequisitionBulkDeleteView, SoftDeletedJobRequisitionsView,
    RecoverSoftDeletedJobRequisitionsView,PermanentDeleteJobRequisitionsView,
    JobRequisitionByLinkView, ComplianceItemView, VideoSessionViewSet
)

router = DefaultRouter()
router.register(r'video-sessions', VideoSessionViewSet, basename='video-session')


app_name = 'talent_engine'

urlpatterns = [
    path('', include(router.urls)),
    path('requisitions/', JobRequisitionListCreateView.as_view(), name='requisition-list-create'),
    path('requisitions/<str:id>/', JobRequisitionDetailView.as_view(), name='requisition-detail'),
    path('requisitions/bulk/bulk-delete/', JobRequisitionBulkDeleteView.as_view(), name='requisition-bulk-delete'),
    path('requisitions/deleted/soft_deleted/', SoftDeletedJobRequisitionsView.as_view(), name='soft-deleted-requisitions'),
    path('requisitions/recover/requisition/', RecoverSoftDeletedJobRequisitionsView.as_view(), name='recover-requisitions'),
    path('requisitions/permanent-delete/requisition/', PermanentDeleteJobRequisitionsView.as_view(), name='permanent-delete-requisitions'),
    path('requisitions/by-link/<str:unique_link>/', JobRequisitionByLinkView.as_view(), name='requisition-by-link'),
    path('requisitions/<str:job_requisition_id>/compliance-items/', ComplianceItemView.as_view(), name='compliance-item-create'),
    path('requisitions/<str:job_requisition_id>/compliance-items/<str:item_id>/', ComplianceItemView.as_view(), name='compliance-item-detail'),
]