from rest_framework import serializers
from moda import models as modaModels
from api.serializers import DistrictsSerializer, UserSerializer, User_Serializer

class ModaSerializer(serializers.ModelSerializer):
    district = DistrictsSerializer()
    is_active = serializers.ReadOnlyField()
    member_count = serializers.ReadOnlyField()

    class Meta:
        model = modaModels.ModaModel
        fields = "__all__"

class ModaMembersSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    moda = ModaSerializer()
    vote_ins = serializers.StringRelatedField(many=True)
    vote_outs = serializers.StringRelatedField(many=True)
    put_farward = serializers.StringRelatedField(many=True)
    count_vote_in = serializers.StringRelatedField()
    count_vote_out = serializers.StringRelatedField()
    count_put_forward = serializers.StringRelatedField()
    class Meta:
        model = modaModels.ModaMembers
        fields = ["id","user","moda","is_delegate","is_member", "joined_at","updated_at",
                  "vote_outs","vote_ins", "put_farward","count_put_forward", "count_vote_out", "count_vote_in"]


class VoteOutModaMemberSerializer(serializers.ModelSerializer):
    class Meta: 
        model= modaModels.VoteOutModaMember
        fields = "__all__"

class VoteInModaMemberSerializer(serializers.ModelSerializer):
    class Meta: 
        model = modaModels.VoteInModaMember
        fields = "__all__"

class PutFarwardModaMemberSerializer(serializers.ModelSerializer):
    class Meta: 
        model = modaModels.PutFarwardModaMember
        fields = "__all__"


class ModaMemberContactSerializer(serializers.ModelSerializer):
    member = ModaMembersSerializer(read_only=True)
    moda = ModaSerializer(read_only=True)
    
    class Meta:
        model = modaModels.ModaMemberContact
        fields = ["id", "member", "moda", "legal_name", "contact_rules", 
                 "address", "contact", "phone", "email", "created_at", "updated_at"]


class ModaBackNForthChatSerializer(serializers.ModelSerializer):
    sender = User_Serializer(read_only=True)
    sender_name = serializers.CharField(source='sender.users.legalName', read_only=True)
    reply_to_message = serializers.SerializerMethodField()
    
    class Meta:
        model = modaModels.ModaBackNForthChat
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


class ModaBackNForthChatCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = modaModels.ModaBackNForthChat
        fields = ['message', 'reply_to']
    
    def create(self, validated_data):
        request = self.context['request']
        moda_code = self.context['moda_code']
        
        try:
            moda = modaModels.ModaModel.objects.get(code=moda_code)
        except modaModels.ModaModel.DoesNotExist:
            raise serializers.ValidationError("S-Link not found")
        
        validated_data['sender'] = request.user
        validated_data['moda'] = moda
        
        return super().create(validated_data)
