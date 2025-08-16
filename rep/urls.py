from rest_framework import routers
from django.urls import path, include
from rep import views
from rep import backnforth_views

# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register('district-council', views.DistrictCouncilViewSet)
router.register('district-council-members', views.DistrictCouncilMembersViewSet)
router.register('district-council-member-contacts', views.DistrictCouncilMemberContactViewSet)

urlpatterns = [
    path('', include(router.urls)),
        # BackNForth endpoints
    path('district-council/<int:district_council_code>/backnforth/messages/', 
         backnforth_views.DistrictCouncilBackNForthViewSet.as_view({'get': 'list', 'post': 'create'}), 
         name='district-council-backnforth-list'),
         
    path('district-council/<int:district_council_code>/backnforth/messages/<int:pk>/', 
         backnforth_views.DistrictCouncilBackNForthViewSet.as_view({
             'get': 'retrieve', 
             'put': 'update', 
             'patch': 'partial_update', 
             'delete': 'destroy'
         }), 
         name='district-council-backnforth-detail'),

    path('district-council/<int:district_council_code>/backnforth/search/', 
         backnforth_views.DistrictCouncilBackNForthViewSet.as_view({'get': 'search'}), 
         name='district-council-backnforth-search'),

    path('district-council/<int:district_council_code>/backnforth/statistics/', 
         backnforth_views.DistrictCouncilBackNForthViewSet.as_view({'get': 'statistics'}), 
         name='district-council-backnforth-statistics'),

    path('district-council/<int:district_council_code>/backnforth/members/', 
         backnforth_views.DistrictCouncilBackNForthViewSet.as_view({'get': 'members_online'}), 
         name='district-council-backnforth-members'),

    ]