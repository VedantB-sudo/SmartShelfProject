import os
import sys
import uuid  # Required to generate the missing 'sku' key
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

# 2. DASHBOARD
@login_required
def dashboard(request):
    query = request.GET.get('search')
    stock_filter = request.GET.get('filter') 
    
    # PynamoDB uses .scan()
    all_products = list(Product.scan())

    if query:
        all_products = [p for p in all_products if p.name and query.lower() in p.name.lower()]
    
    if stock_filter == 'low_stock':
        all_products = [p for p in all_products if (p.quantity or 0) < 5]

    total_items = len(all_products)
    low_stock_count = len([p for p in all_products if (p.quantity or 0) < 5])
    
    inventory_summary = f"Items: {total_items}. Low Stock: {low_stock_count}."
    ai_advice = aws_manager.get_inventory_advice(inventory_summary)
    
    context = {
        'products': all_products,
        'ai_advice': ai_advice,
        'total_items': total_items,
        'low_stock_count': low_stock_count,
    }
    return render(request, 'inventory/dashboard.html', context)

# 3. ADD PRODUCT (Fixed for DynamoDB SKU error)
@login_required
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                expiry_date = form.cleaned_data.get('expiry_date')
                image_url = None

                if 'image' in request.FILES:
                    image_file = request.FILES['image']
                    image_bytes = image_file.read()

                    from django.core.files.storage import default_storage
                    unique_filename = f"products/{uuid.uuid4()}_{image_file.name}"
                    
                    # In python string image_file.seek(0) to reset the pointer after read()
                    image_file.seek(0)
                    saved_path = default_storage.save(unique_filename, image_file)
                    image_url = default_storage.url(saved_path)

                    detected_date = aws_manager.get_product_expiry_from_image(image_bytes)
                    if detected_date:
                        expiry_date = detected_date
                        messages.info(request, f"Auto-detected Expiry Date via Textract: {detected_date}")

                final_expiry = str(expiry_date) if expiry_date else "Unknown"

                # We generate a unique SKU using uuid4 to satisfy DynamoDB requirements
                new_product = Product(
                    sku=str(uuid.uuid4()),  # CRITICAL FIX: Provides the missing Partition Key
                    name=form.cleaned_data['name'],
                    category=form.cleaned_data['category'],
                    quantity=int(form.cleaned_data['quantity']),
                    price=float(form.cleaned_data['price']),
                    expiry_date=final_expiry
                )
                if image_url:
                    new_product.image_url = image_url
                    
                new_product.save()
                
                # Dispatch SNS Notification for New Stock
                subject = f"SmartShelf: New Product Added ({new_product.name})"
                message = f"A new product has been registered.\nName: {new_product.name}\nQuantity: {new_product.quantity}"
                aws_manager.send_sns_alert(subject, message)
                
                messages.success(request, "Product added to DynamoDB!")
                return redirect('dashboard')
            except Exception as e:
                messages.error(request, f"DynamoDB Error: {str(e)}")
    else:
        form = ProductForm()
    return render(request, 'inventory/product_form.html', {'form': form, 'title': 'Add Product'})

# 4. UPDATE & DELETE (Updated to use SKU for lookup)
@login_required
def update_product(request, sku):
    try:
        product = Product.get(sku)
    except Product.DoesNotExist:
        messages.error(request, "Product not found.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            expiry_date = form.cleaned_data.get('expiry_date')
            
            if 'image' in request.FILES:
                image_file = request.FILES['image']
                image_bytes = image_file.read()
                
                from django.core.files.storage import default_storage
                import uuid
                unique_filename = f"products/{uuid.uuid4()}_{image_file.name}"
                image_file.seek(0)
                saved_path = default_storage.save(unique_filename, image_file)
                product.image_url = default_storage.url(saved_path)

                detected_date = aws_manager.get_product_expiry_from_image(image_bytes)
                if detected_date:
                    expiry_date = detected_date
                    messages.info(request, f"Auto-detected Expiry Date via Textract: {detected_date}")

            # In DynamoDB, the Hash Key (sku) cannot be changed.
            product.name = form.cleaned_data['name']
            product.category = form.cleaned_data['category']
            product.quantity = int(form.cleaned_data['quantity'])
            product.price = float(form.cleaned_data['price'])
            
            final_expiry = str(expiry_date) if expiry_date else "Unknown"
            product.expiry_date = final_expiry
            
            product.save()
            
            # Dispatch SNS Notification for Updated Stock
            subject = f"SmartShelf: Stock Updated ({product.name})"
            message = f"Stock has been updated for this item.\nName: {product.name}\nNew Quantity: {product.quantity}"
            aws_manager.send_sns_alert(subject, message)
            
            messages.success(request, "Product updated successfully.")
            return redirect('dashboard')
    else:
        initial_data = {
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
        product.delete()
        messages.success(request, "Product deleted from DynamoDB.")
        return redirect('dashboard')
    except Product.DoesNotExist:
        return redirect('dashboard')

# 5. REPORTS
def generate_inventory_report(request):
    products = list(Product.scan())
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="inventory_report.pdf"'
    
    p = canvas.Canvas(response)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, "SmartShelf Inventory Report")
    
    y = 750
    for item in products:
        # Safely handle missing SKU in old items during report generation
        item_sku = getattr(item, 'sku', 'N/A')
        p.drawString(100, y, f"SKU: {item_sku} | {item.name} - Qty: {item.quantity}")
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
        'all_users': User.objects.all(),
    }
    return render(request, 'inventory/admin_dashboard.html', context)
    
@login_required
def scan_product_date(request, pk):
    """
    Placeholder for the missing scan_product_date view 
    to resolve the AttributeError in urls.py.
    """
    product = get_object_or_404(Product, sku=pk)
    # Add your logic for scanning/freshness auditing here
    return render(request, 'inventory/dashboard.html')