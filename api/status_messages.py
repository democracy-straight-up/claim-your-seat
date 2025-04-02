from rest_framework import serializers
from api import models as apiModels
from rest_framework import viewsets
from rest_framework.permissions import AllowAny

class StatusItemsSerializer(serializers.ModelSerializer):
    class Meta: 
        model= apiModels.StatusItems
        fields = "__all__"


class ItemsViewSet(viewsets.ModelViewSet):
    permission_classes = (AllowAny,)
    queryset = apiModels.StatusItems.objects.all()
    serializer_class = StatusItemsSerializer