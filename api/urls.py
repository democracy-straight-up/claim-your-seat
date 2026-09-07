from rest_framework import routers
from django.urls import path, include
from api import views as apiViews
from api import sec_del_view
from api import status_messages
from api import backnforth_views

# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register('districts', apiViews.DistrictsViewSet)
router.register('user', apiViews.UserPageView)
router.register('voter-page', apiViews.VoterPageView)
router.register('circle', apiViews.CircleList)
router.register('get-circle', apiViews.CircleViewSet)

# Contact routes for different member types
router.register('circle-member-contacts', apiViews.GroupMemberContactViewSet, basename='groupmembercontact')
router.register('sec-del-member-contacts', sec_del_view.SecDelContactInfoViewSet, basename='secdelmembercontact')

# second delegate routes:
router.register('second-delegate', sec_del_view.SecDelViewSet)
router.register('second-delegate-members', sec_del_view.SecDelMembersViewSet)

from rest_framework_simplejwt.views import (TokenObtainPairView,TokenRefreshView,TokenVerifyView,)   # TokenVerifyView added by siva

urlpatterns = [
    path('', include(router.urls)),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),   # added by siva
    path('register/', apiViews.RegisterView.as_view(), name='auth_register'),
    path('activate/<uidb64>/<token>/',apiViews.activate, name='activate'),
    path('reset-password/', apiViews.PasswordResetRequestView.as_view(), name='reset_password'),
    path('reset-password-confirm/', apiViews.PasswordResetConfirmView.as_view(), name='reset_password_confirm'),
    path('login/', apiViews.LoginPageView.as_view()),
    path('create-circle/', apiViews.CreateCIRCLE.as_view()),
    path('house-keeping/', apiViews.HouseKeeping.as_view()),
    path('join-circle/', apiViews.JoinCIRCLE.as_view()),
    path('userinfo/', apiViews.UserView.as_view()),
    path('account-key/', apiViews.AccountKeyView.as_view()),
    path('circle-key/<str:circle_code>/', apiViews.CircleKeyView.as_view()),
    path('circle-credential/<str:circle_code>/', apiViews.CircleCredentialView.as_view()),
    path('circle-desolve/', apiViews.DesolveCircle.as_view()),
    path('circlemember/', apiViews.CircleMem.as_view()),
    path('circle-vote-in-list/',apiViews.CircleMemeber_voteIn.as_view()),
    path('circle-vote-out-list/',apiViews.CircleMemeber_voteOut.as_view()),
    path('circle-put-forward-list/',apiViews.CircleMemeber_putforward.as_view()),
    path('status/circle/',apiViews.CircleStatus.as_view()),
    path('get-username/', apiViews.UsernameRequestView.as_view(), name='get_username'),
    path('get-status-messages/', status_messages.ItemsViewSet.as_view({'get': 'list'})),
    path('chain-of-delegation/', apiViews.ChainOfDelegation.as_view()),
    
    # BackNForth Chat API endpoints
    path('backnforth/<str:sec_del_code>/messages/', backnforth_views.BackNForthChatViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='backnforth-chat-list'),
    path('backnforth/<str:sec_del_code>/messages/<int:pk>/', backnforth_views.BackNForthChatViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='backnforth-chat-detail'),
    path('backnforth/<str:sec_del_code>/search/', backnforth_views.BackNForthChatViewSet.as_view({
        'get': 'search'
    }), name='backnforth-chat-search'),
    path('backnforth/<str:sec_del_code>/statistics/', backnforth_views.BackNForthChatViewSet.as_view({
        'get': 'statistics'
    }), name='backnforth-chat-statistics'),
    path('backnforth/<str:sec_del_code>/members/', backnforth_views.BackNForthChatViewSet.as_view({
        'get': 'members_online'
    }), name='backnforth-chat-members'),
]