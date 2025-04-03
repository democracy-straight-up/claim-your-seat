from rest_framework import serializers
from api import models as apiModels
from api.serializers import DistrictsSerializer, UserSerializer

class SecDelSerializer(serializers.ModelSerializer):
    district = DistrictsSerializer()
    is_active = serializers.ReadOnlyField()
    member_count = serializers.ReadOnlyField()

    class Meta:
        model = apiModels.SecDelModel
        fields = "__all__"

class SecDelMembersSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    sec_del = SecDelSerializer()
    vote_ins = serializers.StringRelatedField(many=True)
    vote_outs = serializers.StringRelatedField(many=True)
    put_farward = serializers.StringRelatedField(many=True)
    count_vote_in = serializers.StringRelatedField()
    count_vote_out = serializers.StringRelatedField()
    count_put_forward = serializers.StringRelatedField()
    class Meta:
        model = apiModels.SecDelMembers
        fields = ["id","user","sec_del", "vote_outs","vote_ins", "put_farward","is_delegate","is_member"
                  , "count_put_forward", "count_vote_out", "count_vote_in", "joined_at","updated_at"]

class VoteOutSecDelMemberSerializer(serializers.ModelSerializer):
    class Meta: 
        model= apiModels.VoteOutSecDelMember
        fields = "__all__"

class VoteInSecDelMemberSerializer(serializers.ModelSerializer):
    class Meta: 
        model = apiModels.VoteInSecDelMember
        fields = "__all__"