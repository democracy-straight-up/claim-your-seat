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


class DistrictCouncilBackNForthSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    sender_name = serializers.CharField(source='sender.users.legalName', read_only=True)
    reply_to_message = serializers.SerializerMethodField()
    
    class Meta:
        model = repModels.DistrictCouncilBackNForth
        fields = [
            'id', 'message', 'sender', 'sender_name', 'timestamp', 
            'is_edited', 'edited_at', 'reply_to', 'reply_to_message'
        ]
        read_only_fields = ['id', 'timestamp', 'sender', 'is_edited', 'edited_at']
    
    def get_reply_to_message(self, obj):
        if obj.reply_to:
            return {
                'id': obj.reply_to.id,
                'message': obj.reply_to.message[:100] + '...' if len(obj.reply_to.message) > 100 else obj.reply_to.message,
                'sender': obj.reply_to.sender.username,
                'sender_name': getattr(obj.reply_to.sender.users, 'legalName', obj.reply_to.sender.username)
            }
        return None


class DistrictCouncilBackNForthCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = repModels.DistrictCouncilBackNForth
        fields = ['message', 'reply_to']
    
    def create(self, validated_data):
        request = self.context['request']
        district_council_code = self.context['district_council_code']
        
        try:
            district_council = repModels.DistrictCouncil.objects.get(code=district_council_code)
        except repModels.DistrictCouncil.DoesNotExist:
            raise serializers.ValidationError("District Council not found")
        
        # Verify user is a member
        if not repModels.DistrictCouncilMembers.objects.filter(
            user=request.user,
            district_council=district_council,
            is_member=True
        ).exists():
            raise serializers.ValidationError("You must be a District Council member to send messages")
        
        validated_data['sender'] = request.user
        validated_data['district_council'] = district_council
        
        return super().create(validated_data)
