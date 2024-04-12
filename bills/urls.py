from rest_framework import routers
from django.urls import path, include
from bills import views as billViews


router = routers.DefaultRouter()

# the bills endpoints (get list, update via patch or put, delete methods on each bill) is being registered.
router.register('bills', billViews.BillViewSet)
router.register('bill-vote', billViews.BillVoteViewSet)


urlpatterns = [
    path('', include(router.urls)),
]