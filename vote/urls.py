from django.urls import path
from django.views.generic import TemplateView
from vote import views as voteViews

urlpatterns = [
    path('', TemplateView.as_view(template_name='vote/index.html'), name='home'),
    path('confirm', TemplateView.as_view(template_name='vote/signUpConfirm.html'), name='test'),
    path('claim-your-seat',voteViews.ClaimYourSeat, name="ClaimYourSeat"),
    path('enter-the-floor',voteViews.EnterTheFloor, name="EnterTheFloor"),
    path('activate/<uidb64>/<token>/',voteViews.activate, name='activate'),
    path('logout',voteViews.userLogout, name='logout'),
    # the home page of user
    path('home',voteViews.voterPage, name='voterPage'),

    path('circle-create',voteViews.CreateCircle, name='createCircle'),
    path('circle-join',voteViews.joinCircle, name='joinCircle'),
    path('circle/<int:pk>/', voteViews.HouseKeepingCircle.as_view(), name='circle'),

    path('circle-vote-in', voteViews.circleVoteIN, name="circle_vote_in"),
    path('circle-vote-out', voteViews.circleVoteOUT, name="circle_vote_out"),
    path('circle-remove-member', voteViews.removeCircleMember, name="removeCircleMember"),
    path('circle-put-forward', voteViews.putForward, name="putForward"),
    path('circle-members/<int:pk>', voteViews.Circle_members.as_view(), name="circleMember"),
    path('circle-remove/<int:pk>', voteViews.Delete_CIRCLE.as_view(), name="circleRemove"),

    path('circlemembercontact', voteViews.CircleMemberContactAPIView.as_view(), name='circlemembercontact-api'),

]
