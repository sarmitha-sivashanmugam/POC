import json
import os
from google import genai
from dotenv import load_dotenv
from .models import Products

load_dotenv()

class LLMProcessor:
    def __init__(self, user=None):
        self.client = genai.Client(
            api_key=os.getenv("API_KEY"),
            http_options={"api_version": "v1alpha"}
        )
        self.model = "models/gemini-2.5-flash"
        self.user = user
    
    #age and conditions extraction
    def extract_patient_info(self, conversation_data):
        """
        Send everything to Gemini 2.0 Flash to extract only age range and conditions
        """
        print("===== LLM PROCESSOR STARTING =====")
        print("Conversation data:", json.dumps(conversation_data, indent=2))
        print("API Key configured:", "Yes" if os.getenv("API_KEY") else "No")
        print("Model:", self.model)
        
        # Format conversation into readable text
        conversation_text = "Dental Consultation Conversation:\n\n"
        for message in conversation_data.get('messages', []):
            role = message.get('role', 'unknown')
            text = message.get('text', '')
            if role == 'user':
                conversation_text += f"Patient: {text}\n"
            elif role == 'ai':
                conversation_text += f"Dental Assistant: {text}\n"
        
        print("Formatted conversation:", conversation_text)
        
        # Prompt to extract specific age groups and conditions for product filtering using Gemini 2.0 Flash
        prompt = f"""
        Analyze this dental consultation conversation and extract age group and medical conditions for product filtering.

        Conversation:
        {conversation_text}

        Return ONLY this JSON structure:
        {{
            "age_group": "Teething to 24 months" or "2 to 5" or "6 to 12" or "13 to above" or "Not specified",
            "conditions": {{
                "pregnancy": true/false,
                "orthodontics": true/false
            }}
        }}

        IMPORTANT: Return ONLY the JSON, no other text.
        """
        
        print("Sending to Gemini 2.0 Flash...")
        print(f"Prompt length: {len(prompt)} characters")
        print(f"Model: {self.model}")
        
        try:
            print("Making API call to Gemini...")
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "temperature": 0,
                    "max_output_tokens": 1000
                }
            )
            print("Gemini API call completed")
            
            print("Gemini response:", response.text if response else "None")
            
            # Check if response is valid
            if not response or not hasattr(response, 'text') or not response.text:
                print("ERROR: Empty or invalid response from Gemini")
                raise ValueError("Empty response from Gemini API")
            
            # Extract JSON from response
            response_text = response.text.strip()
            
            # Find JSON in response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
                print("Extracted JSON:", json.dumps(result, indent=2))
                return result
            else:
                raise ValueError("No JSON found in response")
                
        except Exception as e:
            print(f"ERROR: {e}")
            # Return default if failed
            return {
                "age_group": "Not specified",
                "conditions": {
                    "pregnancy": False,
                    "orthodontics": False
                }
            }
    #retrive from database
    def filter_products_by_age_and_conditions(self, age_group, conditions):
        """Filter products using intersection logic (AND conditions)"""
        # Construct filter dictionary directly
        filters = {}
        
        age_map = {
            "Teething to 24 months": "teething_to_24_months",
            "2 to 5": "age_2_to_5",
            "6 to 12": "age_6_to_12",
            "13 to above": "age_13_and_above"
        }
        
        if age_group in age_map:
            filters[age_map[age_group]] = True
        
        if conditions.get('pregnancy'):
            filters['pregnancy'] = True
        
        if conditions.get('orthodontics'):
            filters['orthodontics'] = True
        
        # Filter the Products
        filtered_products = list(Products.objects.filter(**filters))
        
        return filtered_products
    #main function for first filtering
    def process_conversation_and_filter_products(self, conversation_data):
        """Main method to process conversation and filter products"""
        print("===== PROCESSING CONVERSATION AND FILTERING PRODUCTS =====")
        
        # Step 1: Extract age group and conditions
        print("Extracting age group and conditions...")
        patient_info = self.extract_patient_info(conversation_data)
        
        # Step 2: Filter products
        print("Filtering products...")
        filtered_products = self.filter_products_by_age_and_conditions(
            patient_info.get('age_group', 'Not specified'),
            patient_info.get('conditions', {})
        )
        
        # Step 3: Return results
        result = {
            'status': 'success',
            'patient_info': patient_info,
            'filtered_products_count': len(filtered_products),
            'filtered_products': [
                {
                    'name': p.product_name,
                    'category': p.category,
                    'subcategory': p.subcategory,
                    'price': float(p.price),
                    'description': p.description or '',
                    'pregnancy': p.pregnancy,
                    'orthodontics': p.orthodontics,
                    'teething_to_24_months': p.teething_to_24_months,
                    'age_2_to_5': p.age_2_to_5,
                    'age_6_to_12': p.age_6_to_12,
                    'age_13_and_above': p.age_13_and_above
                } for p in filtered_products
            ]
        }
        
        print("===== PROCESSING COMPLETE =====")
        print(f"Age Group: {patient_info.get('age_group')}")
        print(f"Conditions: {patient_info.get('conditions')}")
        print(f"Filtered Products: {len(filtered_products)}")
        
        # Debug: Show intersection logic summary
        print("===== INTERSECTION FILTERING SUMMARY =====")
        age_group = patient_info.get('age_group', 'Not specified')
        conditions = patient_info.get('conditions', {})
        
        print(f"Looking for products that match ALL of:")
        if age_group != "Not specified":
            print(f"  - Age Group: {age_group}")
        if conditions.get('pregnancy'):
            print(f"  - Pregnancy Safe: Yes")
        if conditions.get('orthodontics'):
            print(f"  - Orthodontics: Yes")
        
        if not any([age_group != "Not specified", conditions.get('pregnancy'), conditions.get('orthodontics')]):
            print("  - No specific criteria - showing all products")
        
        return result
    
    def send_products_to_gemini_for_second_filter(self, filtered_products, conversation_data):
        """
        Send only product names and descriptions to Gemini for second filtering
        Returns list of selected product names
        """
        print("===== SECOND FILTERING WITH GEMINI 2.5 FLASH =====")
        print(f"Sending {len(filtered_products)} products for second filtering")
        
        # Format conversation into readable text
        conversation_text = "Dental Consultation:\n"
        for message in conversation_data.get('messages', []):
            role = message.get('role', 'unknown')
            text = message.get('text', '')
            if role == 'user':
                conversation_text += f"P: {text}\n"
            elif role == 'ai':
                conversation_text += f"A: {text}\n"
        
        # Format only product names and descriptions (much more concise)
        products_text = "Available Products:\n\n"
        for i, product in enumerate(filtered_products, 1):
            # Truncate description if too long
            description = product['description'][:150] + "..." if len(product['description']) > 150 else product['description']
            products_text += f"{i}. {product['name']}\n"
            products_text += f"   {description}\n\n"
        
        # Create prompt for second filtering
        prompt = f"""
        Based on the dental consultation conversation and the available products, 
        select the most relevant products for this patient.

        {conversation_text}

        {products_text}

        Analyze the conversation and select products that would be most beneficial for this patient.
        Consider:
        1. Patient's specific dental needs mentioned in the conversation
        2. Specific symptoms or concerns mentioned
        3. Product descriptions and their relevance

        Return ONLY a JSON array of product names that are most relevant:
        ["Product Name 1", "Product Name 2", "Product Name 3"]

        IMPORTANT: Return ONLY the JSON array, no other text.
        """
        
        print("Sending to Gemini 2.5 Flash for second filtering...")
        print(f"Prompt length: {len(prompt)} characters")
        
        try:
            print("Making API call to Gemini 2.5 Flash...")
            print(f"Model: {self.model}")
            print(f"API Key configured: {'Yes' if os.getenv('API_KEY') else 'No'}")
            print(f"Temperature: 0")
            print(f"Max tokens: 1000")
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "temperature": 0,
                    "max_output_tokens": 10000
                }
            )
            
            print("Gemini API call completed")
            print("Gemini 2.5 Flash response:", response.text if response else "None")
            print("Response type:", type(response))
            print("Response attributes:", dir(response) if response else "No response object")
            
            if not response or not hasattr(response, 'text') or not response.text:
                print("ERROR: Empty response from Gemini 2.5 Flash")
                return [p['name'] for p in filtered_products]  # Return all product names if failed
            
            # Extract JSON array from response
            response_text = response.text.strip()
            
            # Find JSON array in response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response_text[start_idx:end_idx]
                selected_product_names = json.loads(json_str)
                print(f"Selected product names: {selected_product_names}")
                return selected_product_names
            else:
                print("No JSON array found in response, returning all product names")
                return [p['name'] for p in filtered_products]
                
        except Exception as e:
            print(f"ERROR in second filtering: {e}")
            print(f"Error type: {type(e)}")
            print(f"Error details: {str(e)}")
            return [p['name'] for p in filtered_products]  # Return all product names if failed
    
    def filter_products_by_names(self, product_names):
        """
        Filter products from database by product names using exact matching only
        """
        print(f"===== FILTERING PRODUCTS BY NAMES =====")
        print(f"Looking for {len(product_names)} product names")
        
        # Filter products by name using exact case-insensitive matching only
        filtered_products = []
        for name in product_names:
            # Use only exact match - no partial matching
            products = Products.objects.filter(product_name__iexact=name)
            if products.exists():
                filtered_products.extend(products)
                print(f"✅ Exact match found for: {name}")
            else:
                print(f"❌ No exact match found for: {name}")
        
        print(f"Found {len(filtered_products)} products in database")
        return filtered_products
    
    def finalize_products_with_chat_conversation(self, conversation_data, initial_filtered_products):
        """
        Finalize products using chat conversation context with Gemini 2.5 Flash
        """
        print("===== FINALIZING PRODUCTS WITH CHAT CONVERSATION =====")
        
        # Send products to Gemini for second filtering (returns product names)
        selected_product_names = self.send_products_to_gemini_for_second_filter(
            initial_filtered_products, 
            conversation_data
        )
        
        # Filter products from database by names
        final_products = self.filter_products_by_names(selected_product_names)
        
        # Convert to dict format for consistency
        final_products_dict = [
            {
                'name': p.product_name,
                'category': p.category,
                'subcategory': p.subcategory,
                'price': float(p.price),
                'description': p.description or '',
                'pregnancy': p.pregnancy,
                'orthodontics': p.orthodontics,
                'teething_to_24_months': p.teething_to_24_months,
                'age_2_to_5': p.age_2_to_5,
                'age_6_to_12': p.age_6_to_12,
                'age_13_and_above': p.age_13_and_above
            } for p in final_products
        ]
        
        # Create final result
        result = {
            'status': 'success',
            'initial_filtered_count': len(initial_filtered_products),
            'final_filtered_count': len(final_products_dict),
            'final_products': final_products_dict,
            'filtering_applied': 'Age/Condition + Chat Conversation Analysis'
        }
        
        print("===== FINAL FILTERING COMPLETE =====")
        print(f"Initial filtered: {len(initial_filtered_products)} products")
        print(f"Final filtered: {len(final_products_dict)} products")
        
        return result
    
    def process_conversation_with_second_filter(self, conversation_data):
        """
        Enhanced main method that includes second filtering with chat conversation
        """
        print("===== ENHANCED PROCESSING WITH SECOND FILTER =====")
        
        # Step 1: Extract age group and conditions
        print("Step 1: Extracting age group and conditions...")
        patient_info = self.extract_patient_info(conversation_data)
        
        # Step 2: First filtering by age and conditions
        print("Step 2: First filtering by age and conditions...")
        first_filtered_products = self.filter_products_by_age_and_conditions(
            patient_info.get('age_group', 'Not specified'),
            patient_info.get('conditions', {})
        )
        
        # Convert to dict format for Gemini processing
        first_filtered_dict = [
            {
                'name': p.product_name,
                'category': p.category,
                'subcategory': p.subcategory,
                'price': float(p.price),
                'description': p.description or '',
                'pregnancy': p.pregnancy,
                'orthodontics': p.orthodontics,
                'teething_to_24_months': p.teething_to_24_months,
                'age_2_to_5': p.age_2_to_5,
                'age_6_to_12': p.age_6_to_12,
                'age_13_and_above': p.age_13_and_above
            } for p in first_filtered_products
        ]
        
        # Step 3: Second filtering with chat conversation
        print("Step 3: Second filtering with chat conversation...")
        final_result = self.finalize_products_with_chat_conversation(
            conversation_data, 
            first_filtered_dict
        )
        
        # Add patient info to final result
        final_result['patient_info'] = patient_info
        
        print("===== ENHANCED PROCESSING COMPLETE =====")
        return final_result
    
