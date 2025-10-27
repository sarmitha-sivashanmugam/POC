"""
Simplified tool definitions for Gemini Live API function calling.
Only essential tools to reduce redundancy and complexity.
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from django.db.models import Q
from asgiref.sync import sync_to_async
from .models import Products, Cart, UserProfile


# Tool definitions using Google Gemini API format
from google.genai import types
from google import genai


# Find products tool - SIMPLIFIED to match database fields exactly
find_products_tool = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="find_products",
            description="Find products based on patient age, medical conditions, and product category",
            parameters=genai.types.Schema(
                type=genai.types.Type.OBJECT,
                required=["age_range"],
                properties={
                    "age_range": genai.types.Schema(
                        type=genai.types.Type.STRING,
                        enum=["teething_to_24_months", "age_2_to_5", "age_6_to_12", "age_13_and_above"],
                        description="Patient's age range - choose the appropriate range based on their age"
                    ),
                    "pregnancy": genai.types.Schema(
                        type=genai.types.Type.BOOLEAN,
                        description="Whether patient is pregnant (filters pregnancy=True products)"
                    ),
                    "orthodontics": genai.types.Schema(
                        type=genai.types.Type.BOOLEAN,
                        description="Whether patient has braces (filters orthodontics=True products)"
                    ),
                    "category": genai.types.Schema(
                        type=genai.types.Type.STRING,
                        description="Product category to filter by (e.g., 'Toothpaste', 'Mouthwash', 'Toothbrush')"
                    ),
                    "limit": genai.types.Schema(
                        type=genai.types.Type.INTEGER,
                        description="Maximum number of products to return (default: 10)"
                    )
                }
            )
        )
    ]
)

# Manage cart tool
manage_cart_tool = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="manage_cart",
            description="Add products to cart or get cart summary",
            parameters=genai.types.Schema(
                type=genai.types.Type.OBJECT,
                required=["action"],
                properties={
                    "action": genai.types.Schema(
                        type=genai.types.Type.STRING,
                        enum=["add", "get_summary"],
                        description="Action to perform: 'add' products or 'get_summary'"
                    ),
                    "products": genai.types.Schema(
                        type=genai.types.Type.ARRAY,
                        items=genai.types.Schema(
                            type=genai.types.Type.OBJECT,
                            required=["name"],
                            properties={
                                "name": genai.types.Schema(
                                    type=genai.types.Type.STRING,
                                    description="Product name"
                                ),
                                "quantity": genai.types.Schema(
                                    type=genai.types.Type.INTEGER,
                                    description="Quantity to add (default: 1)"
                                )
                            }
                        ),
                        description="Products to add (only required when action='add')"
                    )
                }
            )
        )
    ]
)

# Combined tools list
TOOL_DEFINITIONS = [find_products_tool, manage_cart_tool]


# Removed get_age_range function - now using direct age_range parameter


async def execute_tool(tool_name: str, parameters: Dict[str, Any], user) -> Dict[str, Any]:
    """
    Execute a tool function and return the result.
    """
    print(f"\nEXECUTE_TOOL DEBUG")
    print(f"   Tool Name: {tool_name}")
    print(f"   Parameters: {json.dumps(parameters, indent=2)}")
    print(f"   User: {user.username if user else 'Anonymous'}")
    print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Multiple tool calls are allowed - each search is independent")
    print(f"   This is tool call #{getattr(execute_tool, 'call_count', 0) + 1} in this conversation")
    execute_tool.call_count = getattr(execute_tool, 'call_count', 0) + 1
    
    try:
        if tool_name == "find_products":
            print(f"   🎯 Routing to find_products function")
            result = await find_products(parameters)
            print(f"   ✅ find_products completed")
            return result
        elif tool_name == "manage_cart":
            print(f"   🎯 Routing to manage_cart function")
            result = await manage_cart(parameters, user)
            print(f"   ✅ manage_cart completed")
            return result
        else:
            print(f"   ❌ Unknown tool: {tool_name}")
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }
    except Exception as e:
        print(f"   🚨 Exception in execute_tool: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Tool execution error: {str(e)}"
        }





async def find_products(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Find products based on patient age, medical conditions, and category - matches database fields exactly."""
    print(f"\n🔍 FIND_PRODUCTS DEBUG")
    print(f"   📊 Input Parameters:")
    print(f"      Age: {parameters.get('age', 'Not provided')}")
    print(f"      Pregnancy: {parameters.get('pregnancy', False)}")
    print(f"      Orthodontics: {parameters.get('orthodontics', False)}")
    print(f"      Category: {parameters.get('category', 'Not provided')}")
    print(f"      Limit: {parameters.get('limit', 10)}")
    print(f"   🔍 RAW PARAMETERS RECEIVED:")
    print(f"      {json.dumps(parameters, indent=2)}")
    
    try:
        # Validate required parameters
        age_range = parameters.get("age_range")
        pregnancy = parameters.get("pregnancy", False)
        orthodontics = parameters.get("orthodontics", False)
        category = parameters.get("category")
        limit = parameters.get("limit", 10)
        
        print(f"   ✅ PARAMETER VALIDATION:")
        print(f"      Age Range: {age_range} (type: {type(age_range)})")
        print(f"      Pregnancy: {pregnancy} (type: {type(pregnancy)})")
        print(f"      Orthodontics: {orthodontics} (type: {type(orthodontics)})")
        print(f"      Category: {category} (type: {type(category)})")
        print(f"   🔍 MAPPING VERIFICATION:")
        print(f"      Age Range '{age_range}' → Database filter: {age_range}=True")
        print(f"      Orthodontics {orthodontics} → Database filter: orthodontics={orthodontics}")
        print(f"      Category '{category}' → Database filter: category__icontains='{category}'")
        
        # Validate age_range parameter
        if not age_range:
            print(f"   ❌ ERROR: Age range parameter is missing!")
            return {
                "success": False,
                "error": "Age range parameter is required",
                "products": [],
                "count": 0
            }
        
        valid_age_ranges = ["teething_to_24_months", "age_2_to_5", "age_6_to_12", "age_13_and_above"]
        if age_range not in valid_age_ranges:
            print(f"   ❌ ERROR: Invalid age range: {age_range}")
            return {
                "success": False,
                "error": f"Invalid age range: {age_range}. Must be one of: {valid_age_ranges}",
                "products": [],
                "count": 0
            }
        
        # Validate category parameter
        if not category:
            print(f"   ❌ ERROR: Category parameter is missing!")
            return {
                "success": False,
                "error": "Category parameter is required",
                "products": [],
                "count": 0
            }
        
        print(f"   ✅ All parameters validated successfully")
        
        # Build comprehensive query
        print(f"   🔨 Building database query...")
        query = Q()
        
        # Age-based filtering - direct mapping
        print(f"   👶 Age-based filtering for range: {age_range}")
        query &= Q(**{age_range: True})
        print(f"      → Added {age_range}=True filter")
        
        # Category filtering
        if category:
            query &= Q(category__icontains=category)
            print(f"   📂 Category filtering: {category}")
        
        # Medical condition filtering
        if pregnancy:
            query &= Q(pregnancy=True)
            print(f"   🤰 Pregnancy-safe filter added (pregnancy=True)")
        
        if orthodontics:
            query &= Q(orthodontics=True)
            print(f"   🦷 Orthodontic-friendly filter added (orthodontics=True)")
        
        # Execute query using simple database filtering
        
        # Execute query
        print(f"   🚀 Executing database query...")
        print(f"   📊 Query limit: {limit}")
        print(f"   🔍 Final query filters:")
        print(f"      - Age range: {age_range}")
        print(f"      - Pregnancy: {pregnancy}")
        print(f"      - Orthodontics: {orthodontics}")
        print(f"      - Category: {category}")
        
        products = await sync_to_async(list)(Products.objects.filter(query)[:limit])
        print(f"   📈 Products found: {len(products)}")
        
        # Debug: Show what products were found
        if len(products) > 0:
            print(f"   📋 Found products:")
            for i, product in enumerate(products[:3], 1):
                print(f"      {i}. {product.product_name} (age_6_to_12={product.age_6_to_12}, orthodontics={product.orthodontics})")
            if len(products) > 3:
                print(f"      ... and {len(products) - 3} more products")
        else:
            # Debug: Check what products exist in database with these flags
            print(f"   🔍 DEBUG: Checking database contents...")
            all_products = await sync_to_async(list)(Products.objects.all()[:10])
            print(f"   📊 Total products in database: {len(all_products)}")
            
            # Check products with age_6_to_12=True
            age_6_12_products = await sync_to_async(list)(Products.objects.filter(age_6_to_12=True)[:5])
            print(f"   👶 Products with age_6_to_12=True: {len(age_6_12_products)}")
            for product in age_6_12_products:
                print(f"      - {product.product_name} (orthodontics={product.orthodontics}, category={product.category})")
            
            # Check products with orthodontics=True
            ortho_products = await sync_to_async(list)(Products.objects.filter(orthodontics=True)[:5])
            print(f"   🦷 Products with orthodontics=True: {len(ortho_products)}")
            for product in ortho_products:
                print(f"      - {product.product_name} (age_6_to_12={product.age_6_to_12}, category={product.category})")
            
            # Check products with both age_6_to_12=True AND orthodontics=True
            both_products = await sync_to_async(list)(Products.objects.filter(age_6_to_12=True, orthodontics=True)[:5])
            print(f"   🎯 Products with BOTH age_6_to_12=True AND orthodontics=True: {len(both_products)}")
            for product in both_products:
                print(f"      - {product.product_name} (category={product.category})")
        
        # Handle no products found
        if len(products) == 0:
            print(f"   ❌ NO PRODUCTS FOUND!")
            print(f"   🔍 Query details:")
            print(f"      Age Range: {age_range}")
            print(f"      Pregnancy: {pregnancy}")
            print(f"      Orthodontics: {orthodontics}")
            print(f"      Category: {category}")
            
            # Try different filter combinations
            print(f"   🔄 Trying different filter combinations...")
            
            # Strategy 1: Try without orthodontics filter
            if orthodontics:
                print(f"   🔄 Strategy 1: Trying without orthodontics filter...")
                fallback_query = Q()
                fallback_query &= Q(**{age_range: True})
                
                fallback_query &= Q(category__icontains=category)
                
                if pregnancy:
                    fallback_query &= Q(pregnancy=True)
                
                fallback_products = await sync_to_async(list)(Products.objects.filter(fallback_query)[:limit])
                if len(fallback_products) > 0:
                    print(f"   ✅ Found {len(fallback_products)} products without orthodontics filter")
                    products = fallback_products
                    print(f"   📋 Found products (without orthodontics filter):")
                    for i, product in enumerate(fallback_products[:3], 1):
                        print(f"      {i}. {product.product_name} (age_6_to_12={product.age_6_to_12}, orthodontics={product.orthodontics})")
            
            # Strategy 2: Try alternative categories
            if len(products) == 0:
                print(f"   🔄 Strategy 2: Trying alternative categories...")
                alternative_categories = []
                if category.lower() == "toothpaste":
                    alternative_categories = ["Toothbrush", "Mouthwash"]
                elif category.lower() == "toothbrush":
                    alternative_categories = ["Toothpaste", "Mouthwash"]
                elif category.lower() == "mouthwash":
                    alternative_categories = ["Toothpaste", "Toothbrush"]
                else:
                    alternative_categories = ["Toothpaste", "Toothbrush", "Mouthwash"]
                
                print(f"   🔄 Trying alternative categories: {alternative_categories}")
                
                # Try each alternative category
                for alt_category in alternative_categories:
                    alt_query = Q()
                    alt_query &= Q(**{age_range: True})
                    
                    alt_query &= Q(category__icontains=alt_category)
                    
                    if pregnancy:
                        alt_query &= Q(pregnancy=True)
                    
                    # Try without orthodontics filter for alternative categories
                    alt_products = await sync_to_async(list)(Products.objects.filter(alt_query)[:limit])
                    if len(alt_products) > 0:
                        print(f"   ✅ Found {len(alt_products)} products in alternative category: {alt_category}")
                        products = alt_products
                        category = alt_category
                        break
            
            # Strategy 3: Try with any age range
            if len(products) == 0:
                print(f"   🔄 Strategy 3: Trying with any age range...")
                any_age_query = Q(category__icontains=category)
                if pregnancy:
                    any_age_query &= Q(pregnancy=True)
                if orthodontics:
                    any_age_query &= Q(orthodontics=True)
                
                any_age_products = await sync_to_async(list)(Products.objects.filter(any_age_query)[:limit])
                if len(any_age_products) > 0:
                    print(f"   ✅ Found {len(any_age_products)} products with any age range")
                    products = any_age_products
            
            # If still no products found, return error with suggestions
            if len(products) == 0:
                return {
                    "success": False,
                    "error": f"No products found for age_range {age_range}, pregnancy: {pregnancy}, orthodontics: {orthodontics}, category: {category}",
                    "products": [],
                    "count": 0,
                    "suggestion": f"Try a different category like 'Toothpaste' or 'Toothbrush'"
                }
        
        # Format results
        print(f"   📝 Formatting {len(products)} products...")
        results = []
        for i, product in enumerate(products, 1):
            product_data = {
                "id": product.id,
                "name": product.product_name,
                "category": product.category,
                "subcategory": product.subcategory,
                "price": float(product.price),
                "description": product.description,
                "pregnancy_safe": product.pregnancy,
                "orthodontic_friendly": product.orthodontics,
                "age_groups": {
                    "teething_to_24_months": product.teething_to_24_months,
                    "age_2_to_5": product.age_2_to_5,
                    "age_6_to_12": product.age_6_to_12,
                    "age_13_and_above": product.age_13_and_above
                }
            }
            results.append(product_data)
            print(f"      {i}. {product.product_name} - ${product.price}")
        
        result = {
            "success": True,
            "products": results,
            "count": len(results),
            "criteria": {
                "age_range": age_range,
                "pregnancy": pregnancy,
                "orthodontics": orthodontics,
                "category": category
            }
        }
        
        print(f"   ✅ find_products result:")
        print(f"      Success: {result['success']}")
        print(f"      Products: {result['count']}")
        
        return result
        
    except Exception as e:
        print(f"   🚨 Exception in find_products: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Product search error: {str(e)}"
        }


