"""
Unit Tests for Mano Startuolis Accounting System

This file contains automated tests to verify that the application works correctly.
We use Python's built-in unittest library - no additional packages needed!

WHY WE USE IN-MEMORY DATABASE FOR TESTS:
========================================

We use SQLite in-memory database (':memory:') instead of the real 'accounting.db' file because:

1. **Isolation**: Each test runs with a fresh, empty database
   - Tests don't interfere with each other
   - No leftover data from previous tests

2. **Speed**: In-memory database is much faster
   - No disk I/O operations
   - Tests run quickly

3. **Cleanliness**: Tests don't pollute your real database
   - Your real 'accounting.db' stays clean
   - No test clients/invoices mixed with real data
   - You can run tests as many times as you want without worry

4. **Reliability**: Tests are predictable
   - Same starting state every time
   - No dependencies on existing data

5. **Safety**: Can't accidentally delete real data
   - Tests can create/delete freely
   - Your production data is safe

This is a standard practice in software development - always test against a separate test database!
"""

import unittest
from datetime import datetime, date
from app import create_app
from models import db, Client, Invoice


class AccountingTests(unittest.TestCase):
    """
    Test suite for the accounting system.
    
    Each test method (starting with 'test_') is automatically discovered and run by unittest.
    setUp() runs before each test - creates a fresh database.
    tearDown() runs after each test - cleans up.
    """
    
    def setUp(self):
        """
        Set up test environment before each test runs.
        
        This method is called automatically before every test_* method.
        We create a Flask app with in-memory database here.
        """
        # Create Flask app with test configuration
        # We pass a test config that uses in-memory database
        self.app = create_app()
        
        # Override the database URI to use in-memory SQLite
        # ':memory:' creates a database that exists only in RAM
        # It's automatically deleted when the connection closes
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        # Disable CSRF protection for testing (not needed for unit tests)
        self.app.config['TESTING'] = True
        
        # Create application context
        # Flask requires this to access the database
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Create all database tables in the in-memory database
        # This creates fresh tables for each test
        db.create_all()
    
    def tearDown(self):
        """
        Clean up after each test runs.
        
        This method is called automatically after every test_* method.
        We remove all data and close the database connection.
        """
        # Remove all data from database
        # This ensures each test starts with a clean slate
        db.session.remove()
        
        # Drop all tables
        # This completely cleans up the in-memory database
        db.drop_all()
        
        # Remove application context
        self.app_context.pop()
    
    def test_create_client(self):
        """
        Test 1: Create a new Client and verify it was saved to the database.
        
        This test verifies:
        1. We can create a Client object
        2. We can save it to the database
        3. We can retrieve it from the database
        4. The data we saved matches what we retrieve
        
        This is a fundamental test - if this fails, nothing else will work!
        """
        # STEP 1: Create a Client object in memory
        # This object exists only in Python memory, not in database yet
        new_client = Client(
            name="Test Client",
            email="test@example.com",
            phone="+370 600 00000",
            company_code="123456789",
            address="Test Address 123"
        )
        
        # STEP 2: Add to database session
        # This stages the client for saving (like adding to a shopping cart)
        db.session.add(new_client)
        
        # STEP 3: Commit to database
        # This actually writes the data to the in-memory database
        db.session.commit()
        
        # STEP 4: Verify the client was saved
        # Query the database to retrieve the client we just saved
        # We use the client's ID to find it
        # Using db.session.get() is the modern way (avoids deprecation warnings)
        saved_client = db.session.get(Client, new_client.id)
        
        # STEP 5: Assertions - verify the data is correct
        # If any assertion fails, the test fails and shows what went wrong
        
        # Check that we found a client (not None)
        self.assertIsNotNone(saved_client, "Client should be saved in database")
        
        # Check that the name matches what we saved
        self.assertEqual(saved_client.name, "Test Client", 
                        "Client name should match what we saved")
        
        # Check that the email matches
        self.assertEqual(saved_client.email, "test@example.com",
                        "Client email should match what we saved")
        
        # Check that the phone matches
        self.assertEqual(saved_client.phone, "+370 600 00000",
                        "Client phone should match what we saved")
        
        # Check that ID was automatically assigned
        # The database should have given it an ID (1, since it's the first record)
        self.assertIsNotNone(saved_client.id, "Client should have an ID assigned")
        self.assertEqual(saved_client.id, 1, "First client should have ID = 1")
    
    def test_create_invoice_with_client_relationship(self):
        """
        Test 2: Create an Invoice linked to a Client and verify the relationship works.
        
        This test verifies:
        1. We can create a Client
        2. We can create an Invoice linked to that Client
        3. The relationship works (invoice.client returns the correct client)
        4. The foreign key (client_id) is correctly set
        
        This is crucial - it tests that the Client-Invoice relationship works correctly!
        """
        # STEP 1: Create a Client first
        # Invoices must belong to a client, so we need a client first
        test_client = Client(
            name="Invoice Test Client",
            email="invoice@example.com"
        )
        db.session.add(test_client)
        db.session.commit()
        
        # Verify client was saved (basic sanity check)
        self.assertIsNotNone(test_client.id, "Client should have an ID")
        
        # STEP 2: Create an Invoice linked to the client
        # We use client_id to link the invoice to the client
        # This is the foreign key relationship
        new_invoice = Invoice(
            invoice_number="INV-TEST-001",
            client_id=test_client.id,  # This links invoice to client
            invoice_date=date.today(),
            status="pending"
        )
        
        # STEP 3: Save invoice to database
        db.session.add(new_invoice)
        db.session.commit()
        
        # STEP 4: Verify invoice was saved
        # Using db.session.get() is the modern way (avoids deprecation warnings)
        saved_invoice = db.session.get(Invoice, new_invoice.id)
        self.assertIsNotNone(saved_invoice, "Invoice should be saved in database")
        
        # STEP 5: Verify the foreign key is set correctly
        # The invoice.client_id should match the client's ID
        self.assertEqual(saved_invoice.client_id, test_client.id,
                        "Invoice client_id should match the client's ID")
        
        # STEP 6: Test the relationship - this is the key part!
        # SQLAlchemy relationship lets us access invoice.client directly
        # This should return the Client object we created
        related_client = saved_invoice.client
        
        # Verify the relationship works
        self.assertIsNotNone(related_client, 
                            "Invoice.client should return a Client object")
        
        # Verify it's the correct client
        self.assertEqual(related_client.id, test_client.id,
                        "Invoice should be linked to the correct client")
        
        # Verify we can access client properties through the relationship
        self.assertEqual(related_client.name, "Invoice Test Client",
                        "Should be able to access client.name through relationship")
        
        # STEP 7: Test reverse relationship (client.invoices)
        # The Client model has a relationship back to invoices
        # We should be able to access all invoices for a client
        client_invoices = test_client.invoices.all()  # .all() executes the query
        
        # Verify the client has one invoice
        self.assertEqual(len(client_invoices), 1,
                        "Client should have one invoice")
        
        # Verify it's the correct invoice
        self.assertEqual(client_invoices[0].invoice_number, "INV-TEST-001",
                        "Client's invoice should be the one we created")


if __name__ == '__main__':
    """
    This allows us to run tests directly with: python tests.py
    
    unittest.main() automatically:
    - Discovers all test methods (starting with 'test_')
    - Runs them
    - Reports results
    """
    # Run all tests
    unittest.main()

