from rest_framework import serializers
from api import models as apiModels
from api.serializers import DistrictsSerializer, UserSerializer

class SecDelSerializer(serializers.ModelSerializer):
    district = DistrictsSerializer()
    is_active= serializers.ReadOnlyField()
    class Meta:
        model = apiModels.SecDelModel
        fields = "__all__"

class SecDelMembersSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    sec_del = SecDelSerializer()
    vote_outs = serializers.StringRelatedField(many=True)
    put_farward = serializers.StringRelatedField(many=True)
    class Meta:
        model = apiModels.SecDelMembers
        fields = ["id","user","sec_del", "vote_outs","put_farward","is_delegate","is_member","joined_at","updated_at","vote_in_count","vote_out_count"]


class VoteOutSecDelMemberSerializer(serializers.ModelSerializer):
    class Meta: 
        model= apiModels.VoteOutSecDelMember
        fields = "__all__"