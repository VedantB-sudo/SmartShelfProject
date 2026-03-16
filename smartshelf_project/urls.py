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
    path('scan/<int:pk>/', views.scan_product_date, name='scan_product'),
    path('scan/<int:pk>/', views.scan_product_date, name='scan_product_date'),
    path('delete/<int:pk>/', views.delete_product, name='delete_product'),
    path('', auth_views.LoginView.as_view(template_name='inventory/login.html')),
    path('product/add/', views.add_product, name='add_product'),
    path('product/edit/<int:pk>/', views.update_product, name='update_product'),
    path('success/', views.success_page, name='success_page'),
    path('register/', views.register_view, name='register'),
    path('user/reset/<int:user_id>/', views.reset_user_password, name='reset_user_password'),
    path('user/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('generate-report/', views.generate_inventory_report, name='generate_inventory_report'),
]

from django.conf import settings
from django.conf.urls.static import static
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)