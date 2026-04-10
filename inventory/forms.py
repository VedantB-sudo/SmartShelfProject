from django import forms
from .models import Product
from django.contrib.auth.models import User

class ProductForm(forms.Form):
    name = forms.CharField(max_length=201)
    category = forms.CharField(max_length=100)
    quantity = forms.IntegerField(min_value=0)
    price = forms.DecimalField(max_digits=10, decimal_places=2)
    shelf_number = forms.CharField(max_length=50, required=False, label="Shelf Number")
    is_perishable = forms.BooleanField(required=False, label="Is Perishable?")
    current_temperature = forms.FloatField(required=False, label="Current Temp (°C)", initial=20.0)
    temp_threshold = forms.FloatField(required=False, label="Temp Threshold (°C)", initial=15.0)
    expiry_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}), help_text="Upload an image to auto-detect expiry")
    image = forms.ImageField(required=False, help_text="Upload a label image to auto-detect expiry date")

class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    is_staff = forms.BooleanField(required=False, label="Grant Admin Access")

    class Meta:
        model = User
        fields = ['username', 'password', 'is_staff']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user