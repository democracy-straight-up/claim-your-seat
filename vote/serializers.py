from rest_framework import serializers
from .models import PodMember, PodMemberContact


class PodMemberContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = PodMemberContact
        fields = ['email', 'phone']

    def create(self, validated_data):
        user = self.context['request'].user

        try:
            pod_member = PodMember.objects.get(user=user)
        except PodMember.DoesNotExist:
            # If PodMember does not exist, raise a validation error
            raise serializers.ValidationError(
                "You are not a member of any pod. Please join a pod first.")

        validated_data['member'] = pod_member
        validated_data['pod'] = pod_member.pod
        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance.email = validated_data.get('email', instance.email)
        instance.phone = validated_data.get('phone', instance.phone)
        instance.save()
        return instance
