from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('login-redirect/', views.login_redirect_view, name='login_redirect'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('cart/', views.cart_view, name='cart'),
    path('api/cart/', views.get_cart_api, name='get_cart_api'),
    path('api/cart/add/', views.add_to_cart_api, name='add_to_cart_api'),
    path('api/cart/update/', views.update_cart_item_api, name='update_cart_item_api'),
    path('api/cart/remove/', views.remove_from_cart_api, name='remove_from_cart_api'),
    path('api/cart/clear/', views.clear_cart_api, name='clear_cart_api'),
]