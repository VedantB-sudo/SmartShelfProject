import os
import sys
import re
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.db.models import Sum, F, Count
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Product
from .forms import ProductForm
from django.contrib.admin.views.decorators import staff_member_required
from .forms import UserRegistrationForm
from django.contrib.auth.models import User
from .services import aws_manager

# Technical Fix: Ensuring the custom library is in the Python Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from freshness_lib.checker import FreshnessAuditor
except (ImportError, ModuleNotFoundError):
    from freshness_lib.checker import FreshnessAuditor

# 1. LOGIN: Handled via dynamic redirection
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            if user.is_staff:
                return redirect('custom_admin')
            else:
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'inventory/login.html', {'form': form})

# 2. USER DASHBOARD: Statistics, Search, and Filtering
@login_required
def dashboard(request):
    query = request.GET.get('search')
    stock_filter = request.GET.get('filter') 
    
    products = Product.objects.all()

    # Apply search filter
    if query:
        products = products.filter(name__icontains=query)
    
    # Apply Stock Level filter
    if stock_filter == 'low_stock':
        products = products.filter(quantity__lt=5)

    # --- STATS CALCULATION (Global counts for the cards) ---
    all_products = Product.objects.all()
    total_value = all_products.aggregate(total=Sum(F('price') * F('quantity')))['total'] or 0
    total_items = all_products.count()
    low_stock_count = all_products.filter(quantity__lt=5).count()

    # AI Advice logic
    inventory_summary = f"Total products: {total_items}. Critical low stock items: {low_stock_count}."
    ai_advice = aws_manager.get_inventory_advice(inventory_summary)
    
    # Freshness Auditing logic for visible items
    for item in products:
        auditor = FreshnessAuditor(item.name, item.category)
        item.calculated_status = auditor.calculate_status(item.expiry_date)
        
    context = {
        'products': products,
        'ai_advice': ai_advice,
        'total_value': total_value,
        'total_items': total_items,
        'low_stock_count': low_stock_count,
        'current_filter': stock_filter,
    }
    return render(request, 'inventory/dashboard.html', context)

# 3. ADMIN DASHBOARD: Management Metrics
@user_passes_test(lambda u: u.is_staff)
def admin_dashboard(request):   
    products = Product.objects.all()
    all_users = User.objects.all().order_by('-date_joined')
    
    total_items = products.count()
    total_stock = products.aggregate(Sum('quantity'))['quantity__sum'] or 0
    total_value = products.aggregate(total=Sum(F('price') * F('quantity')))['total'] or 0
    
    for item in products:
        auditor = FreshnessAuditor(item.name, item.category)
        item.calculated_status = auditor.calculate_status(item.expiry_date)
    
    context = {
        'products': products,
        'all_users': all_users,
        'total_items': total_items,
        'total_stock': total_stock,
        'total_value': total_value,
    }
    return render(request, 'inventory/admin_dashboard.html', context)

@user_passes_test(lambda u: u.is_staff, login_url='login') 
def register_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Success: New account for '{user.username}' has been activated.") 
            return redirect('custom_admin') 
    else:
        form = UserRegistrationForm()
    return render(request, 'inventory/register.html', {'form': form})

# 4. PRODUCT MANAGEMENT: CRUD with SNS Alerts
@login_required
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            new_product = form.save() 
            if new_product.quantity < 5:
                aws_manager.send_low_stock_notification(new_product.name, new_product.quantity)
            return redirect('success_page')
    else:
        form = ProductForm()
    return render(request, 'inventory/product_form.html', {'form': form, 'title': 'Add New Product'})

@login_required
def update_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            updated_product = form.save()
            if updated_product.quantity < 5:
                aws_manager.send_low_stock_notification(updated_product.name, updated_product.quantity)
            return redirect('success_page')
    else:
        form = ProductForm(instance=product)
    return render(request, 'inventory/product_form.html', {'form': form, 'title': 'Update Product'})

@login_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    messages.success(request, "Product removed from the inventory.")
    return redirect('dashboard')

@login_required
def scan_product_date(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if not product.image:
        messages.error(request, "Error: No product image found to scan.")
        return redirect('dashboard')

    try:
        image_bytes = product.image.read()
        detected_lines = aws_manager.scan_product_label(image_bytes)
        full_text = " ".join(detected_lines)
        date_pattern = r'(\d{2}[/-]\d{2}[/-]\d{4})'
        found_dates = re.findall(date_pattern, full_text)

        if found_dates:
            product.expiry_date = datetime.strptime(found_dates[0].replace('-', '/'), '%d/%m/%Y').date()
            product.save()
            messages.success(request, f"AI updated expiry date to: {product.expiry_date}")
        else:
            messages.info(request, "AI Scan complete: No date patterns recognized on the label.")
    except Exception as e:
        messages.error(request, f"Cloud logic error: {str(e)}")
    return redirect('dashboard')

def success_page(request):
    return render(request, 'inventory/success.html')

@user_passes_test(lambda u: u.is_staff)
def reset_user_password(request, user_id):
    user_to_reset = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        new_pw = request.POST.get('new_password')
        if new_pw:
            user_to_reset.set_password(new_pw)
            user_to_reset.save()
            messages.success(request, f"Password for {user_to_reset.username} updated successfully!")
        else:
            messages.error(request, "Password cannot be empty.")
    return redirect('custom_admin')

@user_passes_test(lambda u: u.is_staff)
def delete_user(request, user_id):
    user_to_delete = get_object_or_404(User, id=user_id)
    if user_to_delete == request.user:
        messages.error(request, "Error: You cannot delete your own account.")
    else:
        username = user_to_delete.username
        user_to_delete.delete()
        messages.success(request, f"Account '{username}' has been purged from the system.")
    return redirect('custom_admin')

# 5. CLOUD OPERATIONS: Report Generation
def generate_inventory_report(request):
    products = Product.objects.all()
    inventory_data = [
        {
            'name': p.name, 
            'quantity': p.quantity, 
            'price': float(p.price), 
            'expiry': str(p.expiry_date)
        } for p in products
    ]
    
    # Passing data to the aws_manager service
    aws_manager.trigger_lambda_pdf(inventory_data)

    messages.success(request, "Success! The inventory report has been generated and uploaded to the cloud (Simulated).")
    return redirect('dashboard')