from rest_framework import routers
from django.urls import path, include
from moda import views
from moda.backnforth_views import ModaBackNForthChatViewSet


# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register('moda', views.ModaViewSet)
router.register('moda-members', views.ModaMembersViewSet)
router.register('moda-member-contacts', views.ModaMemberContactViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('moda/backnforth/<str:moda_code>/messages/', 
         ModaBackNForthChatViewSet.as_view({
             'get': 'list', 
             'post': 'create'
         }), 
         name='moda-backnforth-messages'),
    path('moda/backnforth/<str:moda_code>/messages/<int:pk>/', 
         ModaBackNForthChatViewSet.as_view({
             'get': 'retrieve',
             'put': 'update', 
             'patch': 'partial_update',
             'delete': 'destroy'
         }), 
         name='moda-backnforth-message-detail'),
    path('moda/backnforth/<str:moda_code>/messages/search/', 
         ModaBackNForthChatViewSet.as_view({'get': 'search'}), 
         name='moda-backnforth-search'),
    path('moda/backnforth/<str:moda_code>/statistics/', 
         ModaBackNForthChatViewSet.as_view({'get': 'statistics'}), 
         name='moda-backnforth-statistics'),
    path('moda/backnforth/<str:moda_code>/members/', 
         ModaBackNForthChatViewSet.as_view({'get': 'members_online'}), 
         name='moda-backnforth-members'),
]