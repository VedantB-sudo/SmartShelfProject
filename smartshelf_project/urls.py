from django.contrib import admin
from django.urls import path
from inventory import views
from django.contrib.auth import views as auth_views
from inventory import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('custom-admin/', views.admin_dashboard, name='custom_admin'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('login/', auth_views.LoginView.as_view(template_name='inventory/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', auth_views.LoginView.as_view(template_name='inventory/login.html')),
    path('product/add/', views.add_product, name='add_product'),
    path('delete/<int:pk>/', views.delete_product, name='delete_product'),
    path('product/edit/<int:pk>/', views.update_product, name='update_product'),
    path('register/', views.register_view, name='register'),
    path('generate-report/', views.generate_inventory_report, name='generate_inventory_report'),
]

from django.conf import settings
from django.conf.urls.static import static
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)