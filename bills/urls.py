from rest_framework import routers
from django.urls import path, include
from bills import views as billViews


router = routers.DefaultRouter()

# the bills endpoints (get list, update via patch or put, delete methods on each bill) is being registered.
router.register('bills', billViews.BillViewSet)
router.register('bill-vote', billViews.BillVoteViewSet)
router.register('bill-user-notes', billViews.BillUserNotesViewSet)
router.register('bill-first-del-notes', billViews.BillFirstDelNotesViewSet)
router.register('bill-second-del-notes', billViews.BillSecondDelNotesViewSet)
router.register('bill-moda-notes', billViews.BillModaNotesViewSet)
router.register('bill-holc-notes', billViews.BillHolcNotesViewSet)
router.register('bill-house-rep-notes', billViews.BillHouseRepNotesViewSet)

urlpatterns = [
    path('', include(router.urls)),
]