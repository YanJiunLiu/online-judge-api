from django.db import models


# Create your models here.
class RAG(models.Model):
    response = models.CharField(max_length=512, null=False)