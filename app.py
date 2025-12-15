"""
Flask Application for Mano Startuolis Accounting System - Vercel Serverless Version

This is a serverless function optimized for Vercel deployment.
- No local database (uses InstantDB on frontend)
- No file saving (processes images from memory)
- Minimal routes for AI receipt scanning
"""

import os
from flask import Flask, render_template, request, jsonify, send_file
from openai import OpenAI
import base64
import traceback
import json
import re
import io

# Base directory for absolute paths (templates, static, .env)
base_dir = os.path.abspath(os.path.dirname(__file__))

# Load environment variables first (CRITICAL: must be before any os.environ access)
# Safe dotenv import for Vercel compatibility
try:
    from dotenv import load_dotenv
    # Load .env locally using an absolute path
    load_dotenv(os.path.join(base_dir, '.env'))
except ImportError:
    # If python-dotenv is not installed (e.g. on Vercel), just skip it.
    # Vercel uses System Environment Variables anyway.
    pass

# Optional imports with fallbacks
try:
    import fitz  # PyMuPDF for PDF processing
except ImportError:
    print("WARNING: PyMuPDF not installed. PDF processing will be disabled.")
    fitz = None

try:
    from PIL import Image, ImageEnhance, ImageFilter
except ImportError:
    print("WARNING: Pillow not installed. Image preprocessing will be disabled.")
    Image = None
    ImageEnhance = None
    ImageFilter = None

# Initialize Flask app with explicit template/static folders (absolute paths)
app = Flask(
    __name__,
    template_folder=os.path.join(base_dir, 'templates'),
    static_folder=os.path.join(base_dir, 'static'),
)

# Secret key for flash messages
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Lazy-initialized OpenAI client (set inside route to avoid startup crashes)
client = None


@app.route('/')
def index():
    """
    Index route - renders login page.
    Users must log in before accessing the system.
    """
    return render_template('login.html')


@app.route('/dashboard', methods=['GET'])
def dashboard():
    """
    Dashboard page - main navigation hub after login.
    Shows cards for Expenses, Invoices, and Clients.
    """
    return render_template('dashboard.html')


@app.route('/expenses', methods=['GET'])
def expenses():
    """
    Expenses page - AI receipt scanning and expense tracking.
    Frontend uses InstantDB; no server-side expense queries needed.
    """
    return render_template('expenses.html')


@app.route('/invoices', methods=['GET'])
def invoices():
    """
    Invoices page - rendered as a standalone frontend view.
    Data is managed client-side (e.g., via InstantDB or other JS logic).
    """
    return render_template('invoices.html')


@app.route('/clients', methods=['GET'])
def clients():
    """
    Clients page - standalone frontend view for managing clients.
    Currently purely front-end (InstantDB or other JS can be used).
    """
    return render_template('clients.html')


