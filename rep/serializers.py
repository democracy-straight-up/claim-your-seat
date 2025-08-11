from rest_framework import serializers
from rep import models as repModels
from api.serializers import DistrictsSerializer, UserSerializer

class DistrictCouncilSerializer(serializers.ModelSerializer):
    district = DistrictsSerializer()
    is_active = serializers.ReadOnlyField()
    member_count = serializers.ReadOnlyField()

    class Meta:
        model = repModels.DistrictCouncil
        fields = "__all__"

class DistrictCouncilMembersSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    district_council = DistrictCouncilSerializer()
    vote_ins = serializers.StringRelatedField(many=True)
    vote_outs = serializers.StringRelatedField(many=True)
    put_forward = serializers.StringRelatedField(many=True)
    count_vote_in = serializers.StringRelatedField()
    count_vote_out = serializers.StringRelatedField()
    count_put_forward = serializers.StringRelatedField()
    class Meta:
        model = repModels.DistrictCouncilMembers
        fields = ["id","user","district_council","is_delegate","is_member", "joined_at","updated_at",
                  "vote_outs","vote_ins", "put_forward","count_put_forward", "count_vote_out", "count_vote_in"]


class VoteOutDistrictCouncilMemberSerializer(serializers.ModelSerializer):
    class Meta: 
        model= repModels.VoteOutDistrictCouncilMember
        fields = "__all__"

class VoteInDistrictCouncilMemberSerializer(serializers.ModelSerializer):
    class Meta: 
        model = repModels.VoteInDistrictCouncilMember
        fields = "__all__"

class PutForwardDistrictCouncilMemberSerializer(serializers.ModelSerializer):
    class Meta: 
        model = repModels.PutForwardDistrictCouncilMember
        fields = "__all__"


class DistrictCouncilMemberContactSerializer(serializers.ModelSerializer):
    member = DistrictCouncilMembersSerializer(read_only=True)
    district_council = DistrictCouncilSerializer(read_only=True)
    
    class Meta:
        model = repModels.DistrictCouncilMemberContact
        fields = ["id", "member", "district_council", "legal_name", "contact_rules", 
                 "address", "contact", "phone", "email", "created_at", "updated_at"]
