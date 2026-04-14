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
import io
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
# Corrected library imports
from freshness_lib.checker import FreshnessAuditor
from Nimmu.cloud_utils import SmartCloudManager 

# Internal Project Imports
from .models import Product
from .forms import ProductForm, UserRegistrationForm
from .services import aws_manager

# PDF Generation Imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

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
                    expiry_date=final_expiry,
                    shelf_number=form.cleaned_data.get('shelf_number'),
                    is_perishable=form.cleaned_data.get('is_perishable', False),
                    current_temperature=form.cleaned_data.get('current_temperature'),
                    temp_threshold=form.cleaned_data.get('temp_threshold')
                )
                if image_url:
                    new_product.image_url = image_url
                    
                new_product.save()
                
                # Dispatch SNS Notification for New Stock
                subject = f"🆕 SmartShelf: New Product Added ({new_product.name})"
                message = (
                    f"NEW PRODUCT REGISTERED\n"
                    f"--------------------------\n"
                    f"Name: {new_product.name}\n"
                    f"Quantity: {new_product.quantity}\n"
                    f"Category: {new_product.category}\n"
                    f"Shelf Number: {new_product.shelf_number or 'N/A'}\n"
                )
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
            product.shelf_number = form.cleaned_data.get('shelf_number')
            product.is_perishable = form.cleaned_data.get('is_perishable', False)
            product.current_temperature = form.cleaned_data.get('current_temperature')
            product.temp_threshold = form.cleaned_data.get('temp_threshold')
            
            product.save()
            
            # Dispatch SNS Notification for Updated Stock
            subject = f"🔄 SmartShelf: Stock Updated ({product.name})"
            message = (
                f"INVENTORY UPDATE\n"
                f"--------------------------\n"
                f"Name: {product.name}\n"
                f"New Quantity: {product.quantity}\n"
                f"Price: €{float(product.price):.2f}\n"
            )
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
            'shelf_number': product.shelf_number,
            'is_perishable': product.is_perishable,
            'current_temperature': getattr(product, 'current_temperature', 20.0),
            'temp_threshold': getattr(product, 'temp_threshold', 15.0),
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
    
    # Use a BytesIO buffer to hold the PDF data in memory
    buffer = io.BytesIO()
    
    # Create the PDF document using the buffer instead of the response
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph("SmartShelf Inventory Summary Report", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # Subtitle
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subtitle = Paragraph(f"Generated on: {timestamp}", styles['Normal'])
    elements.append(subtitle)
    elements.append(Spacer(1, 24))
    
    # Table Data
    data = [["Product Name", "Category", "Shelf", "Expiry", "Price", "Qty"]]
    low_stock_rows = []
    
    for idx, item in enumerate(products):
        row = [
            item.name,
            item.category,
            getattr(item, 'shelf_number', 'N/A') or 'N/A',
            item.expiry_date,
            f"€{float(item.price):.2f}",
            str(item.quantity)
        ]
        data.append(row)
        if item.quantity < 5:
            low_stock_rows.append(idx + 1)
            
    # Table Styling
    table = Table(data, colWidths=[150, 100, 60, 80, 60, 40])
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ])
    
    for row_idx in low_stock_rows:
        style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.lightpink)
        style.add('TEXTCOLOR', (5, row_idx), (5, row_idx), colors.red)
        
    table.setStyle(style)
    elements.append(table)
    
    # Build the PDF into the buffer
    doc.build(elements)
    
    # --- NEW: Upload to S3 and Send SNS Alert ---
    buffer.seek(0)
    report_filename = f"reports/inventory_report_{uuid.uuid4().hex[:8]}.pdf"
    
    # Save the file to S3
    saved_path = default_storage.save(report_filename, ContentFile(buffer.read()))
    report_url = default_storage.url(saved_path)
    
    # Send SNS Notification with the link
    subject = "📊 SmartShelf: Inventory Report Generated"
    message = (
        f"A new inventory summary report has been generated.\n\n"
        f"You can download or view the PDF here:\n"
        f"{report_url}\n\n"
        f"Generated at: {timestamp}"
    )
    aws_manager.send_sns_alert(subject, message)
    
    # Return the PDF to the user's browser as before
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="inventory_report.pdf"'
    return response

