from rest_framework import serializers
from api import models as apiModels
from api.serializers import DistrictsSerializer, User_Serializer, UserSerializer

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

class PutFarwardSecDelMemberSerializer(serializers.ModelSerializer):
    class Meta: 
        model = apiModels.PutFarwardSecDelMember
        fields = "__all__"


# Contact Serializers for each member
class SecDelMemberContactInfoSerializer(serializers.ModelSerializer):
    member = SecDelMembersSerializer(read_only=True)
    class Meta:
        model = apiModels.ContactInfo
        fields = ['id', 'member', 'sec_del', 'legal_name', 'contact_rules', 'address',
                  'contact', 'phone', 'email', 'created_at']
        read_only_fields = ['created_at',]


class BackNForthChatSerializer(serializers.ModelSerializer):
    sender = User_Serializer(read_only=True)
    sender_name = serializers.CharField(source='sender.users.legalName', read_only=True)
    reply_to_message = serializers.SerializerMethodField()
    
    class Meta:
        model = apiModels.BackNForthChat
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


class BackNForthChatCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = apiModels.BackNForthChat
        fields = ['message', 'reply_to']
    
    def create(self, validated_data):
        from api.models import SecDelModel  # Import only when needed
        request = self.context['request']
        sec_del_code = self.context['sec_del_code']
        
        try:
            sec_del = SecDelModel.objects.get(code=sec_del_code)
        except SecDelModel.DoesNotExist:
            raise serializers.ValidationError("F-Link not found")
        
        validated_data['sender'] = request.user
        validated_data['sec_del'] = sec_del
        
        return super().create(validated_data)