@app.route('/scan-receipt', methods=['POST'])
def scan_receipt():
    """
    Route to scan receipt images using OpenAI Vision API.
    Serverless version: processes files from memory only (no disk saving).
    Supports split categories and bulk processing.
    """
    # Define valid categories - MUST match frontend dropdown options exactly
    VALID_CATEGORIES = ["Maistas", "Transportas", "Nuoma", "Komunaliniai", "Biuras", "Švara", "Buitinė chemija", "Paslaugos", "Kiti"]

    try:
        print("--- STARTING SCAN ---")
        
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        
        if not file.filename:
            return jsonify({"error": "Empty file uploaded"}), 400
        
        # Get file extension
        filename = file.filename
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        # Validate file extension
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
        if file_ext not in ALLOWED_EXTENSIONS:
            return jsonify({"error": f"Unsupported file format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
        
        # Read file into memory (no disk saving for serverless)
        file_bytes = file.read()
        
        # Generate a unique filename for response (not saved to disk)
        from datetime import datetime
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"receipt_{timestamp}.{file_ext}"
        
        # STEP 2: Preprocess image for better OCR accuracy
        try:
            if Image is None:
                # Fallback: use original image if PIL not available
                base64_image = base64.b64encode(file_bytes).decode('utf-8')
                mime_type = 'image/jpeg'
            elif file_ext == 'pdf':
                # PDF: Convert to image first, then preprocess
                if fitz is None:
                    return jsonify({"error": "PDF processing requires PyMuPDF. Install with: pip install PyMuPDF"}), 400
                
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                page = doc.load_page(0)
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")
                doc.close()
                
                # Open PDF image and preprocess
                img = Image.open(io.BytesIO(img_data))
                img = img.convert('L')  # Convert to grayscale
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(2.0)  # Increase contrast
                img = img.filter(ImageFilter.SHARPEN)  # Sharpen
                
                # Save to buffer as PNG
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                processed_bytes = buffer.getvalue()
                base64_image = base64.b64encode(processed_bytes).decode('utf-8')
                mime_type = 'image/png'
            else:
                # Image file: Preprocess directly
                img = Image.open(io.BytesIO(file_bytes))
                img = img.convert('L')  # Convert to grayscale
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(2.0)  # Increase contrast
                img = img.filter(ImageFilter.SHARPEN)  # Sharpen
                
                # Save to buffer as PNG
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                processed_bytes = buffer.getvalue()
                base64_image = base64.b64encode(processed_bytes).decode('utf-8')
                mime_type = 'image/png'
                
        except Exception as e:
            # Fallback: use original image if preprocessing fails
            print(f"Image preprocessing error: {e}, using original image")
            base64_image = base64.b64encode(file_bytes).decode('utf-8')
            mime_type = f'image/{file_ext}' if file_ext != 'jpg' else 'image/jpeg'
        
        # Get / lazy-init OpenAI client in a crash-proof way
        global client
        if client is None:
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                return jsonify({"error": "OpenAI API key not configured"}), 500
            try:
                client = OpenAI(api_key=api_key)
            except Exception as e:
                # If client initialization fails, surface the real error
                print(f"OpenAI client initialization error: {e}")
                return jsonify({"error": f"Failed to initialize OpenAI client: {str(e)}"}), 500
        
        # STEP 3: Build system prompt for receipt digitization
        STRICT_CATEGORIES = ["Maistas", "Transportas", "Nuoma", "Komunaliniai", "Biuras", "Švara", "Buitinė chemija", "Paslaugos", "Kiti"]
        
        system_prompt = f"""You are a forensic accounting OCR robot. Your goal is 100% data extraction completeness.

The image has been high-contrast processed. Read distinct lines carefully. Do not merge lines.

1. **EXTRACT EVERY SINGLE LINE ITEM.** Do not skip anything. If a receipt has 50 items, return 50 items.

2. **NO SUMMARIZATION.** Do not group 'Various items'. List them individually.

3. **Discounts**: If you see a discount line (e.g., -1.50), include it as a separate item with a negative amount, category 'Kiti'.

4. **Categorization**: Assign a category for each item from this EXACT list: {STRICT_CATEGORIES}.

Category rules:
- Food, drinks, snacks, groceries, restaurants, cafes, bread, milk, meat → 'Maistas'
- Fuel, gas, parking, car wash, tolls, public transport, taxi → 'Transportas'
- Rent, housing payments, lease → 'Nuoma'
- Utilities, electricity, water, gas bills, internet, phone → 'Komunaliniai'
- Paper, pens, office supplies, equipment, stationery, printer → 'Biuras'
- Cleaning services, professional cleaning → 'Švara'
- Detergents, soap, shampoo, washing powder, dishwasher tablets, cleaning chemicals, hygiene products → 'Buitinė chemija'
- Services, repairs, consulting, professional services → 'Paslaugos'
- If unsure or doesn't fit above → 'Kiti'

5. **Structure**: Return JSON: {{ 'items': [{{vendor, date, description, amount, vat_amount, net_amount, category}}, ...] }}.

For EACH item, return:
- 'vendor' (e.g., 'Maxima', 'Circle K')
- 'date' (YYYY-MM-DD format)
- 'description' (Product name or item description - be specific, no grouping)
- 'amount' (Price WITH VAT/PVM - use total_amount if shown separately)
- 'vat_amount' (The VAT/PVM portion of the price)
- 'net_amount' (Price WITHOUT VAT/PVM)
- 'category' (from the list above)

Calculation Rule: If VAT is only shown at the bottom summary, calculate the VAT for each item proportionally (usually 21% in Lithuania, or 9% for books/heat).

Example: If Total is 121.00 and VAT is 21.00, then net is 100.00.

CRITICAL: Extract EVERY item. Do not skip or summarize. If the receipt is illegible, return {{"items": []}}."""
        
        # User prompt with OCR-specific instructions
        user_prompt = """Analyze this Lithuanian receipt image carefully:

1. Look for the 'Total' or 'Mokėti' amount. It is usually the largest number at the bottom.
2. Look for VAT/PVM information - it may be shown per item or as a summary at the bottom.
3. Analyze vendor names carefully (e.g. 'UAB Maxima LT' -> 'Maxima').
4. If the image is blurry, do your best to guess based on context.
5. Extract all items with their VAT amounts (total_amount, vat_amount, net_amount).
6. If VAT is only shown in summary, calculate proportionally (21% standard, 9% for books/heat).
7. Return all items in the JSON format specified."""

        # API Call with JSON response format
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}",
                                "detail": "high"  # Enable high resolution for better OCR
                            }
                        }
                    ]
                }
            ],
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        # Get raw content from AI response
        raw_content = completion.choices[0].message.content
        
        # Print what AI actually sent
        print(f"DEBUG AI RAW: {raw_content}")
        
        # Cleaning Logic
        clean_json = re.sub(r'```json|```', '', raw_content).strip()
        print(f"DEBUG Clean JSON: {clean_json}")
        
        # Parse JSON
        try:
            data = json.loads(clean_json)
            print(f"DEBUG Parsed Data: {data}")
        except json.JSONDecodeError as je:
            print(f"JSON PARSE ERROR: {je}")
            return jsonify({"error": f"AI returned bad JSON. Raw: {raw_content[:200]}..."}), 500
        
        # EXTREMELY FLEXIBLE JSON PARSING LOGIC
        items = None
        
        # 1. Direct List
        if isinstance(data, list):
            print("DEBUG: Data is a direct list, using as items")
            items = data
        
        # 2. Dictionary Search
        elif isinstance(data, dict):
            print("DEBUG: Data is a dictionary, searching for items...")
            
            common_keys = ['items', 'expenses', 'products', 'receipt_items']
            found_key = None
            
            for key in common_keys:
                if key in data:
                    found_key = key
                    items = data[key]
                    print(f"DEBUG: Found items under key '{key}'")
                    break
            
            # Fallback: iterate through ALL values
            if items is None:
                print("DEBUG: No common keys found, searching all dictionary values...")
                for key, value in data.items():
                    if isinstance(value, list):
                        items = value
                        print(f"DEBUG: Found list under key '{key}', using as items")
                        break
            
            # Check if data itself might be a single item
            if items is None:
                print("DEBUG: No list found in dictionary, checking if data is a single item...")
                required_fields = ['vendor', 'date', 'category']
                has_amount = 'total_amount' in data or 'amount' in data
                if all(key in data for key in required_fields) and has_amount:
                    items = [data]
                    print("DEBUG: Data appears to be a single item, wrapping in list")
        
        # 3. Empty Fallback
        if items is None:
            print("DEBUG: No items found, returning empty list")
            items = []
        
        # 4. Ensure items is a list
        if not isinstance(items, list):
            print(f"DEBUG: Items is not a list (type: {type(items)}), converting...")
            items = [items] if items else []
        
        print(f"DEBUG: Final items count: {len(items)}")
        
        # Validate and clean each item
        validated_items = []
        for item in items:
            required_keys = ['vendor', 'date', 'category']
            has_amount = 'total_amount' in item or 'amount' in item
            
            if not all(key in item for key in required_keys) or not has_amount:
                continue  # Skip invalid items
            
            # Normalize amount fields
            if 'amount' in item and 'total_amount' not in item:
                item['total_amount'] = item.pop('amount')
            
            # Convert total_amount if it's a string
            if 'total_amount' in item:
                if isinstance(item['total_amount'], str):
                    amount_str = item['total_amount'].replace('€', '').replace('$', '').replace(',', '').strip()
                    try:
                        item['total_amount'] = float(amount_str)
                    except ValueError:
                        continue  # Skip items with invalid amounts
            
            # Handle vat_amount
            if 'vat_amount' not in item:
                item['vat_amount'] = 0.0
            elif isinstance(item['vat_amount'], str):
                vat_str = item['vat_amount'].replace('€', '').replace('$', '').replace(',', '').strip()
                try:
                    item['vat_amount'] = float(vat_str) if vat_str else 0.0
                except ValueError:
                    item['vat_amount'] = 0.0
            
            # Handle net_amount
            if 'net_amount' not in item:
                total = float(item.get('total_amount', 0))
                vat = float(item.get('vat_amount', 0))
                item['net_amount'] = total - vat
            elif isinstance(item['net_amount'], str):
                net_str = item['net_amount'].replace('€', '').replace('$', '').replace(',', '').strip()
                try:
                    item['net_amount'] = float(net_str) if net_str else 0.0
                except ValueError:
                    total = float(item.get('total_amount', 0))
                    vat = float(item.get('vat_amount', 0))
                    item['net_amount'] = total - vat
            
            # STRICT Category Validation with Fallback Logic
            original_category = item.get('category', '').strip()
            
            if original_category not in VALID_CATEGORIES:
                category_lower = original_category.lower()
                matched_category = None
                
                # Try exact case-insensitive match
                for valid_cat in VALID_CATEGORIES:
                    if valid_cat.lower() == category_lower:
                        matched_category = valid_cat
                        break
                
                # Intelligent fallback
                if not matched_category:
                    fallback_map = {
                        'groceries': 'Maistas',
                        'food': 'Maistas',
                        'restaurant': 'Maistas',
                        'cafe': 'Maistas',
                        'fuel': 'Transportas',
                        'gas': 'Transportas',
                        'parking': 'Transportas',
                        'cleaning': 'Švara',
                        'office': 'Biuras',
                        'stationery': 'Biuras',
                        'utilities': 'Komunaliniai',
                        'rent': 'Nuoma',
                        'housing': 'Nuoma',
                        'services': 'Paslaugos',
                        'household': 'Buitinė chemija',
                        'chemicals': 'Buitinė chemija',
                        'detergent': 'Buitinė chemija',
                        'soap': 'Buitinė chemija'
                    }
                    
                    matched_category = fallback_map.get(category_lower)
                    
                    # Keyword matching
                    if not matched_category:
                        if any(keyword in category_lower for keyword in ['food', 'grocer', 'restaurant', 'cafe', 'meal', 'snack', 'bread', 'milk']):
                            matched_category = 'Maistas'
                        elif any(keyword in category_lower for keyword in ['fuel', 'gas', 'parking', 'transport', 'car', 'taxi']):
                            matched_category = 'Transportas'
                        elif any(keyword in category_lower for keyword in ['detergent', 'soap', 'shampoo', 'washing', 'chemical', 'hygiene', 'household']):
                            matched_category = 'Buitinė chemija'
                        elif any(keyword in category_lower for keyword in ['clean', 'cleaning service']):
                            matched_category = 'Švara'
                        elif any(keyword in category_lower for keyword in ['office', 'stationery', 'paper', 'pen', 'printer']):
                            matched_category = 'Biuras'
                        elif any(keyword in category_lower for keyword in ['utility', 'electric', 'water', 'internet', 'phone']):
                            matched_category = 'Komunaliniai'
                        elif any(keyword in category_lower for keyword in ['rent', 'lease', 'housing']):
                            matched_category = 'Nuoma'
                        elif any(keyword in category_lower for keyword in ['service', 'repair', 'consult']):
                            matched_category = 'Paslaugos'
                
                # Final fallback to 'Kiti'
                if not matched_category:
                    matched_category = 'Kiti'
                    print(f"⚠ Category fallback: '{original_category}' → 'Kiti'")
                
                item['category'] = matched_category
            
            # Map total_amount to amount for frontend compatibility
            if 'total_amount' in item:
                item['amount'] = item['total_amount']
            
            validated_items.append(item)
        
        # Return data with filename and items (filename is just for reference, not a saved file)
        result = {
            "filename": unique_filename,
            "items": validated_items
        }
        print(f"DEBUG: Returning {len(validated_items)} validated items")
        print("--- SCAN COMPLETE ---")
        return jsonify(result)
        
    except Exception as e:
        print("CRITICAL SERVER ERROR:")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/api/generate-pdf', methods=['POST'])
