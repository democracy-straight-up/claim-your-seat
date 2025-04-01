from rest_framework import serializers
from api import models as apiModels


class StatusItemsSerializer(serializers.ModelSerializer):
    class Meta: 
        model= apiModels.StatusItems
        fields = "__all__"