async def manage_cart(parameters: Dict[str, Any], user) -> Dict[str, Any]:
    """Manage cart operations - add products or get summary."""
    print(f"\n🛒 MANAGE_CART DEBUG")
    print(f"   📊 Input Parameters:")
    print(f"      Action: {parameters.get('action', 'Not provided')}")
    print(f"      Products: {parameters.get('products', [])}")
    print(f"   👤 User: {user.username if user else 'Anonymous'}")
    print(f"   🔍 RAW PARAMETERS RECEIVED:")
    print(f"      {json.dumps(parameters, indent=2)}")
    
    try:
        action = parameters.get("action")
        
        # Validate action parameter
        if not action:
            print(f"   ❌ ERROR: Action parameter is missing!")
            return {
                "success": False,
                "error": "Action parameter is required"
            }
        
        if action not in ["add", "get_summary"]:
            print(f"   ❌ ERROR: Invalid action: {action}")
            return {
                "success": False,
                "error": f"Invalid action: {action}. Must be 'add' or 'get_summary'"
            }
        
        print(f"   ✅ Action parameter validated: {action}")
        
        if action == "add":
            print(f"   🎯 Routing to add_to_cart function")
            products_to_add = parameters.get("products", [])
            print(f"   📦 Products to add: {len(products_to_add)}")
            print(f"   📋 Products details:")
            for i, product in enumerate(products_to_add, 1):
                print(f"      {i}. Name: '{product.get('name', 'MISSING')}', Quantity: {product.get('quantity', 'MISSING')}")
            
            if not products_to_add:
                print(f"   ❌ ERROR: No products provided for cart addition!")
                return {
                    "success": False,
                    "error": "No products provided for cart addition"
                }
            
            result = await add_to_cart(products_to_add, user)
            print(f"   ✅ add_to_cart completed")
            return result
        elif action == "get_summary":
            print(f"   🎯 Routing to get_cart_summary function")
            result = await get_cart_summary(user)
            print(f"   ✅ get_cart_summary completed")
            return result
        else:
            print(f"   ❌ Invalid action: {action}")
            return {
                "success": False,
                "error": f"Invalid action: {action}"
            }
            
    except Exception as e:
        print(f"   🚨 Exception in manage_cart: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Cart management error: {str(e)}"
        }


