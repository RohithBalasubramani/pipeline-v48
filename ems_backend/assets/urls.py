from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssetViewSet, Asset3DModelViewSet

router = DefaultRouter()
router.register(r'asset', AssetViewSet, basename='asset')
router.register(r'asset-3d', Asset3DModelViewSet, basename='asset-3d')

urlpatterns = [
    path('', include(router.urls)),
]
