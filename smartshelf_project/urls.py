from django.contrib import admin
from django.urls import path
from inventory import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Admin & Dashboard
    path('admin/', admin.site.urls),
    path('custom-admin/', views.admin_dashboard, name='custom_admin'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='inventory/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('register/', views.register_view, name='register'),
    path('', auth_views.LoginView.as_view(template_name='inventory/login.html')),

    # Product Management (Updated to use <str:sku> for DynamoDB compatibility)
    path('product/add/', views.add_product, name='add_product'),
    path('product/edit/<str:sku>/', views.update_product, name='update_product'),
    path('product/delete/<str:sku>/', views.delete_product, name='delete_product'),

    # Reporting
    path('generate-report/', views.generate_inventory_report, name='generate_inventory_report'),
    path('admin/reset-password/<int:user_id>/', views.reset_user_password, name='reset_user_password'),
    path('admin/delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
]

# Static/Media files configuration
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)