async def add_to_cart(products_to_add: List[Dict], user) -> Dict[str, Any]:
    """Add products to user's cart."""
    print(f"\n🛒 ADD_TO_CART DEBUG")
    print(f"   📦 Products to add: {len(products_to_add)}")
    print(f"   👤 User: {user.username if user else 'Anonymous'}")
    
    try:
        # Validate user
        if not user:
            print(f"   ❌ No user provided")
            return {
                "success": False,
                "error": "User not authenticated"
            }
        
        if not products_to_add:
            print(f"   ❌ No products provided")
            return {
                "success": False,
                "error": "No products provided"
            }
        
        # Validate products list
        if not isinstance(products_to_add, list):
            print(f"   ❌ Products must be a list")
            return {
                "success": False,
                "error": "Products must be provided as a list"
            }
        
        added_items = []
        errors = []
        
        for i, product_data in enumerate(products_to_add, 1):
            print(f"   📦 Processing product {i}/{len(products_to_add)}: {product_data}")
            
            # Validate product data structure
            if not isinstance(product_data, dict):
                print(f"      ❌ Product data must be a dictionary")
                errors.append(f"Product {i} is not a valid dictionary")
                continue
            
            product_name = product_data.get("name", "").strip()
            quantity = product_data.get("quantity", 1)
            
            print(f"      📝 Product name: '{product_name}', Quantity: {quantity}")
            
            # Validate product name
            if not product_name:
                print(f"      ❌ Empty product name")
                errors.append(f"Product {i}: Empty product name")
                continue
            
            # Check for common product name issues
            if len(product_name) < 3:
                print(f"      ❌ Product name too short: '{product_name}'")
                errors.append(f"Product {i}: Name too short: '{product_name}'")
                continue
            
            if product_name.lower() in ['product', 'item', 'thing', 'stuff']:
                print(f"      ❌ Generic product name: '{product_name}'")
                errors.append(f"Product {i}: Generic name: '{product_name}'")
                continue
            
            # Validate quantity
            try:
                quantity = int(quantity)
                if quantity <= 0:
                    print(f"      ❌ Invalid quantity: {quantity}")
                    errors.append(f"Product {i} '{product_name}': Invalid quantity {quantity}")
                    continue
            except (ValueError, TypeError):
                print(f"      ❌ Invalid quantity type: {quantity}")
                errors.append(f"Product {i} '{product_name}': Invalid quantity {quantity}")
                continue
            
            try:
                # Find the product with flexible matching
                print(f"      🔍 Searching for product: {product_name}")
                
                # Try exact match first
                try:
                    product = await sync_to_async(Products.objects.get)(product_name__iexact=product_name)
                    print(f"      ✅ Exact match found: {product.product_name} (ID: {product.id})")
                except Products.DoesNotExist:
                    # Try case-insensitive contains match
                    print(f"      🔍 Trying partial match for: {product_name}")
                    products = await sync_to_async(list)(Products.objects.filter(product_name__icontains=product_name))
                    if len(products) == 1:
                        product = products[0]
                        print(f"      ✅ Partial match found: {product.product_name} (ID: {product.id})")
                    elif len(products) > 1:
                        # Multiple matches - try to find the best one
                        print(f"      🔍 Multiple matches found ({len(products)}), selecting best match")
                        # Find the one with the most similar name
                        best_match = None
                        best_score = 0
                        for p in products:
                            # Simple similarity check
                            if product_name.lower() in p.product_name.lower():
                                score = len(product_name) / len(p.product_name)
                                if score > best_score:
                                    best_score = score
                                    best_match = p
                        if best_match:
                            product = best_match
                            print(f"      ✅ Best match selected: {product.product_name} (ID: {product.id})")
                        else:
                            raise Products.DoesNotExist(f"Multiple products found but no good match for '{product_name}'")
                    else:
                        raise Products.DoesNotExist(f"No products found matching '{product_name}'")
                
                # Add or update cart item
                print(f"      🛒 Adding to cart...")
                try:
                    cart_item, created = await sync_to_async(Cart.objects.get_or_create)(
                        user=user,
                        product=product,
                        defaults={'quantity': quantity}
                    )
                    
                    if not created:
                        # Update quantity if item already exists
                        print(f"      📈 Updating existing cart item (was {cart_item.quantity}, adding {quantity})")
                        cart_item.quantity += quantity
                        await sync_to_async(cart_item.save)()
                        print(f"      ✅ Updated existing cart item")
                    else:
                        print(f"      ✨ Created new cart item")
                    
                    # Calculate total price
                    total_price = float(cart_item.quantity * product.price)
                    
                    added_items.append({
                        "product_name": product.product_name,
                        "quantity": cart_item.quantity,
                        "price": float(product.price),
                        "total_price": total_price
                    })
                    print(f"      ✅ Successfully added: {product.product_name} (total qty: {cart_item.quantity}, total price: ${total_price})")
                    
                except Exception as cart_error:
                    print(f"      🚨 Error creating/updating cart item: {str(cart_error)}")
                    errors.append(f"Error adding '{product_name}' to cart: {str(cart_error)}")
                    continue
                
            except Products.DoesNotExist:
                print(f"      ❌ Product not found: {product_name}")
                errors.append(f"Product '{product_name}' not found")
            except Exception as e:
                print(f"      🚨 Error adding product: {str(e)}")
                errors.append(f"Error adding '{product_name}': {str(e)}")
        
        # Calculate totals
        total_price = sum(item.get("total_price", 0) for item in added_items)
        total_quantity = sum(item.get("quantity", 0) for item in added_items)
        
        # Create success message with product names
        if len(added_items) > 0:
            product_names = [item["product_name"] for item in added_items]
            success_message = f"Great! I've added {', '.join(product_names)} to your cart."
        else:
            success_message = "No products were added to cart"
        
        result = {
            "success": len(added_items) > 0,
            "added_items": added_items,
            "errors": errors,
            "message": success_message,
            "total_items": len(added_items),
            "total_errors": len(errors),
            "total_price": round(total_price, 2),
            "total_quantity": total_quantity
        }
        
        print(f"   ✅ add_to_cart result:")
        print(f"      Success: {result['success']}")
        print(f"      Items added: {len(added_items)}")
        print(f"      Total quantity: {total_quantity}")
        print(f"      Total price: ${total_price}")
        print(f"      Errors: {len(errors)}")
        if errors:
            print(f"      Error details: {errors}")
        if added_items:
            print(f"      Added items:")
            for item in added_items:
                print(f"         - {item['product_name']} x{item['quantity']} = ${item['total_price']}")
        
        return result
        
    except Exception as e:
        print(f"   🚨 Exception in add_to_cart: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Add to cart error: {str(e)}"
        }


