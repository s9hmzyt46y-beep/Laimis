# Mano Startuolis - Accounting System

A simplified accounting system for managing clients, invoices, and invoice items.

## Tech Stack

- **Python 3.8+**
- **Flask** - Web framework
- **SQLite** - Database (no setup required)
- **Flask-SQLAlchemy** - Database ORM

## Project Structure

```
test1/
├── app.py              # Main Flask application
├── models.py           # Database models (Client, Invoice, InvoiceItem)
├── requirements.txt    # Python dependencies
└── accounting.db       # SQLite database (created automatically)
```

## Setup Instructions

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize the database:**
   ```bash
   python3 init_db.py
   ```
   
   This creates all necessary database tables (clients, invoices, invoice_items).
   The database file `accounting.db` will be created automatically.
   
   **Note:** This is safe to run multiple times - it only creates tables that don't exist.

3. **Run the application:**
   ```bash
   python3 start.py
   ```
   
   The application will automatically find an available port (usually 3000).

4. **Access the application:**
   - Open the URL shown in the terminal (usually `http://localhost:3000`)

## Database Models

### Client (Klientas)
- Stores client information (name, email, phone, company code, address)
- Each client can have multiple invoices

### Invoice (Sąskaita faktūra)
- Represents a bill sent to a client
- Contains invoice number, dates, status, and notes
- Belongs to one client
- Can have multiple invoice items

### InvoiceItem (Paslauga/Prekė sąskaitoje)
- Represents a line item on an invoice
- Contains description, quantity, unit price, and tax rate
- Belongs to one invoice
- Used to calculate invoice totals

## Usage Example

```python
from app import app, db
from models import Client, Invoice, InvoiceItem

with app.app_context():
    # Create a client
    client = Client(
        name="John Doe",
        email="john@example.com",
        phone="+370 600 00000"
    )
    db.session.add(client)
    db.session.commit()
    
    # Create an invoice
    invoice = Invoice(
        invoice_number="INV-2024-001",
        client_id=client.id,
        status="pending"
    )
    db.session.add(invoice)
    db.session.commit()
    
    # Add items to invoice
    item = InvoiceItem(
        invoice_id=invoice.id,
        description="Web Development Services",
        quantity=10.0,
        unit_price=50.00,
        tax_rate=21.0
    )
    db.session.add(item)
    db.session.commit()
    
    # Calculate invoice total
    total = invoice.calculate_total()
    print(f"Invoice total: {total}")
```

## Database Initialization

To manually initialize the database (create all tables), you can use:

```bash
python3 init_db.py
```

Or from Python:
```python
from app import init_db
init_db()
```

This command:
- Creates all database tables defined in `models.py`
- Creates the `accounting.db` file if it doesn't exist
- Is safe to run multiple times (won't overwrite existing data)

## Notes

- The database file (`accounting.db`) is created automatically when you first run the app or run `init_db.py`
- All models include detailed comments explaining the design decisions
- The code prioritizes readability over performance (perfect for learning)

