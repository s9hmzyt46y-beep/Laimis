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

# Max content length: 10MB for Vercel serverless
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

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


def resize_image_for_api(img, max_size=1500):
    """
    Resize image to reduce payload size while maintaining quality.
    Max dimension is 1500px by default.
    """
    width, height = img.size
    
    if width > max_size or height > max_size:
        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))
        
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    return img


@app.route('/scan-receipt', methods=['POST'])
def scan_receipt():
    """
    Route to scan receipt images using OpenAI Vision API (GPT-4o - best model).
    Serverless version: processes files from memory only (no disk saving).
    Includes image resizing for Vercel payload limits.
    """
    # Define valid categories - MUST match frontend dropdown options exactly
    VALID_CATEGORIES = ["Maistas", "Transportas", "Nuoma", "Komunaliniai", "Biuras", "Švara", "Buitinė chemija", "Paslaugos", "Kiti"]

    try:
        print("--- STARTING SCAN ---")
        
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({"error": "Nepateiktas failas"}), 400
        
        file = request.files['file']
        
        if not file.filename:
            return jsonify({"error": "Tuščias failas"}), 400
        
        # Get file extension
        filename = file.filename
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        # Validate file extension
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
        if file_ext not in ALLOWED_EXTENSIONS:
            return jsonify({"error": f"Netinkamas failo formatas. Leidžiami: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
        
        # Read file into memory (no disk saving for serverless)
        file_bytes = file.read()
        
        # Check file size (max 5MB for images to avoid Vercel limits)
        file_size_mb = len(file_bytes) / (1024 * 1024)
        print(f"File size: {file_size_mb:.2f} MB")
        
        if file_size_mb > 5:
            return jsonify({"error": "Failas per didelis. Maksimalus dydis: 5MB"}), 400
        
        # Generate a unique filename for response (not saved to disk)
        from datetime import datetime
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"receipt_{timestamp}.{file_ext}"
        
        # STEP 2: Preprocess and resize image for better OCR accuracy
        try:
            if Image is None:
                # Fallback: use original image if PIL not available
                base64_image = base64.b64encode(file_bytes).decode('utf-8')
                mime_type = 'image/jpeg'
            elif file_ext == 'pdf':
                # PDF: Convert to image first, then preprocess
                if fitz is None:
                    return jsonify({"error": "PDF apdorojimui reikalingas PyMuPDF"}), 400
                
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                page = doc.load_page(0)
                # Higher resolution for PDF
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                doc.close()
                
                # Open PDF image and preprocess
                img = Image.open(io.BytesIO(img_data))
                img = resize_image_for_api(img, max_size=2000)  # Larger for PDF
                img = img.convert('RGB')  # Convert to RGB (no grayscale for better color recognition)
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.5)  # Moderate contrast
                img = img.filter(ImageFilter.SHARPEN)  # Sharpen
                
                # Save to buffer as JPEG (smaller than PNG)
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                processed_bytes = buffer.getvalue()
                base64_image = base64.b64encode(processed_bytes).decode('utf-8')
                mime_type = 'image/jpeg'
            else:
                # Image file: Preprocess directly
                img = Image.open(io.BytesIO(file_bytes))
                img = resize_image_for_api(img, max_size=1500)  # Resize for API
                img = img.convert('RGB')  # Keep colors for better recognition
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.3)  # Light contrast boost
                img = img.filter(ImageFilter.SHARPEN)  # Sharpen
                
                # Save to buffer as JPEG (smaller than PNG)
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                processed_bytes = buffer.getvalue()
                base64_image = base64.b64encode(processed_bytes).decode('utf-8')
                mime_type = 'image/jpeg'
            
            # Log processed image size
            processed_size_kb = len(processed_bytes) / 1024
            print(f"Processed image size: {processed_size_kb:.1f} KB")
                
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
                return jsonify({"error": "OpenAI API raktas nesukonfigūruotas"}), 500
            try:
                client = OpenAI(api_key=api_key)
            except Exception as e:
                print(f"OpenAI client initialization error: {e}")
                return jsonify({"error": f"Nepavyko inicializuoti OpenAI: {str(e)}"}), 500
        
        # STEP 3: Build system prompt for Lithuanian receipt digitization - ULTRA PRECISE
        STRICT_CATEGORIES = ["Maistas", "Transportas", "Nuoma", "Komunaliniai", "Biuras", "Švara", "Buitinė chemija", "Paslaugos", "Kiti"]
        
        system_prompt = f"""# LIETUVIŠKŲ ČEKIŲ OCR ROBOTAS - 100% TIKSLUMAS

Tu esi PROFESIONALUS lietuviškų čekių skaitytuvas. Tavo VIENINTELĖ užduotis - TIKSLIAI perskaityti kiekvieną simbolį.

## ⚠️ GRIEŽTOS TAISYKLĖS:

### 1. TEKSTAS TURI BŪTI TIKSLUS
- Kopijuok produktų pavadinimus TIKSLIAI kaip jie parašyti čekyje
- NEKEISK žodžių, NEVERSK į anglų kalbą
- Jei matai "PIENAS 2.5%" - rašyk "PIENAS 2.5%", NE "milk"
- Jei matai "DUONA BALTA" - rašyk "DUONA BALTA", NE "white bread"
- Jei matai sutrumpinimą kaip "POM.TRINT.680G" - rašyk tiksliai taip

### 2. LIETUVIŠKI ČEKIŲ FORMATAI
Tipinis lietuviškas čekis:
```
UAB MAXIMA LT
Pirkimo data: 2024-12-15
--------------------------
PIENAS 2.5% 1L          1.29
DUONA BALTA             0.89
SVIESTAS 82%            2.49
--------------------------
VISO:                   4.67
PVM 21%:                0.81
```

### 3. KAIP SKAITYTI EILUTES
Kiekviena eilutė paprastai yra: [PRODUKTO PAVADINIMAS] [KAINA]
- Pavadinimas gali turėti skaičius (pvz., "2.5%", "500G")
- Kaina visada dešinėje pusėje
- Ignoruok kiekį ir vienetų kainas - imk TIK galutinę kainą

### 4. KATEGORIJOS (PRIVALOMA naudoti TIK šias):
{STRICT_CATEGORIES}

Kategorijų logika:
- Bet koks maistas/gėrimas → "Maistas"
- Degalai, parkavimas → "Transportas"  
- Plovikliai, šampūnai, higiena → "Buitinė chemija"
- Popierius, rašikliai → "Biuras"
- Elektra, vanduo, internetas → "Komunaliniai"
- Nuoma → "Nuoma"
- Valymo paslaugos → "Švara"
- Kitos paslaugos → "Paslaugos"
- Visa kita → "Kiti"

### 5. JSON FORMATAS
```json
{{
  "items": [
    {{
      "vendor": "Maxima",
      "date": "2024-12-15",
      "description": "PIENAS 2.5% 1L",
      "amount": 1.29,
      "vat_amount": 0.22,
      "net_amount": 1.07,
      "category": "Maistas"
    }}
  ]
}}
```

### 6. PVM SKAIČIAVIMAS
- Lietuvoje standartinis PVM = 21%
- Jei amount = 1.29, tai:
  - net_amount = 1.29 / 1.21 = 1.07
  - vat_amount = 1.29 - 1.07 = 0.22

### 7. PARDUOTUVIŲ ATPAŽINIMAS
- "UAB MAXIMA LT" → "Maxima"
- "LIDL LIETUVA" → "Lidl"
- "IKI" → "Iki"
- "RIMI LIETUVA" → "Rimi"
- "CIRCLE K" → "Circle K"
- "VIADA" → "Viada"

## ❌ KO NEDARYTI:
- NEVERSK produktų į anglų kalbą
- NESUGALVOK produktų pavadinimų - jei nematai, nerašyk
- NESUMUOK kelių produktų į vieną
- NEPRALEISK jokių eilučių
- NEINTERPRETUOK - tik kopijuok

## ✅ KĄ DARYTI:
- Kopijuok TIKSLIAI simbolis po simbolio kaip parašyta
- Išlaikyk didžiąsias/mažąsias raides kaip originale
- Išlaikyk sutrumpinimus (pvz. "POM.TRINT." ne "Pomidorų trintukas")
- Išlaikyk skaičius ir vienetų matavimus (pvz. "500G", "2.5%", "1L")
- Jei matai "PIENAS ROKIŠKIO 2.5% 1L" - rašyk tiksliai taip, ne "Pienas"
- Jei neįskaitoma - PRALEISK, bet NESUGALVOK

## 🔍 PAVYZDŽIAI:
Čekyje: "SVIEST.ROKIŠKIO 82% 200G" → description: "SVIEST.ROKIŠKIO 82% 200G"
Čekyje: "BATON.ŠALD.VIRTA 400G" → description: "BATON.ŠALD.VIRTA 400G"  
Čekyje: "DUONA BALTA VILNIAUS" → description: "DUONA BALTA VILNIAUS"
Čekyje: "KEFYRAS 2.5% 1L" → description: "KEFYRAS 2.5% 1L"

NEGALIMA: "Pienas", "Sviestas", "Duona" - tai PER TRUMPA! Kopijuok visą eilutę."""
        
        # User prompt - very specific
        user_prompt = """TIKSLIAI nuskaityk šį lietuvišką čekį kaip OCR skaitytuvas.

INSTRUKCIJOS:
1. Rask parduotuvės pavadinimą viršuje (pvz. MAXIMA, LIDL, IKI)
2. Rask datą (formatas YYYY-MM-DD)
3. Kiekvieną produkto eilutę KOPIJUOK SIMBOLIS PO SIMBOLIO:
   - Išlaikyk VISUS žodžius, skaičius, sutrumpinimus
   - Pvz. "SVIEST.ROKIŠKIO 82% 200G" → būtent taip, ne "Sviestas"
   - Pvz. "KEFYRAS VILKYŠKIŲ 2.5% 1L" → būtent taip, ne "Kefyras"
4. Kainą imk iš dešinės pusės
5. Kategoriją priskirk pagal produkto tipą

⚠️ KRITIŠKAI SVARBU:
- description = TIKSLUS čekio tekstas, ne sutrumpinimas
- Jei čekyje parašyta "DUONA BALTA VILNIAUS 400G" - grąžink tiksliai tai
- NEGALIMA grąžinti tik "Duona" ar "Pienas" - tai per trumpa!
- Grąžink JSON su visais produktais."""

        # API Call with JSON response format - using GPT-4o (best vision model)
        print("Calling OpenAI API with GPT-4o...")
        try:
            completion = client.chat.completions.create(
                model="gpt-4o",  # Best model for vision tasks
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
                                    "detail": "high"  # High detail for better OCR
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
        except Exception as api_error:
            print(f"OpenAI API Error: {api_error}")
            error_msg = str(api_error)
            if "rate_limit" in error_msg.lower():
                return jsonify({"error": "API limitas pasiektas. Bandykite vėliau."}), 429
            elif "invalid_api_key" in error_msg.lower():
                return jsonify({"error": "Neteisingas API raktas"}), 401
            elif "content_policy" in error_msg.lower():
                return jsonify({"error": "Vaizdas neatitinka turinio politikos"}), 400
            else:
                return jsonify({"error": f"AI klaida: {error_msg[:200]}"}), 500
        
        # Get raw content from AI response
        raw_content = completion.choices[0].message.content
        
        # Print what AI actually sent
        print(f"DEBUG AI RAW: {raw_content[:500]}...")
        
        # Cleaning Logic
        clean_json = re.sub(r'```json|```', '', raw_content).strip()
        
        # Parse JSON
        try:
            data = json.loads(clean_json)
            print(f"DEBUG Parsed Data: {type(data)}")
        except json.JSONDecodeError as je:
            print(f"JSON PARSE ERROR: {je}")
            return jsonify({"error": f"AI grąžino neteisingą formatą. Bandykite dar kartą."}), 500
        
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
            if not isinstance(item, dict):
                continue
                
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
                    amount_str = item['total_amount'].replace('€', '').replace('$', '').replace(',', '.').strip()
                    try:
                        item['total_amount'] = float(amount_str)
                    except ValueError:
                        continue  # Skip items with invalid amounts
            
            # Handle vat_amount
            if 'vat_amount' not in item:
                item['vat_amount'] = 0.0
            elif isinstance(item['vat_amount'], str):
                vat_str = item['vat_amount'].replace('€', '').replace('$', '').replace(',', '.').strip()
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
                net_str = item['net_amount'].replace('€', '').replace('$', '').replace(',', '.').strip()
                try:
                    item['net_amount'] = float(net_str) if net_str else 0.0
                except ValueError:
                    total = float(item.get('total_amount', 0))
                    vat = float(item.get('vat_amount', 0))
                    item['net_amount'] = total - vat
            
            # STRICT Category Validation with Lithuanian keyword support
            original_category = item.get('category', '').strip()
            description_lower = item.get('description', '').lower()
            
            if original_category not in VALID_CATEGORIES:
                category_lower = original_category.lower()
                matched_category = None
                
                # Try exact case-insensitive match
                for valid_cat in VALID_CATEGORIES:
                    if valid_cat.lower() == category_lower:
                        matched_category = valid_cat
                        break
                
                # Intelligent fallback with Lithuanian keywords
                if not matched_category:
                    # Combined text for keyword matching
                    search_text = f"{category_lower} {description_lower}"
                    
                    # Lithuanian food keywords
                    food_keywords = [
                        'maistas', 'food', 'grocer', 'restaurant', 'cafe', 'meal', 'snack',
                        'duona', 'pienas', 'sviestas', 'kiaušin', 'mėsa', 'višt', 'kiaul', 'jautien',
                        'žuvis', 'lašiš', 'sūris', 'varškė', 'grietin', 'jogurt', 'kefyr',
                        'alus', 'vynas', 'sult', 'vanduo', 'kava', 'arbata', 'gėrim',
                        'cukrus', 'druska', 'milt', 'ryži', 'makaron', 'bulv', 'mork',
                        'svogūn', 'pomidor', 'agurk', 'obuol', 'banan', 'apelsin',
                        'saldain', 'šokolad', 'led', 'pyrag', 'bandel', 'sumuštini',
                        'maxima', 'iki', 'lidl', 'rimi', 'norfa', 'bread', 'milk', 'cheese',
                        'kebab', 'pica', 'pizza', 'burger', 'kavin', 'restoran'
                    ]
                    
                    # Lithuanian transport keywords
                    transport_keywords = [
                        'transportas', 'fuel', 'gas', 'parking', 'transport', 'car', 'taxi',
                        'degalai', 'benzin', 'dyzel', 'diesel', 'parkav', 'plovykl',
                        'tepal', 'aušin', 'circle k', 'viada', 'orlen', 'neste',
                        'autoservis', 'autobus', 'traukin', 'taksi'
                    ]
                    
                    # Lithuanian household chemicals keywords
                    chemistry_keywords = [
                        'buitin', 'chemij', 'detergent', 'soap', 'shampoo', 'washing', 'chemical', 'hygiene', 'household',
                        'skalbim', 'plovikl', 'valikl', 'dezodorant', 'šampūn', 'muil',
                        'dantų past', 'tualetinis popier', 'servetėl', 'kapsul', 'minkštikl',
                        'balikl', 'higienos', 'wc', 'grindų'
                    ]
                    
                    # Lithuanian office keywords
                    office_keywords = [
                        'office', 'stationery', 'paper', 'pen', 'printer', 'biuras',
                        'popier', 'rašikl', 'sąsiuvin', 'segtuk', 'vokai', 'spausdint', 'rašal',
                        'kanceliar'
                    ]
                    
                    # Lithuanian utilities keywords
                    utilities_keywords = [
                        'utility', 'electric', 'water', 'internet', 'phone', 'komunalin',
                        'elektr', 'vanden', 'duj', 'šildym', 'telefon', 'telia', 'tele2', 'bite'
                    ]
                    
                    # Check keywords
                    if any(kw in search_text for kw in food_keywords):
                        matched_category = 'Maistas'
                    elif any(kw in search_text for kw in transport_keywords):
                        matched_category = 'Transportas'
                    elif any(kw in search_text for kw in chemistry_keywords):
                        matched_category = 'Buitinė chemija'
                    elif any(kw in search_text for kw in office_keywords):
                        matched_category = 'Biuras'
                    elif any(kw in search_text for kw in utilities_keywords):
                        matched_category = 'Komunaliniai'
                    elif any(kw in search_text for kw in ['clean', 'valym', 'švara']):
                        matched_category = 'Švara'
                    elif any(kw in search_text for kw in ['rent', 'lease', 'nuom', 'būst']):
                        matched_category = 'Nuoma'
                    elif any(kw in search_text for kw in ['service', 'repair', 'paslaug', 'remont', 'konsult']):
                        matched_category = 'Paslaugos'
                
                # Final fallback to 'Kiti'
                if not matched_category:
                    matched_category = 'Kiti'
                    print(f"⚠ Category fallback: '{original_category}' (desc: {description_lower[:30]}) → 'Kiti'")
                
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
        return jsonify({"error": f"Serverio klaida: {str(e)[:200]}"}), 500


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

# Vercel Force Update: v2.1 - Better error handling and image resize