async def get_cart_summary(user) -> Dict[str, Any]:
    """Get current cart contents and summary."""
    print(f"\n🛒 GET_CART_SUMMARY DEBUG")
    print(f"   👤 User: {user.username if user else 'Anonymous'}")
    
    try:
        print(f"   🔍 Fetching cart items for user...")
        cart_items = await sync_to_async(list)(Cart.objects.filter(user=user))
        print(f"   📦 Found {len(cart_items)} cart items")
        
        items = []
        total_price = 0
        total_items = 0
        
        for i, item in enumerate(cart_items, 1):
            item_data = {
                "product_id": item.product.id,
                "product_name": item.product.product_name,
                "category": item.product.category,
                "subcategory": item.product.subcategory,
                "price": float(item.product.price),
                "quantity": item.quantity,
                "total_price": float(item.total_price)
            }
            items.append(item_data)
            total_price += float(item.total_price)
            total_items += item.quantity
            print(f"      {i}. {item.product.product_name} x{item.quantity} = ${item.total_price}")
        
        result = {
            "success": True,
            "cart": {
                "items": items,
                "total_items": total_items,
                "total_price": round(total_price, 2)
            }
        }
        
        print(f"   get_cart_summary result:")
        print(f"      Success: {result['success']}")
        print(f"      Total items: {total_items}")
        print(f"      Total price: ${round(total_price, 2)}")
        
        return result
        
    except Exception as e:
        print(f"   Exception in get_cart_summary: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Cart summary error: {str(e)}"
        }
