from django.db import models
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
import logging

# Set up logging to track email status in your console
logger = logging.getLogger(__name__)

class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    quantity = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    expiry_date = models.DateField()
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    last_audited = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def calculated_status(self):
        """Logic for the Dashboard status badges"""
        if self.quantity <= 2:
            return "Critical"
        elif self.quantity <= 5:
            return "Attention"
        return "Fresh"

    def send_ses_alert(self):
        """Handles the Amazon SES Email logic"""
        subject = f"⚠️ SmartShelf Alert: Low Stock on {self.name}"
        
        # Professional Email Body
        message = (
            f"INVENTORY ALERT\n"
            f"--------------------------\n"
            f"Product: {self.name}\n"
            f"Current Stock: {self.quantity}\n"
            f"Status: {self.calculated_status}\n"
            f"Category: {self.category}\n\n"
            f"Action Required: Please restock this item immediately via the dashboard."
        )
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.DEFAULT_FROM_EMAIL], # Sends to yourself/admin
                fail_silently=False,
            )
            logger.info(f"SES Alert sent for {self.name}")
        except Exception as e:
            logger.error(f"Failed to send SES alert: {str(e)}")

    def save(self, *args, **kwargs):
        """
        Overrides the save method to trigger alerts automatically 
        when stock is low.
        """
        # Define your threshold for an alert (e.g., stock < 5)
        if self.quantity < 5:
            # We only send the alert if the product already exists (not first creation)
            # or you can remove the 'self.pk' check to alert on new low-stock items.
            self.send_ses_alert()
            
        super(Product, self).save(*args, **kwargs)