# 6. ADMIN DASHBOARD
@user_passes_test(lambda u: u.is_staff)
def admin_dashboard(request):
    try:
        products = list(Product.scan())
        
        total_items = len(products)
        
        # Explicit type casting for safety against corrupted data
        total_stock = 0
        total_value = 0.0
        
        for p in products:
            qty = int(p.quantity) if p.quantity is not None else 0
            price = float(p.price) if p.price is not None else 0.0
            total_stock += qty
            total_value += (qty * price)
            
        low_stock_items = [p for p in products if (p.quantity or 0) < 5]
        
        # Format for the master table which expects 'obj' and 'status'
        product_list = []
        for p in products:
            product_list.append({
                'obj': p,
                'status': p.calculated_status
            })
        
        context = {
            'total_items': total_items,
            'total_stock': total_stock,
            'total_value': total_value,
            'low_stock_items': low_stock_items,
            'product_list': product_list,
            'all_users': User.objects.all(),
        }
        return render(request, 'inventory/admin_dashboard.html', context)
    except Exception as e:
        # Graceful fallback in case of catastrophic data corruption
        messages.error(request, f"System Oversight Error: {str(e)}")
        return redirect('dashboard')
    
@user_passes_test(lambda u: u.is_staff)
def reset_user_password(request, user_id):
    if request.method == 'POST':
        try:
            target_user = User.objects.get(id=user_id)
            new_password = request.POST.get('new_password')
            if new_password:
                target_user.set_password(new_password)
                target_user.save()
                messages.success(request, f"Password updated for {target_user.username}")
            else:
                messages.error(request, "Password cannot be empty.")
        except User.DoesNotExist:
            messages.error(request, "User not found.")
    return redirect('custom_admin')

@user_passes_test(lambda u: u.is_staff)
def delete_user(request, user_id):
    try:
        if request.user.id == user_id:
            messages.error(request, "You cannot delete your own admin account.")
        else:
            target_user = User.objects.get(id=user_id)
            username = target_user.username
            target_user.delete()
            messages.success(request, f"User '{username}' has been removed.")
    except User.DoesNotExist:
        messages.error(request, "User not found.")
    return redirect('custom_admin')

@login_required
def scan_product_date(request, pk):
    """
    Placeholder for the missing scan_product_date view 
    to resolve the AttributeError in urls.py.
    """
    product = get_object_or_404(Product, sku=pk)
    # Add your logic for scanning/freshness auditing here
    return render(request, 'inventory/dashboard.html')
    
@login_required
def manual_scan_expiry(request, sku):
    try:
        product = Product.get(sku)
        
        if not product.image_url:
            messages.warning(request, f"No image available to scan for {product.name}.")
            return redirect('dashboard')

        # 1. Download the image from S3
        import requests
        response = requests.get(product.image_url)
        if response.status_code != 200:
            messages.error(request, "Could not retrieve image from storage.")
            return redirect('dashboard')
            
        image_bytes = response.content

        # 2. Run Textract
        detected_date = aws_manager.get_product_expiry_from_image(image_bytes)
        
        if detected_date:
            product.expiry_date = detected_date
            product.save()
            messages.success(request, f"Successfully detected expiry date for {product.name}: {detected_date}")
        else:
            messages.error(request, f"Textract could not find a valid date in the image for {product.name}.")
            
    except Product.DoesNotExist:
        messages.error(request, "Product not found.")
    except Exception as e:
        messages.error(request, f"Scanning error: {str(e)}")
        
    return redirect('dashboard')