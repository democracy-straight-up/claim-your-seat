from rest_framework import serializers
from api import models as apiModels
from rest_framework import viewsets

class StatusItemsSerializer(serializers.ModelSerializer):
    class Meta: 
        model= apiModels.StatusItems
        fields = "__all__"


class ItemsViewSet(viewsets.ModelViewSet):
    queryset = apiModels.StatusItems.objects.all()
    serializer_class = StatusItemsSerializer