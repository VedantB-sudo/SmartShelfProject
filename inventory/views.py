import os
import sys
import re
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.db.models import Sum, F
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.http import HttpResponse

# Internal Project Imports
from .models import Product
from .forms import ProductForm, UserRegistrationForm
from .services import aws_manager
from .cloud_utils import SmartCloudManager # Your Custom Library
from reportlab.pdfgen import canvas

# 1. AUTHENTICATION: Dynamic Redirection
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect('custom_admin' if user.is_staff else 'dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'inventory/login.html', {'form': form})

# 2. DASHBOARD: Integrated with Custom Library for Telemetry
@login_required
def dashboard(request):
    query = request.GET.get('search')
    stock_filter = request.GET.get('filter') 
    products = Product.objects.all()

    if query:
        products = products.filter(name__icontains=query)
    if stock_filter == 'low_stock':
        products = products.filter(quantity__lt=5)

    # Use the Custom Library to fetch AI Insights
    total_items = products.count()
    low_stock_count = products.filter(quantity__lt=5).count()
    inventory_summary = f"Items: {total_items}. Low Stock: {low_stock_count}."
    ai_advice = aws_manager.get_inventory_advice(inventory_summary)
    
    context = {
        'products': products,
        'ai_advice': ai_advice,
        'total_items': total_items,
        'low_stock_count': low_stock_count,
    }
    return render(request, 'inventory/dashboard.html', context)

# 3. ADVANCED FEATURE: AI Document Extraction via Custom Library
@login_required
def scan_product_date(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if not product.image:
        messages.error(request, "No image found for scanning.")
        return redirect('dashboard')

    # IMPLEMENTATION: Using the Custom Library (SmartCloudManager)
    # This demonstrates the 'Context Manager' advanced construct.
    try:
        with SmartCloudManager() as cloud:
            # We pass the S3 bucket and the image path stored in the model
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            image_key = str(product.image)
            
            # Use library method for extraction
            extracted_data = cloud.extract_inventory_data(bucket_name, image_key)
            
            # Logic to update the model based on library output
            if extracted_data and 'expiry_date' in extracted_data:
                product.expiry_date = extracted_data['expiry_date']
                product.save()
                messages.success(request, f"Library successfully updated expiry: {product.expiry_date}")
            else:
                messages.info(request, "Library processed image but found no date patterns.")
                
    except Exception as e:
        messages.error(request, f"Library Error: {str(e)}")
        
    return redirect('custom_admin' if request.user.is_staff else 'dashboard')

# 4. PRODUCT MANAGEMENT: With Automated Alerts
@login_required
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            new_product = form.save()
            
            # Trigger Library-based Telemetry Update & Alerts
            if new_product.quantity < 5:
                with SmartCloudManager() as cloud:
                    # Update DynamoDB Telemetry and send SES Alert
                    cloud.update_stock_telemetry("InventoryLog", str(new_product.id), new_product.quantity)
                    aws_manager.send_low_stock_notification(new_product.name, new_product.quantity)
            
            return redirect('custom_admin' if request.user.is_staff else 'dashboard')
    else:
        form = ProductForm()
    return render(request, 'inventory/product_form.html', {'form': form, 'title': 'Add Product'})

# 5. REPORTING: PDF Generation
def generate_inventory_report(request):
    products = Product.objects.all()
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="inventory_report.pdf"'
    
    p = canvas.Canvas(response)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, "SmartShelf Inventory Report")
    
    y = 750
    for item in products:
        p.drawString(100, y, f"{item.name} - Qty: {item.quantity}")
        y -= 20
        if y < 50:
            p.showPage()
            y = 800
    
    p.showPage()
    p.save()
    return response

# Standard Admin Function
@user_passes_test(lambda u: u.is_staff)
def admin_dashboard(request):
    context = {
        'products': Product.objects.all(),
        'all_users': User.objects.all(),
    }
    return render(request, 'inventory/admin_dashboard.html', context)