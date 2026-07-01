from django.urls import path

from . import views

urlpatterns = [
    path("auth/register", views.register, name="kc-register"),
    path("auth/login", views.login, name="kc-login"),
    path("auth/refresh", views.refresh, name="kc-refresh"),
    path("auth/assign-role/<str:username>", views.assign_role, name="kc-assign-role"),
    path("auth/roles/<str:username>", views.roles, name="kc-roles"),
]
