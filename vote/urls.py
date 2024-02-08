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

    path('pod-create',voteViews.CreatePod, name='createPod'),
    path('pod-join',voteViews.joinPod, name='joinPod'),
    path('pod/<int:pk>/', voteViews.HouseKeepingPod.as_view(), name='pod'),

    path('pod-vote-in', voteViews.podVoteIN, name="pod_vote_in"),
    path('pod-vote-out', voteViews.podVoteOUT, name="pod_vote_out"),
    path('pod-remove-member', voteViews.removePodMember, name="removePodMember"),
    path('pod-put-farward', voteViews.putFarward, name="putFarward"),
    path('pod-members/<int:pk>', voteViews.Pod_members.as_view(), name="podMember"),
    path('pod-remove/<int:pk>', voteViews.Delete_POD.as_view(), name="podRemove"),

    path('podmembercontact', voteViews.PodMemberContactAPIView.as_view(), name='podmembercontact-api'),

]
