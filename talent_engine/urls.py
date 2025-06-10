# apps/talent_engine/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import JobPostingViewSet

router = DefaultRouter()
router.register(r'job-postings', JobPostingViewSet)

urlpatterns = [
    path('', include(router.urls)),
]