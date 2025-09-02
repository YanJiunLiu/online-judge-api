from l1m import views
from django.urls import path
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

router = DefaultRouter()
router.register(r"RAG", views.RAGViewSet, basename="RAG")
urlpatterns = []
urlpatterns += router.urls
urlpatterns += [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]