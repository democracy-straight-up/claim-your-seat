from rest_framework import routers
from django.urls import path, include
from rep import views


# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register('district-council', views.DistrictCouncilViewSet)
router.register('district-council-members', views.DistrictCouncilMembersViewSet)
router.register('district-council-member-contacts', views.DistrictCouncilMemberContactViewSet)

urlpatterns = [
    path('', include(router.urls)),
    ]