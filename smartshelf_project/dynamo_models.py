from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, NumberAttribute, UTCDateTimeAttribute

class InventoryItem(Model):
    class Meta:
        table_name = "SmartShelf_Inventory"
        region = 'us-east-1'  # Change to your AWS region

    # Primary Key (Partition Key)
    sku = UnicodeAttribute(hash_key=True)
    
    # Attributes
    product_name = UnicodeAttribute()
    quantity = NumberAttribute(default=0)
    expiry_date = UTCDateTimeAttribute()
    category = UnicodeAttribute(null=True)