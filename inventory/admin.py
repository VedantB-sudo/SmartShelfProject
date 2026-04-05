from django.contrib import admin
from .models import Product

admin.site.register(Product)

from django.contrib import admin

# Customizing the Admin Portal branding
admin.site.site_header = "SmartShelf Management System"
admin.site.site_title = "SmartShelf Admin"
admin.site.index_title = "Welcome to the SmartShelf Inventory Controller"