from django import forms
from .models import Product
from django.contrib.auth.models import User

class ProductForm(forms.Form):
    name = forms.CharField(max_length=201)
    category = forms.CharField(max_length=100)
    quantity = forms.IntegerField(min_value=0)
    price = forms.DecimalField(max_digits=10, decimal_places=2)
    expiry_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

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