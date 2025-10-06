from rest_framework import serializers
from holc import models as holcModels
from api.serializers import DistrictsSerializer, UserSerializer

# Import User_Serializer from api.serializers for consistent user data
try:
    from api.serializers import User_Serializer
except ImportError:
    User_Serializer = UserSerializer

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
    # vote_ins = serializers.StringRelatedField(many=True)
    # vote_outs = serializers.StringRelatedField(many=True)
    # put_forward = serializers.StringRelatedField(many=True)
    # count_vote_in = serializers.StringRelatedField()
    # count_vote_out = serializers.StringRelatedField()
    # count_put_forward = serializers.StringRelatedField()
    class Meta:
        model = holcModels.HolcMembers
        fields = ["id","user","holc","is_delegate","is_member", "joined_at","updated_at" ]


# class VoteOutHolcMemberSerializer(serializers.ModelSerializer):
#     class Meta: 
#         model= holcModels.VoteOutHolcMember
#         fields = "__all__"

# class VoteInHolcMemberSerializer(serializers.ModelSerializer):
#     class Meta: 
#         model = holcModels.VoteInHolcMember
#         fields = "__all__"

class PutForwardHolcMemberSerializer(serializers.ModelSerializer):
    class Meta: 
        model = holcModels.PutForwardHolcMember
        fields = "__all__"


class HolcMemberContactSerializer(serializers.ModelSerializer):
    member = HolcMembersSerializer(read_only=True)
    holc = HolcSerializer(read_only=True)
    
    class Meta:
        model = holcModels.HolcMemberContact
        fields = ["id", "member", "holc", "legal_name", "contact_rules", 
                 "address", "contact", "phone", "email", "created_at", "updated_at"]


class HolcBackNForthChatSerializer(serializers.ModelSerializer):
    sender = User_Serializer(read_only=True)
    sender_name = serializers.CharField(source='sender.users.legalName', read_only=True)
    reply_to_message = serializers.SerializerMethodField()
    
    class Meta:
        model = holcModels.HolcBackNForthChat
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


class HolcBackNForthChatCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = holcModels.HolcBackNForthChat
        fields = ['message', 'reply_to']
    
    def create(self, validated_data):
        request = self.context['request']
        holc_code = self.context['holc_code']
        
        try:
            holc = holcModels.HolcModel.objects.get(code=holc_code)
        except holcModels.HolcModel.DoesNotExist:
            raise serializers.ValidationError("HoLC not found")
        
        # Verify user is a member
        if not holcModels.HolcMembers.objects.filter(
            user=request.user,
            holc=holc,
            is_member=True
        ).exists():
            raise serializers.ValidationError("You must be a HoLC member to send messages")
        
        validated_data['sender'] = request.user
        validated_data['holc'] = holc
        
        return super().create(validated_data)
