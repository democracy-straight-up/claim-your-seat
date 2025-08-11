from rest_framework import routers
from django.urls import path, include
from holc import views


# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register('holc', views.HolcViewSet)
router.register('holc-members', views.HolcMembersViewSet)
router.register('holc-member-contact', views.HolcMemberContactViewSet)

urlpatterns = [path('', include(router.urls)),]