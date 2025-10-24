from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('P', 'Prefer not to say'),
    ]
    
    COUNTRY_CHOICES = [
        ('+1', '🇺🇸 United States'),
        ('+44', '🇬🇧 United Kingdom'),
        ('+91', '🇮🇳 India'),
        ('+86', '🇨🇳 China'),
        ('+49', '🇩🇪 Germany'),
        ('+33', '🇫🇷 France'),
        ('+81', '🇯🇵 Japan'),
        ('+61', '🇦🇺 Australia'),
        ('+55', '🇧🇷 Brazil'),
        ('+39', '🇮🇹 Italy'),
        ('+34', '🇪🇸 Spain'),
        ('+7', '🇷🇺 Russia'),
        ('+82', '🇰🇷 South Korea'),
        ('+31', '🇳🇱 Netherlands'),
        ('+46', '🇸🇪 Sweden'),
        ('+47', '🇳🇴 Norway'),
        ('+45', '🇩🇰 Denmark'),
        ('+41', '🇨🇭 Switzerland'),
        ('+43', '🇦🇹 Austria'),
        ('+32', '🇧🇪 Belgium'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, null=True, blank=True)
    phone_country_code = models.CharField(max_length=5, choices=COUNTRY_CHOICES, default='+1')
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}'s Profile"
    
    @property
    def full_phone_number(self):
        if self.phone_number:
            return f"{self.phone_country_code} {self.phone_number}"
        return None


class Products(models.Model):
    category = models.CharField(max_length=100)
    subcategory = models.CharField(max_length=100, blank=True, null=True)
    product_name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    
    # Flags for filtering purpose
    pregnancy = models.BooleanField(default=False)
    orthodontics = models.BooleanField(default=False)
    teething_to_24_months = models.BooleanField(default=False)
    age_2_to_5 = models.BooleanField(default=False)
    age_6_to_12 = models.BooleanField(default=False)
    age_13_and_above = models.BooleanField(default=False)
    
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.product_name


class Cart(models.Model):
    """Shopping cart model for persistent cart storage"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart')
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'product']
    
    def __str__(self):
        return f"{self.user.username} - {self.product.product_name} (x{self.quantity})"
    
    @property
    def total_price(self):
        return self.product.price * self.quantity
