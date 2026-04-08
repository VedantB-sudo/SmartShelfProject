import os
import sys
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import HttpResponse

# Corrected library imports
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

# 2. DASHBOARD (Updated for PynamoDB Scan)
@login_required
def dashboard(request):
    query = request.GET.get('search')
    stock_filter = request.GET.get('filter') 
    
    # PynamoDB uses .scan() instead of .objects.all()
    all_products = list(Product.scan())

    # Manual filtering since PynamoDB scan filtering is complex for a student project
    if query:
        all_products = [p for p in all_products if query.lower() in p.name.lower()]
    
    if stock_filter == 'low_stock':
        all_products = [p for p in all_products if p.quantity < 5]

    total_items = len(all_products)
    low_stock_count = len([p for p in all_products if p.quantity < 5])
    
    inventory_summary = f"Items: {total_items}. Low Stock: {low_stock_count}."
    ai_advice = aws_manager.get_inventory_advice(inventory_summary)
    
    context = {
        'products': all_products,
        'ai_advice': ai_advice,
        'total_items': total_items,
        'low_stock_count': low_stock_count,
    }
    return render(request, 'inventory/dashboard.html', context)

# 3. ADD PRODUCT (Updated to use 'sku' and PynamoDB save)
@login_required
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            try:
                # Manually initialize the PynamoDB model using 'sku'
                new_product = Product(
                    sku=form.cleaned_data['sku'], # Ensure SKU is in your form
                    name=form.cleaned_data['name'],
                    category=form.cleaned_data['category'],
                    quantity=int(form.cleaned_data['quantity']),
                    price=float(form.cleaned_data['price']),
                    expiry_date=str(form.cleaned_data['expiry_date'])
                )
                new_product.save()
                messages.success(request, "Product added to DynamoDB!")
                return redirect('dashboard')
            except Exception as e:
                messages.error(request, f"DynamoDB Error: {str(e)}")
    else:
        form = ProductForm()
    return render(request, 'inventory/add_product.html', {'form': form})

# 4. UPDATE & DELETE (Updated for .get() using sku)
@login_required
def update_product(request, sku):
    try:
        product = Product.get(sku)
    except Product.DoesNotExist:
        messages.error(request, "Product not found.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product.name = form.cleaned_data['name']
            product.category = form.cleaned_data['category']
            product.quantity = int(form.cleaned_data['quantity'])
            product.price = float(form.cleaned_data['price'])
            product.expiry_date = str(form.cleaned_data['expiry_date'])
            product.save()
            messages.success(request, "Product updated successfully.")
            return redirect('dashboard')
    else:
        # Pre-fill form for PynamoDB object
        initial_data = {
            'sku': product.sku,
            'name': product.name,
            'category': product.category,
            'quantity': product.quantity,
            'price': product.price,
            'expiry_date': product.expiry_date,
        }
        form = ProductForm(initial=initial_data)
    
    return render(request, 'inventory/product_form.html', {'form': form, 'title': 'Update Product'})

@login_required
def delete_product(request, sku):
    try:
        product = Product.get(sku)
        if request.method == 'POST':
            product.delete()
            messages.success(request, "Product deleted from DynamoDB.")
            return redirect('dashboard')
    except Product.DoesNotExist:
        return redirect('dashboard')
        
    return render(request, 'inventory/product_confirm_delete.html', {'product': product})

# 5. REPORTING (Updated for PynamoDB)
def generate_inventory_report(request):
    products = list(Product.scan())
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="inventory_report.pdf"'
    
    p = canvas.Canvas(response)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, "SmartShelf Inventory Report")
    
    y = 750
    for item in products:
        p.drawString(100, y, f"SKU: {item.sku} | {item.name} - Qty: {item.quantity}")
        y -= 20
        if y < 50:
            p.showPage()
            y = 800
    p.showPage()
    p.save()
    return response

# 6. ADMIN DASHBOARD
@user_passes_test(lambda u: u.is_staff)
def admin_dashboard(request):
    products = list(Product.scan())
    context = {
        'products': products,
        'all_users': User.objects.all(), # Local Auth still uses SQLite
    }
    return render(request, 'inventory/admin_dashboard.html', context)