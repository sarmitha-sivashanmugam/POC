import os
import json
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import UserProfile, Cart, Products


def login_view(request):
    """Handle login page."""
    if request.user.is_authenticated:
        # Check if user has a profile, if not redirect to profile page
        try:
            profile = request.user.profile
            return redirect('dashboard')
        except UserProfile.DoesNotExist:
            return redirect('profile')
    return render(request, 'chat/login.html')


@login_required
def login_redirect_view(request):
    """Handle post-login redirect to check for profile."""
    try:
        profile = request.user.profile
        return redirect('dashboard')
    except UserProfile.DoesNotExist:
        return redirect('profile')


@login_required
def profile_view(request):
    """Handle user profile creation and editing."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = None
    
    if request.method == 'POST':
        # Update user basic info
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.save()
        
        # Create or update profile
        if profile:
            profile.age = request.POST.get('age') or None
            profile.gender = request.POST.get('gender', '')
            profile.phone_country_code = request.POST.get('phone_country_code', '+1')
            profile.phone_number = request.POST.get('phone_number', '')
            profile.address = request.POST.get('address', '')
            profile.save()
        else:
            profile = UserProfile.objects.create(
                user=request.user,
                age=request.POST.get('age') or None,
                gender=request.POST.get('gender', ''),
                phone_country_code=request.POST.get('phone_country_code', '+1'),
                phone_number=request.POST.get('phone_number', ''),
                address=request.POST.get('address', '')
            )
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('dashboard')
    
    context = {
        'profile': profile,
        'country_choices': UserProfile.COUNTRY_CHOICES,
    }
    return render(request, 'chat/profile.html', context)

@login_required
def dashboard(request):
    """Render the main dashboard for voice chat."""
    context = {
        "websocket_host": settings.WEBSOCKET_HOST,
    }
    return render(request, "chat/dashboard.html", context)

@login_required
def cart_view(request):
    """Display the shopping cart page"""
    return render(request, 'chat/cart.html')


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_cart_api(request):
    """Get user's cart items"""
    try:
        cart_items = Cart.objects.filter(user=request.user)
        
        items = []
        total_price = 0
        total_items = 0
        
        for item in cart_items:
            items.append({
                'product_id': item.product.id,
                'product_name': item.product.product_name,
                'category': item.product.category,
                'subcategory': item.product.subcategory,
                'price': float(item.product.price),
                'quantity': item.quantity,
                'total_price': float(item.total_price)
            })
            total_price += float(item.total_price)
            total_items += item.quantity
        
        cart_data = {
            'items': items,
            'total_items': total_items,
            'total_price': round(total_price, 2)
        }
        
        return JsonResponse({
            'success': True,
            'cart': cart_data
        })
        
    except Exception as e:
        print(f"Error getting cart: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def add_to_cart_api(request):
    """Add products to cart"""
    try:
        print("===== CART API CALLED =====")
        print(f"User: {request.user.username}")
        print(f"Request body: {request.body}")
        
        data = json.loads(request.body)
        products = data.get('products', [])
        
        print(f"Products to add: {products}")
        print(f"Number of products: {len(products)}")
        
        added_items = []
        
        for product_data in products:
            product_name = product_data.get('name')
            quantity = product_data.get('quantity', 1)
            
            # Validate product name
            if not product_name or not product_name.strip():
                print(f"❌ Empty or invalid product name: '{product_name}'")
                continue
                
            print(f"Looking for product: '{product_name}' with quantity: {quantity}")
            
            try:
                product = Products.objects.get(product_name__iexact=product_name)
                print(f"Found product: {product.product_name} (ID: {product.id})")
                
                # Check if item already exists in cart
                cart_item, created = Cart.objects.get_or_create(
                    user=request.user,
                    product=product,
                    defaults={'quantity': quantity}
                )
                
                if not created:
                    # Update quantity if item already exists
                    cart_item.quantity += quantity
                    cart_item.save()
                
                added_items.append({
                    'product_name': product.product_name,
                    'quantity': cart_item.quantity
                })
                
                print(f"✅ Successfully added {product.product_name} to cart")
                
            except Products.DoesNotExist:
                print(f"❌ Product with name '{product_name}' not found in database")
                # List all available products for debugging
                all_products = Products.objects.all()
                print(f"Available products: {[p.product_name for p in all_products]}")
                continue
            except Exception as e:
                print(f"❌ Error processing product '{product_name}': {e}")
                continue
        
        print(f"Final added items: {added_items}")
        print(f"Total items added: {len(added_items)}")
        
        return JsonResponse({
            'success': True,
            'message': f'Added {len(added_items)} products to cart',
            'added_items': added_items
        })
        
    except Exception as e:
        print(f"❌ Error in cart API: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def update_cart_item_api(request):
    """Update cart item quantity"""
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = data.get('quantity')
        
        if quantity <= 0:
            # Remove item if quantity is 0 or negative
            Cart.objects.filter(user=request.user, product_id=product_id).delete()
            return JsonResponse({
                'success': True,
                'message': 'Item removed from cart'
            })
        
        cart_item = Cart.objects.get(user=request.user, product_id=product_id)
        cart_item.quantity = quantity
        cart_item.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Cart updated'
        })
        
    except Cart.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Item not found in cart'
        }, status=404)
    except Exception as e:
        print(f"Error updating cart: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def remove_from_cart_api(request):
    """Remove item from cart"""
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        
        Cart.objects.filter(user=request.user, product_id=product_id).delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Item removed from cart'
        })
        
    except Exception as e:
        print(f"Error removing from cart: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def clear_cart_api(request):
    """Clear all items from user's cart"""
    try:
        # Delete all cart items for the user
        deleted_count = Cart.objects.filter(user=request.user).delete()[0]
        
        print(f"Cleared {deleted_count} items from cart for user: {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': f'Cleared {deleted_count} items from cart',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        print(f"Error clearing cart: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)



