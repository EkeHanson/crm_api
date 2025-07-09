from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, SocialLoginCallbackView, AdminUserCreateView, UserCreateView

router = DefaultRouter()
router.register(r'users', UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('social/callback/', SocialLoginCallbackView.as_view(), name='social_callback'),
    path('admin/create/', AdminUserCreateView.as_view(), name='admin_user_create'),
    path('create/', UserCreateView.as_view(), name='user_create'),
]