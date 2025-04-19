from rest_framework import serializers
from moda import models as modaModels
from api.serializers import DistrictsSerializer, UserSerializer

class SecDelSerializer(serializers.ModelSerializer):
    district = DistrictsSerializer()
    is_active = serializers.ReadOnlyField()
    member_count = serializers.ReadOnlyField()

    class Meta:
        model = modaModels.ModaModel
        fields = "__all__"

class SecDelMembersSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    sec_del = SecDelSerializer()
    # vote_ins = serializers.StringRelatedField(many=True)
    # vote_outs = serializers.StringRelatedField(many=True)
    # put_farward = serializers.StringRelatedField(many=True)
    # count_vote_in = serializers.StringRelatedField()
    # count_vote_out = serializers.StringRelatedField()
    # count_put_forward = serializers.StringRelatedField()
    class Meta:
        model = modaModels.ModaMembers
        fields = ["id","user","moda","is_delegate","is_member", "joined_at","updated_at"]