def generate_pdf():
    """
    Serverless PDF generation endpoint using FPDF2 with full Unicode support.
    Supports Lithuanian characters, seller/buyer details, and payment terms.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON body provided"}), 400

        # Invoice title (customizable)
        invoice_title = (data.get("invoice_title") or "PVM SASKAITA FAKTURA").strip()
        invoice_series = (data.get("invoice_series") or "SF").strip()

        # Seller details
        seller_name = (data.get("seller_name") or "").strip()
        seller_code = (data.get("seller_code") or "").strip()
        seller_vat = (data.get("seller_vat") or "").strip()
        seller_bank = (data.get("seller_bank") or "").strip()
        seller_address = (data.get("seller_address") or "").strip()

        # Buyer details
        client_name = (data.get("client_name") or "").strip()
        client_code = (data.get("client_code") or "").strip()
        client_vat = (data.get("client_vat") or "").strip()
        client_address = (data.get("client_address") or "").strip()

        # Invoice details
        invoice_number = (data.get("invoice_number") or "").strip()
        date_str = (data.get("date") or "").strip()
        due_date_str = (data.get("due_date") or "").strip()
        items = data.get("items") or []
        
        # Get totals from payload (or calculate)
        subtotal = float(data.get("subtotal") or 0)
        vat_total = float(data.get("vat_total") or 0)
        grand_total = float(data.get("total") or 0)

        if not client_name or not invoice_number or not date_str:
            return jsonify({"error": "Trūksta privalomų laukų: kliento pavadinimas, sąskaitos nr., data"}), 400

        if not isinstance(items, list) or len(items) == 0:
            return jsonify({"error": "Būtina pridėti bent vieną prekę/paslaugą"}), 400

        # Import FPDF2 with Unicode support
        try:
            from fpdf import FPDF
        except ImportError:
            return jsonify({"error": "PDF generatorius nepasiekiamas. Įdiekite fpdf2."}), 500

        # Helper function to safely encode text
        def safe_text(text):
            """Replace Lithuanian characters with ASCII equivalents for basic FPDF"""
            if not text:
                return ""
            replacements = {
                'ą': 'a', 'č': 'c', 'ę': 'e', 'ė': 'e', 'į': 'i',
                'š': 's', 'ų': 'u', 'ū': 'u', 'ž': 'z',
                'Ą': 'A', 'Č': 'C', 'Ę': 'E', 'Ė': 'E', 'Į': 'I',
                'Š': 'S', 'Ų': 'U', 'Ū': 'U', 'Ž': 'Z',
                '€': 'EUR'
            }
            result = text
            for lt_char, ascii_char in replacements.items():
                result = result.replace(lt_char, ascii_char)
            return result

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # ========== HEADER ==========
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_fill_color(41, 128, 185)  # Blue header
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 12, safe_text(invoice_title), ln=True, align="C", fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

        # Invoice number and date
        pdf.set_font("Helvetica", "B", 11)
        full_invoice_number = f"{invoice_series}-{invoice_number}"
        pdf.cell(95, 7, f"Saskaitos Nr.: {safe_text(full_invoice_number)}", border=0)
        pdf.cell(95, 7, f"Data: {date_str}", border=0, align="R")
        pdf.ln()
        
        # Due date if provided
        if due_date_str:
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(95, 6, "", border=0)
            pdf.cell(95, 6, f"Apmoketi iki: {due_date_str}", border=0, align="R")
        pdf.ln(8)

        # ========== SELLER & BUYER INFO ==========
        pdf.set_fill_color(245, 245, 245)
        
        # Seller box (left side)
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(90, 7, "PARDAVEJAS:", ln=True, fill=True)
        pdf.set_font("Helvetica", "", 9)
        
        if seller_name:
            pdf.cell(90, 5, safe_text(seller_name), ln=True)
        else:
            pdf.cell(90, 5, "(Nenurodyta)", ln=True)
        
        if seller_code:
            pdf.cell(90, 5, f"Im. kodas: {safe_text(seller_code)}", ln=True)
        if seller_vat:
            pdf.cell(90, 5, f"PVM kodas: {safe_text(seller_vat)}", ln=True)
        if seller_bank:
            pdf.cell(90, 5, f"IBAN: {safe_text(seller_bank)}", ln=True)
        if seller_address:
            pdf.cell(90, 5, safe_text(seller_address), ln=True)
        
        seller_end_y = pdf.get_y()
        
        # Buyer box (right side)
        pdf.set_xy(x_start + 100, y_start)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(90, 7, "PIRKEJAS:", ln=True, fill=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_x(x_start + 100)
        
        pdf.cell(90, 5, safe_text(client_name), ln=True)
        if client_code:
            pdf.set_x(x_start + 100)
            pdf.cell(90, 5, f"Im. kodas: {safe_text(client_code)}", ln=True)
        if client_vat:
            pdf.set_x(x_start + 100)
            pdf.cell(90, 5, f"PVM kodas: {safe_text(client_vat)}", ln=True)
        if client_address:
            pdf.set_x(x_start + 100)
            pdf.cell(90, 5, safe_text(client_address), ln=True)
        
        buyer_end_y = pdf.get_y()
        
        # Move to after both boxes
        pdf.set_y(max(seller_end_y, buyer_end_y) + 8)

        # ========== ITEMS TABLE ==========
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(52, 73, 94)  # Dark header
        pdf.set_text_color(255, 255, 255)
        pdf.cell(55, 8, "Aprasymas", border=1, fill=True)
        pdf.cell(18, 8, "Kiekis", border=1, align="C", fill=True)
        pdf.cell(28, 8, "Kaina be PVM", border=1, align="C", fill=True)
        pdf.cell(18, 8, "PVM %", border=1, align="C", fill=True)
        pdf.cell(28, 8, "PVM suma", border=1, align="C", fill=True)
        pdf.cell(28, 8, "Suma", border=1, align="C", fill=True)
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

        # Table rows
        pdf.set_font("Helvetica", "", 9)
        calc_subtotal = 0.0
        calc_vat = 0.0
        calc_total = 0.0

        for i, item in enumerate(items):
            desc = safe_text(str(item.get("description", ""))[:35])
            qty = float(item.get("qty") or 0)
            
            net = float(item.get("net") or item.get("price") or 0)
            vat_rate = float(item.get("vatRate") or 21)
            vat_amount = float(item.get("vatAmount") or (net * qty * vat_rate / 100))
            total = float(item.get("total") or (net * qty + vat_amount))
            
            line_net = net * qty
            calc_subtotal += line_net
            calc_vat += vat_amount
            calc_total += total

            # Alternating row colors
            if i % 2 == 0:
                pdf.set_fill_color(250, 250, 250)
            else:
                pdf.set_fill_color(255, 255, 255)
            
            pdf.cell(55, 7, desc, border=1, fill=True)
            pdf.cell(18, 7, f"{qty:.0f}", border=1, align="C", fill=True)
            pdf.cell(28, 7, f"{net:.2f} EUR", border=1, align="R", fill=True)
            pdf.cell(18, 7, f"{vat_rate:.0f}%", border=1, align="C", fill=True)
            pdf.cell(28, 7, f"{vat_amount:.2f} EUR", border=1, align="R", fill=True)
            pdf.cell(28, 7, f"{total:.2f} EUR", border=1, align="R", fill=True)
            pdf.ln()

        # Use provided totals or calculated ones
        final_subtotal = subtotal if subtotal > 0 else calc_subtotal
        final_vat = vat_total if vat_total > 0 else calc_vat
        final_total = grand_total if grand_total > 0 else calc_total

        # ========== TOTALS SECTION ==========
        pdf.ln(5)
        pdf.set_font("Helvetica", "", 10)
        
        # Right-aligned totals
        pdf.cell(147, 7, "Suma be PVM:", align="R")
        pdf.cell(28, 7, f"{final_subtotal:.2f} EUR", align="R", border=0)
        pdf.ln()
        
        pdf.cell(147, 7, "PVM suma:", align="R")
        pdf.cell(28, 7, f"{final_vat:.2f} EUR", align="R", border=0)
        pdf.ln()
        
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_fill_color(46, 204, 113)  # Green total
        pdf.set_text_color(255, 255, 255)
        pdf.cell(147, 9, "BENDRA SUMA:", align="R")
        pdf.cell(28, 9, f"{final_total:.2f} EUR", align="R", fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(15)

        # ========== FOOTER ==========
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 6, "Dekojame uz bendradarbiavima!", ln=True, align="C")
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(0, 5, f"Saskaita sugeneruota: {date_str}", ln=True, align="C")

        # Output to bytes
        pdf_bytes = pdf.output()
        buffer = io.BytesIO(pdf_bytes)
        buffer.seek(0)

        filename = f"{invoice_series}-{invoice_number}.pdf"
        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        print("PDF GENERATION ERROR:")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# Expose app globally for Vercel
# Vercel will use this as the entry point

# For local development
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

# Vercel Force Update: Clients Module
