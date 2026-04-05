from datetime import date

class FreshnessAuditor:
    def __init__(self, product_name, category):
        self.product_name = product_name
        self.category = category

    def calculate_status(self, expiry_date):
        """Calculates freshness based on days remaining until expiry."""
        if not expiry_date:
            return "Unknown"
        
        today = date.today()
        days_left = (expiry_date - today).days

        if days_left < 0:
            return "Expired"
        elif days_left <= 3:
            return "Critical: Action Required"
        elif days_left <= 7:
            return "Warning: Short Shelf Life"
        else:
            return "Stable"

    def get_audit_summary(self, expiry_date):
        status = self.calculate_status(expiry_date)
        return f"Audit for {self.product_name} ({self.category}): Status is {status}."