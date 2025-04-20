from rest_framework import routers
from django.urls import path, include
from moda import views


# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register('moda', views.ModaViewSet)
router.register('moda-members', views.ModaMembersViewSet)

urlpatterns = [
    path('', include(router.urls)),
    ]