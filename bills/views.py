from django.core.cache import cache
from rest_framework.response import Response

from bills import models as billModels
from bills import serializers as billSerializers
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny


class CustomPagination(PageNumberPagination):
    """
    We are creating a custome pagination for Bill and BillVote Model
    to limit the query and more """
    page_size = 10  # Number of items per page
    page_size_query_param = 'page_size'  # Allows the client to override the page size
    max_page_size = 100  # Maximum page size to prevent abuse


class BillViewSet(viewsets.ModelViewSet):
    """endpoints for Bills
    1. adding a new Bill,
    2. updating a bill record,
    3. removing a record.
     It handles the followings:
      1. pagination: default paginating is 10 and max is 100
      and can be changed via url param named: page_size
      2. it list bills.
      3. updates via put and patch request method.
      4. removed a record via delete request method"""

    queryset = billModels.Bill.objects.all()
    serializer_class = billSerializers.BillSerializer
    pagination_class = CustomPagination
    permission_classes = [AllowAny]

    def list(self, request, *args, **kwargs):
        cache_key = 'bill_list'
        cache_time = 60 * 15  # 缓存时间，单位是秒
        data = cache.get(cache_key)

        if not data:
            response = super().list(request, *args, **kwargs)
            data = response.data
            cache.set(cache_key, data, cache_time)
        return Response(data)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        cache.delete('bill_list')
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        cache.delete('bill_list')
        return response

    def destroy(self, request, *args, **kwargs):
        response = super().destroy(request, *args, **kwargs)
        cache.delete('bill_list')
        return response


class BillVoteViewSet(viewsets.ModelViewSet):
    """We have bill vote view set in case that for sure there
    is going to be needed to have endpoints for
    1. adding a new vote,
    2. updating a vote record,
    3. removing a record.
     It handles the followings:
      1. pagination: default paginating is 10 and max is 100
      and can be changed via url param named: page_size
      2. it list the bill's votes.
      3. updates via put and patch request method.
      4. removed a record via delete request method"""
    queryset = billModels.BillVote.objects.all()
    serializer_class = billSerializers.BillVoteSerializer
    pagination_class = CustomPagination
    permission_classes = [AllowAny]
