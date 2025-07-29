from rest_framework import routers
from django.urls import path, include
from holc import views


# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
# router.register('', views.HelloWorldView)
# router.register('moda-members', views.ModaMembersViewSet)

urlpatterns = [
    path('hello/', views.HelloWorldView.as_view(), name='hello-world'),
    path('', include(router.urls)),
    ]