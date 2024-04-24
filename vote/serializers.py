from rest_framework import serializers
from .models import GroupMember, GroupMemberContact


class CircleMemberContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMemberContact
        fields = ['email', 'phone']

    def create(self, validated_data):
        user = self.context['request'].user

        try:
            circle_member = GroupMember.objects.get(user=user)
        except GroupMember.DoesNotExist:
            # If CircleMember does not exist, raise a validation error
            raise serializers.ValidationError(
                "You are not a member of any circle. Please join a circle first.")

        validated_data['member'] = circle_member
        validated_data['circle'] = circle_member.group
        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance.email = validated_data.get('email', instance.email)
        instance.phone = validated_data.get('phone', instance.phone)
        instance.save()
        return instance
