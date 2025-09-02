from rest_framework import serializers


class RAGSerializer(serializers.Serializer):
    response = serializers.CharField(required=False)

    def create(self, validated_data):
        return []

    def to_representation(self, instance):
        print(instance)
        return super().to_representation(instance=instance)