from rest_framework import serializers
from holc import models as holcModels
from api.serializers import DistrictsSerializer, UserSerializer

class HolcSerializer(serializers.ModelSerializer):
    district = DistrictsSerializer()
    is_active = serializers.ReadOnlyField()
    member_count = serializers.ReadOnlyField()

    class Meta:
        model = holcModels.HolcModel
        fields = "__all__"

class HolcMembersSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    holc = HolcSerializer()
    vote_ins = serializers.StringRelatedField(many=True)
    vote_outs = serializers.StringRelatedField(many=True)
    put_forward = serializers.StringRelatedField(many=True)
    count_vote_in = serializers.StringRelatedField()
    count_vote_out = serializers.StringRelatedField()
    count_put_forward = serializers.StringRelatedField()
    class Meta:
        model = holcModels.HolcMembers
        fields = ["id","user","holc","is_delegate","is_member", "joined_at","updated_at",
                  "vote_outs","vote_ins", "put_forward","count_put_forward", "count_vote_out", "count_vote_in"]


class VoteOutHolcMemberSerializer(serializers.ModelSerializer):
    class Meta: 
        model= holcModels.VoteOutHolcMember
        fields = "__all__"

class VoteInHolcMemberSerializer(serializers.ModelSerializer):
    class Meta: 
        model = holcModels.VoteInHolcMember
        fields = "__all__"

class PutForwardHolcMemberSerializer(serializers.ModelSerializer):
    class Meta: 
        model = holcModels.PutForwardHolcMember
        fields = "__all__"
