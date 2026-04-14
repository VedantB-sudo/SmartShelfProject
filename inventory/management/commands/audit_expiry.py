from django.core.management.base import BaseCommand
from inventory.models import Product
from inventory.services import aws_manager
from dateutil import parser
from datetime import date

class Command(BaseCommand):
    help = 'Scans DynamoDB for products nearing their expiry date and sends SNS alerts.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting SmartShelf Inventory Audit..."))
        
        products = list(Product.scan())
        alert_count = 0
        
        for product in products:
            if not product.expiry_date or product.expiry_date == "Unknown":
                continue
                
            try:
                expiry_dt = parser.parse(product.expiry_date).date()
                days_left = (expiry_dt - date.today()).days
                
                # We trigger alerts for anything within the 3-day window
                if 0 <= days_left <= 3:
                    self.stdout.write(f"Alert: {product.name} expires in {days_left} days.")
                    
                    subject = f"⏳ SmartShelf Audit: {product.name} is about to perish"
                    message = (
                        f"AUDIT ALERT: NEAR EXPIRY\n"
                        f"--------------------------\n"
                        f"Product: {product.name}\n"
                        f"Expiry Date: {product.expiry_date}\n"
                        f"Days Remaining: {days_left}\n\n"
                        f"Shelf Location: {getattr(product, 'shelf_number', 'N/A')}\n"
                        f"Current Quantity: {product.quantity}\n"
                    )
                    aws_manager.send_sns_alert(subject, message)
                    alert_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Fail: {product.name} - {e}"))

        self.stdout.write(self.style.SUCCESS(f"Audit Complete. {alert_count} alerts dispatched."))
