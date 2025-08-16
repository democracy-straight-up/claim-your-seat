from rest_framework import routers
from django.urls import path, include
from holc import views
from holc import backnforth_views


# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register('holc', views.HolcViewSet)
router.register('holc-members', views.HolcMembersViewSet)
router.register('holc-member-contacts', views.HolcMemberContactViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # BackNForth chat endpoints
    path('holc/<int:holc_code>/backnforth/messages/', 
         backnforth_views.HolcBackNForthChatViewSet.as_view({'get': 'list', 'post': 'create'}), 
         name='holc-backnforth-list'),
    path('holc/<int:holc_code>/backnforth/messages/<int:pk>/', 
         backnforth_views.HolcBackNForthChatViewSet.as_view({
             'get': 'retrieve', 
             'put': 'update', 
             'patch': 'partial_update', 
             'delete': 'destroy'
         }), 
         name='holc-backnforth-detail'),
    path('holc/<int:holc_code>/backnforth/search/', 
         backnforth_views.HolcBackNForthChatViewSet.as_view({'get': 'search'}), 
         name='holc-backnforth-search'),
    path('holc/<int:holc_code>/backnforth/statistics/', 
         backnforth_views.HolcBackNForthChatViewSet.as_view({'get': 'statistics'}), 
         name='holc-backnforth-statistics'),
    path('holc/<int:holc_code>/backnforth/members/', 
         backnforth_views.HolcBackNForthChatViewSet.as_view({'get': 'members_online'}), 
         name='holc-backnforth-members'),
]