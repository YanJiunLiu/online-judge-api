from rest_framework import viewsets, mixins
from l1m import serializers
from rest_framework import status
from rest_framework.response import Response


# Create your views here.
class RAGViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = serializers.RAGSerializer

    def create(self, request, *args, **kwargs):
        print(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)