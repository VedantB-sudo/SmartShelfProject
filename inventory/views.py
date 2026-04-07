import os
import sys
import re
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.db.models import Sum, F
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.http import HttpResponse

# Corrected library imports based on your root-level file structur
from freshness_lib.checker import FreshnessAuditor
from Nimmu.cloud_utils import SmartCloudManager 

# Internal Project Imports
from .models import Product
from .forms import ProductForm, UserRegistrationForm
from .services import aws_manager
from reportlab.pdfgen import canvas

# 1. USER & AUTHENTICATION MANAGEMENT
def register_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, "Registration successful.")
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()
    return render(request, 'inventory/register.html', {'form': form})

@user_passes_test(lambda u: u.is_staff)
def reset_user_password(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.set_password('Temporary123!')
    user.save()
    messages.success(request, f"Password for {user.username} reset to 'Temporary123!'.")
    return redirect('custom_admin')

@user_passes_test(lambda u: u.is_staff)
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if not user.is_superuser:
        user.delete()
        messages.success(request, "User deleted successfully.")
    else:
        messages.error(request, "Cannot delete a superuser.")
    return redirect('custom_admin')

# 2. DASHBOARD
@login_required
def dashboard(request):
    query = request.GET.get('search')
    stock_filter = request.GET.get('filter') 
    products = Product.objects.all()

    if query:
        products = products.filter(name__icontains=query)
    if stock_filter == 'low_stock':
        products = products.filter(quantity__lt=5)

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

# 3. ADVANCED FEATURE: AI Document Extraction
@login_required
def scan_product_date(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if not product.image:
        messages.error(request, "No image found for scanning.")
        return redirect('dashboard')

    try:
        with SmartCloudManager() as cloud:
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            image_key = str(product.image)
            extracted_data = cloud.extract_inventory_data(bucket_name, image_key)
            
            if extracted_data and 'expiry_date' in extracted_data:
                product.expiry_date = extracted_data['expiry_date']
                product.save()
                messages.success(request, f"Successfully updated expiry: {product.expiry_date}")
            else:
                messages.info(request, "Processed image but found no date patterns.")
                
    except Exception as e:
        messages.error(request, f"Library Error: {str(e)}")
        
    return redirect('custom_admin' if request.user.is_staff else 'dashboard')

# 4. PRODUCT MANAGEMENT: Add, Update, and Delete
@login_required
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            # Manually initialize the PynamoDB model
            new_product = Product(
                name=form.cleaned_data['name'],
                category=form.cleaned_data['category'],
                quantity=form.cleaned_data['quantity'],
                price=float(form.cleaned_data['price']),
                expiry_date=str(form.cleaned_data['expiry_date'])
            )
            new_product.save()
            return redirect('dashboard')
    else:
        form = ProductForm()
    return render(request, 'inventory/add_product.html', {'form': form})

@login_required
def update_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated successfully.")
            return redirect('dashboard')
    else:
        form = ProductForm(instance=product)
    return render(request, 'inventory/product_form.html', {'form': form, 'title': 'Update Product'})

@login_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        messages.success(request, "Product deleted successfully.")
        return redirect('dashboard')
    return render(request, 'inventory/product_confirm_delete.html', {'product': product})

# 5. NAVIGATION & PAGES
@login_required
def success_page(request):
    return render(request, 'inventory/success.html')

# 6. REPORTING
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

# 7. ADMIN DASHBOARD
@user_passes_test(lambda u: u.is_staff)
def admin_dashboard(request):
    products = Product.objects.all()
    for item in products:
        auditor = FreshnessAuditor(item.name, item.category)
    context = {
        'products': products,
        'all_users': User.objects.all(),
    }
    return render(request, 'inventory/admin_dashboard.html', context)