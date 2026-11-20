from django.urls import path
from .views import UserListCreateView, UserDetailView, UserStatusView, UserPermissionsView

app_name = 'users'

urlpatterns = [
    path('', UserListCreateView.as_view(), name='user-list'),
    path('<uuid:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('<uuid:pk>/status/', UserStatusView.as_view(), name='user-status'),
    path('<uuid:pk>/permissions/', UserPermissionsView.as_view(), name='user-permissions'),
]
