from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),       # Páginas estáticas
    path('usuarios/', include('usuarios.urls')), # <-- Esta línea es crucial
    path('actividades/', include('actividades.urls')),
]