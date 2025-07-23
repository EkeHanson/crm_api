from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (UserViewSet, PasswordResetRequestView, PasswordResetConfirmView,
                     AdminUserCreateView, UserCreateView, UserBranchUpdateView, TenantUsersListView, BranchUsersListView)

router = DefaultRouter()
router.register(r'users', UserViewSet)




urlpatterns = [
    path('', include(router.urls)),
    #path('social/callback/', SocialLoginCallbackView.as_view(), name='social_callback'),
    path('admin/create/', AdminUserCreateView.as_view(), name='admin_user_create'),
    path('create/', UserCreateView.as_view(), name='user_create'),
    path('users/<int:user_id>/branch/', UserBranchUpdateView.as_view(), name='user_branch_update'),
    path('tenant-users/', TenantUsersListView.as_view(), name='tenant_users_list'),
    path('branch-users/<int:branch_id>/', BranchUsersListView.as_view(), name='branch_users_list'),
    path('password/reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]


