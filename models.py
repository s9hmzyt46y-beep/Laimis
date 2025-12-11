"""
Database Models for Mano Startuolis Accounting System

This module defines the database structure for managing clients, invoices, and invoice items.
We use SQLAlchemy (Flask-SQLAlchemy) because it provides an easy way to work with databases
in Python without writing raw SQL queries. This makes the code more readable and maintainable.
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from decimal import Decimal

# We create a db instance here that will be initialized in the Flask app
# This is a common pattern - we define the db object here so models can import it
# without creating circular imports
db = SQLAlchemy()


class Client(db.Model):
    """
    Client (Klientas) Model
    
    Represents a customer or client in the system. We store basic information
    about clients so we can associate invoices with them. This is a fundamental
    entity in accounting - every invoice must belong to a client.
    
    Why we need this:
    - To track who we're billing
    - To maintain client contact information
    - To generate reports by client
    - To ensure data integrity (invoices must reference valid clients)
    """
    
    # We use __tablename__ to explicitly set the table name
    # This is optional but makes it clear what the database table will be called
    __tablename__ = 'clients'
    
    # Primary key: unique identifier for each client
    # We use Integer because it's simple and efficient for auto-incrementing IDs
    id = db.Column(db.Integer, primary_key=True)
    
    # Client name - required field
    # We use String(100) to limit length and prevent extremely long names
    # nullable=False means this field cannot be empty (required)
    name = db.Column(db.String(100), nullable=False)
    
    # Email for contacting the client
    # We allow it to be nullable because some clients might not have email
    # String(120) is slightly longer than name to accommodate email addresses
    email = db.Column(db.String(120), nullable=True)
    
    # Phone number for contacting the client
    # String type (not Integer) because phone numbers can have +, -, spaces, etc.
    phone = db.Column(db.String(20), nullable=True)
    
    # Company registration number (if applicable)
    # In Lithuania, this is called "Įmonės kodas" or "PVM kodas"
    # We store as string because it might contain letters or special formatting
    company_code = db.Column(db.String(20), nullable=True)
    
    # Address for billing purposes
    # We use Text instead of String for longer addresses
    address = db.Column(db.Text, nullable=True)
    
    # Timestamp when the client record was created
    # We use datetime.utcnow (without parentheses) so it's called when record is created
    # This helps us track when clients were added to the system
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship: one client can have many invoices
    # This creates a virtual column that lets us access all invoices for a client
    # like: client.invoices (returns list of Invoice objects)
    # backref creates a reverse relationship: invoice.client (returns Client object)
    # lazy='dynamic' means we get a query object instead of loading all invoices at once
    # This is better for performance when clients have many invoices
    invoices = db.relationship('Invoice', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        """
        String representation of the Client object.
        
        This is useful for debugging - when you print a Client object,
        you'll see something like: <Client John Doe> instead of <Client object at 0x...>
        """
        return f'<Client {self.name}>'
    
    def to_dict(self):
        """
        Convert Client object to dictionary.
        
        This is useful when we need to send client data as JSON (for APIs or frontend).
        We convert datetime to string because JSON doesn't support datetime objects.
        """
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'company_code': self.company_code,
            'address': self.address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Invoice(db.Model):
    """
    Invoice (Sąskaita faktūra) Model
    
    Represents a bill or invoice sent to a client. This is the core document
    in accounting - it records what services/products were provided and how much
    the client owes. Each invoice belongs to one client and can have multiple items.
    
    Why we need this:
    - To track what we've billed clients
    - To record payment status
    - To generate invoice documents
    - To calculate totals and taxes
    - To maintain accounting records for tax purposes
    """
    
    __tablename__ = 'invoices'
    
    # Primary key: unique identifier for each invoice
    id = db.Column(db.Integer, primary_key=True)
    
    # Invoice number - unique identifier visible to clients
    # We use String because invoice numbers often have prefixes like "INV-2024-001"
    # unique=True ensures no two invoices have the same number
    # nullable=False makes it required
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # Foreign key: links this invoice to a client
    # db.ForeignKey references the 'clients.id' column
    # nullable=False means every invoice must belong to a client
    # ondelete='CASCADE' means if a client is deleted, their invoices are deleted too
    # This prevents orphaned invoices (invoices without a client)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # Invoice date - when the invoice was issued
    # We use Date (not DateTime) because we typically only care about the day
    # default=datetime.utcnow.date() sets today's date as default
    invoice_date = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)
    
    # Due date - when payment is expected
    # This helps track which invoices are overdue
    due_date = db.Column(db.Date, nullable=True)
    
    # Payment date - when the invoice was actually paid
    # This is nullable because invoices might not be paid yet
    # We track this separately from status to have precise payment tracking
    payment_date = db.Column(db.Date, nullable=True)
    
    # Payment status - tracks if invoice has been paid
    # We use String with choices instead of Boolean because we might want:
    # 'pending', 'paid', 'overdue', 'cancelled', etc.
    # Default is 'pending' (not paid yet)
    status = db.Column(db.String(20), default='pending', nullable=False)
    
    # Notes or additional information about the invoice
    # Text type allows for longer descriptions
    notes = db.Column(db.Text, nullable=True)
    
    # Total amount - stored amount for the invoice
    # We use Float to store the invoice total amount
    # nullable=False means every invoice must have an amount (defaults to 0.0)
    # default=0.0 ensures new invoices start with zero amount
    amount = db.Column(db.Float, nullable=False, default=0.0)
    
    # Timestamp when invoice was created in the system
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # RELATIONSHIP TO CLIENT:
    # ======================
    #
    # The Invoice model has a relationship to Client through:
    # 1. Foreign Key: client_id (line 136) - stores the ID number
    # 2. Relationship: Created via backref in Client model
    #
    # HOW db.relationship WORKS:
    # ========================
    #
    # db.relationship() creates a Python property that lets you access related objects
    # without writing SQL JOIN queries manually.
    #
    # In the Client model (line 75), we have:
    #   invoices = db.relationship('Invoice', backref='client', ...)
    #
    # This creates TWO relationships:
    #
    # 1. client.invoices - Access all invoices for a client
    #    Example: client = Client.query.get(1)
    #             all_invoices = client.invoices.all()  # Gets all invoices for this client
    #
    # 2. invoice.client - Access the client for an invoice (via backref)
    #    Example: invoice = Invoice.query.get(1)
    #             client = invoice.client  # Gets the Client object linked to this invoice
    #             client_name = invoice.client.name  # Access client's name
    #
    # WHAT backref DOES:
    # ================
    #
    # backref='client' automatically creates a reverse relationship.
    # - We define the relationship in Client model: invoices = db.relationship(...)
    # - backref creates the opposite: invoice.client (without defining it in Invoice model)
    # - This is convenient - we only define it once, get both directions
    #
    # WITHOUT relationship (manual way):
    #   invoice = Invoice.query.get(1)
    #   client = Client.query.get(invoice.client_id)  # Manual lookup
    #
    # WITH relationship (automatic):
    #   invoice = Invoice.query.get(1)
    #   client = invoice.client  # SQLAlchemy does the lookup automatically
    #
    # WHY THIS IS USEFUL:
    # ==================
    # - Cleaner code: invoice.client.name instead of Client.query.get(invoice.client_id).name
    # - Automatic: SQLAlchemy handles the SQL JOIN for you
    # - Efficient: Can be optimized with lazy loading
    # - Type-safe: Your IDE knows invoice.client is a Client object
    
    # Relationship: one invoice can have many items
    # This lets us access invoice.items to get all items on this invoice
    # cascade='all, delete-orphan' means if invoice is deleted, items are deleted too
    # order_by sorts items by id (so they appear in creation order)
    items = db.relationship('InvoiceItem', backref='invoice', lazy='dynamic', 
                           cascade='all, delete-orphan', order_by='InvoiceItem.id')
    
    def __repr__(self):
        """String representation for debugging."""
        return f'<Invoice {self.invoice_number}>'
    
    def calculate_total(self):
        """
        Calculate GRAND TOTAL amount for this invoice (including VAT).
        
        We calculate this dynamically (not stored in database) because:
        1. It's always accurate - if items change, total updates automatically
        2. Reduces data duplication (single source of truth)
        3. Prevents inconsistencies if someone manually edits the database
        
        Returns the sum of all item totals including VAT (grand total).
        
        NOTE: We use Decimal for calculations because unit_price is stored as
        Numeric(10, 2) which returns Decimal type. We need to convert quantity
        to Decimal before multiplying to avoid TypeError.
        """
        # Initialize total as Decimal(0) for precise calculations
        total = Decimal('0')
        # We iterate through all items and sum their totals with VAT
        # Each item calculates: (quantity * unit_price) + vat_amount
        for item in self.items:
            # Use the total_with_vat property which handles all Decimal conversions
            item_total = Decimal(str(item.total_with_vat))
            total += item_total
        # Convert back to float for return value (maintains compatibility)
        return float(total)
    
    def calculate_totals_breakdown(self):
        """
        Calculate detailed breakdown of invoice totals.
        
        Returns a dictionary with:
        - subtotal: Sum of all items without VAT
        - vat_total: Sum of all VAT amounts
        - grand_total: Sum of all items with VAT (subtotal + vat_total)
        
        All calculations use Decimal for precision to avoid floating point errors.
        This is critical for financial calculations where precision matters.
        
        Returns:
            dict: {
                'subtotal': float,
                'vat_total': float,
                'grand_total': float
            }
        """
        # Initialize all totals as Decimal(0) for precise calculations
        subtotal = Decimal('0')
        vat_total = Decimal('0')
        
        # Iterate through all items and calculate subtotals and VAT
        for item in self.items:
            # Calculate item subtotal (quantity * unit_price) without VAT
            quantity_decimal = Decimal(str(item.quantity))
            unit_price_decimal = Decimal(str(item.unit_price)) if not isinstance(item.unit_price, Decimal) else item.unit_price
            item_subtotal = quantity_decimal * unit_price_decimal
            subtotal += item_subtotal
            
            # Calculate item VAT amount
            vat_rate_decimal = Decimal(str(item.vat_rate))
            item_vat = (item_subtotal * vat_rate_decimal) / Decimal('100')
            vat_total += item_vat
        
        # Calculate grand total (subtotal + VAT)
        grand_total = subtotal + vat_total
        
        # Return as dictionary with float values (for JSON serialization compatibility)
        return {
            'subtotal': float(subtotal),
            'vat_total': float(vat_total),
            'grand_total': float(grand_total)
        }
    
    def to_dict(self):
        """
        Convert Invoice object to dictionary with calculated total.
        
        We include the calculated total so frontend/API consumers
        don't need to calculate it themselves.
        """
        return {
            'id': self.id,
            'invoice_number': self.invoice_number,
            'client_id': self.client_id,
            'client_name': self.client.name if self.client else None,  # Include client name for convenience
            'invoice_date': self.invoice_date.isoformat() if self.invoice_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'total': self.calculate_total(),  # Include calculated total
            'items_count': self.items.count()  # Number of items for quick reference
        }


class InvoiceItem(db.Model):
    """
    Invoice Item (Paslauga/Prekė sąskaitoje) Model
    
    Represents a single line item on an invoice. Each invoice can have multiple
    items (e.g., "Web Development - 10 hours", "Hosting - 1 month"). This allows
    us to break down what the client is being charged for.
    
    Why we need this:
    - To itemize what's on each invoice (detailed billing)
    - To calculate invoice totals (sum of all items)
    - To track different services/products separately
    - To allow different prices and quantities per item
    - To generate detailed invoice documents
    """
    
    __tablename__ = 'invoice_items'
    
    # Primary key: unique identifier for each item
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign key: links this item to an invoice
    # Every item must belong to an invoice
    # ondelete='CASCADE' means if invoice is deleted, items are deleted too
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    
    # Description of the service or product
    # This is what appears on the invoice line item
    # nullable=False because every item needs a description
    description = db.Column(db.String(200), nullable=False)
    
    # Quantity - how many units of this item
    # We use Float instead of Integer because quantities can be fractional
    # (e.g., 2.5 hours of work, 0.5 months of service)
    # nullable=False with default=1.0 means if not specified, assume 1 unit
    quantity = db.Column(db.Float, nullable=False, default=1.0)
    
    # Unit price - price per unit
    # We use Numeric(10, 2) which stores exactly 2 decimal places
    # This is important for money - we need precise decimal calculations
    # 10 digits total, 2 after decimal point (e.g., 99999999.99)
    # nullable=False because we can't calculate total without price
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Optional: tax rate for this item (e.g., 21 for 21% VAT)
    # We store as Float to allow decimal percentages if needed
    # nullable=True because some items might be tax-exempt
    tax_rate = db.Column(db.Float, nullable=True, default=0.0)
    
    # VAT rate (PVM) for this item - standard Lithuanian VAT is 21%
    # We use Integer because VAT rates are typically whole numbers (0, 5, 9, 21)
    # Default is 21% which is the standard VAT rate in Lithuania
    # nullable=False with default=21 means every item has VAT unless explicitly set to 0
    vat_rate = db.Column(db.Integer, nullable=False, default=21)
    
    # Discount percentage for this item
    # Represents a percentage discount (e.g., 10 means 10% off)
    # Default is 0 (no discount)
    # We use Float to allow decimal discounts if needed (e.g., 5.5%)
    # nullable=False with default=0.0 means every item has no discount unless explicitly set
    discount = db.Column(db.Float, nullable=False, default=0.0)
    
    # Timestamp when item was added
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        """String representation for debugging."""
        return f'<InvoiceItem {self.description}>'
    
    def calculate_subtotal(self):
        """
        Calculate subtotal for this item (quantity * unit_price).
        
        We calculate this as a method instead of storing it because:
        1. It's always accurate - automatically updates if quantity/price changes
        2. Prevents data inconsistency
        3. Simple calculation, no need to store redundant data
        
        Returns the subtotal before tax.
        
        NOTE: We use Decimal for calculations because unit_price is stored as
        Numeric(10, 2) which returns Decimal type. We need to convert quantity
        to Decimal before multiplying to avoid TypeError.
        """
        # Convert both quantity and unit_price to Decimal before multiplying
        # This prevents TypeError: unsupported operand type(s) for *: 'float' and 'decimal.Decimal'
        quantity_decimal = Decimal(str(self.quantity))
        unit_price_decimal = Decimal(str(self.unit_price)) if not isinstance(self.unit_price, Decimal) else self.unit_price
        subtotal = quantity_decimal * unit_price_decimal
        return float(subtotal)
    
    def calculate_total_with_tax(self):
        """
        Calculate total for this item including tax.
        
        Formula: subtotal + (subtotal * tax_rate / 100)
        Example: If subtotal is 100 and tax_rate is 21, result is 121
        
        Returns the total including tax.
        """
        subtotal = self.calculate_subtotal()
        if self.tax_rate:
            tax_amount = subtotal * (self.tax_rate / 100.0)
            return subtotal + tax_amount
        return subtotal
    
    @property
    def vat_amount(self):
        """
        Calculate VAT amount for this item.
        
        Formula: (price * quantity * vat_rate) / 100
        
        Uses Decimal for precise calculations to avoid floating point errors.
        
        Returns the VAT amount as a float.
        """
        # Calculate subtotal first (quantity * unit_price)
        quantity_decimal = Decimal(str(self.quantity))
        unit_price_decimal = Decimal(str(self.unit_price)) if not isinstance(self.unit_price, Decimal) else self.unit_price
        subtotal = quantity_decimal * unit_price_decimal
        
        # Calculate VAT: (subtotal * vat_rate) / 100
        vat_rate_decimal = Decimal(str(self.vat_rate))
        vat_amount = (subtotal * vat_rate_decimal) / Decimal('100')
        
        return float(vat_amount)
    
    @property
    def total_with_vat(self):
        """
        Calculate total for this item including VAT.
        
        Formula: (price * quantity) + vat_amount
        
        Uses Decimal for precise calculations.
        
        Returns the total including VAT as a float.
        """
        # Calculate subtotal (price * quantity)
        quantity_decimal = Decimal(str(self.quantity))
        unit_price_decimal = Decimal(str(self.unit_price)) if not isinstance(self.unit_price, Decimal) else self.unit_price
        subtotal = quantity_decimal * unit_price_decimal
        
        # Add VAT amount
        vat_rate_decimal = Decimal(str(self.vat_rate))
        vat_amount = (subtotal * vat_rate_decimal) / Decimal('100')
        total = subtotal + vat_amount
        
        return float(total)
    
    def to_dict(self):
        """
        Convert InvoiceItem object to dictionary with calculated values.
        
        We include calculated subtotals and totals so consumers
        don't need to recalculate them.
        """
        return {
            'id': self.id,
            'invoice_id': self.invoice_id,
            'description': self.description,
            'quantity': float(self.quantity),
            'unit_price': float(self.unit_price),
            'tax_rate': float(self.tax_rate) if self.tax_rate else 0.0,
            'vat_rate': int(self.vat_rate),
            'subtotal': self.calculate_subtotal(),
            'vat_amount': self.vat_amount,
            'total_with_tax': self.calculate_total_with_tax(),
            'total_with_vat': self.total_with_vat,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Expense(db.Model):
    """
    Expense (Išlaidos) Model
    
    Represents an expense or cost incurred by the business. This allows tracking
    of all business expenses for accounting and tax purposes. Each expense can
    have a receipt/image attached for documentation.
    
    Why we need this:
    - To track business expenses for accounting
    - To maintain records for tax deductions
    - To categorize expenses for reporting
    - To attach receipts/images as proof of purchase
    - To calculate total expenses for financial analysis
    
    CATEGORIES:
    ==========
    
    Predefined categories for better organization:
    - 'Maistas' - Food and meals
    - 'Transportas' - Transportation costs
    - 'Nuoma' - Rent
    - 'Komunaliniai' - Utilities (electricity, water, etc.)
    - 'Biuras' - Office expenses
    - 'Paslaugos' - Services
    - 'Kita' - Other expenses
    """
    
    __tablename__ = 'expenses'
    
    # Primary key: unique identifier for each expense
    id = db.Column(db.Integer, primary_key=True)
    
    # Expense date - when the expense was incurred
    # We use Date (not DateTime) because we typically only care about the day
    # default=datetime.utcnow().date sets today's date as default
    date = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)
    
    # Category - predefined category for the expense
    # We use String(50) to limit length
    # Categories: 'Maistas', 'Transportas', 'Nuoma', 'Komunaliniai', 'Biuras', 'Paslaugos', 'Kita'
    category = db.Column(db.String(50), nullable=False)
    
    # Vendor - where the expense was made (e.g., "Maxima", "Circle K", "UAB Example")
    # We use String(100) to accommodate vendor names
    vendor = db.Column(db.String(100), nullable=False)
    
    # Amount - the cost of the expense (total price including VAT)
    # We use Numeric(10, 2) for precise decimal calculations (like money)
    # 10 digits total, 2 after decimal point (e.g., 99999999.99)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    
    # VAT Amount - the VAT portion of the expense
    # We use Float for VAT amount (defaults to 0.0 if not specified)
    # This allows tracking VAT separately from the total amount
    vat_amount = db.Column(db.Float, default=0.0, nullable=False)
    
    # Description - optional details about the expense
    # Text type allows for longer descriptions
    description = db.Column(db.Text, nullable=True)
    
    # File path - stores the filename of uploaded receipt/image
    # We store just the filename, not the full path
    # The actual file is stored in static/uploads/ directory
    # nullable=True because not all expenses may have receipts
    file_path = db.Column(db.String(255), nullable=True)
    
    # Timestamp when expense was created in the system
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Predefined categories as a class constant
    # This makes it easy to reference valid categories throughout the application
    CATEGORIES = ['Maistas', 'Transportas', 'Nuoma', 'Komunaliniai', 'Biuras', 'Paslaugos', 'Kita']
    
    def __repr__(self):
        """String representation for debugging."""
        return f'<Expense {self.vendor} - {self.amount}€>'
    
    @staticmethod
    def calculate_total_expenses():
        """
        Calculate total of all expenses in the database.
        
        This is a static method because it operates on all expenses,
        not just a single expense instance.
        
        Uses Decimal for precise calculations to avoid floating point errors.
        This is critical for financial calculations where precision matters.
        
        Returns:
            float: Total amount of all expenses
        """
        # Query all expenses and sum their amounts
        # We use func.sum() from SQLAlchemy for efficient database-level summation
        from sqlalchemy import func
        
        # Get the sum of all expense amounts
        # If no expenses exist, result will be None, so we default to 0
        total = db.session.query(func.sum(Expense.amount)).scalar()
        
        # Convert to float, handling None case
        if total is None:
            return 0.0
        
        # Convert Decimal to float for return value
        return float(total)
    
    def to_dict(self):
        """
        Convert Expense object to dictionary.
        
        Useful when we need to send expense data as JSON (for APIs or frontend).
        We convert date and Decimal to string/float because JSON doesn't support these types.
        """
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'category': self.category,
            'vendor': self.vendor,
            'amount': float(self.amount) if self.amount else 0.0,
            'vat_amount': float(self.vat_amount) if self.vat_amount else 0.0,
            'description': self.description,
            'file_path': self.file_path,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

