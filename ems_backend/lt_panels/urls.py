from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MFMViewSet, Asset3DViewSet, assets, bms, overview_pages, overview_page
from .electrical_equipment import electrical_equipment

router = DefaultRouter()
router.register(r'mfm', MFMViewSet, basename='mfm')
router.register(r'asset3d', Asset3DViewSet, basename='asset3d')

urlpatterns = [
    path('', include(router.urls)),
    path('ems/', electrical_equipment, name='ems'),
    path('assets/', assets, name='assets'),
    path('bms/', bms, name='bms'),
    path('overview/', overview_pages, name='overview-pages'),
    path('overview/<slug:slug>/', overview_page, name='overview-page'),
]
