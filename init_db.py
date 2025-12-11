#!/usr/bin/env python3
"""
Database Initialization Script

This script initializes the SQLite database by creating all necessary tables.

WHAT IT DOES:
=============

This script creates the database structure (tables) for the accounting system:
- clients table: Stores client information
- invoices table: Stores invoice headers
- invoice_items table: Stores individual line items on invoices

The database file (accounting.db) will be created in the project directory
if it doesn't already exist.

HOW TO RUN:
===========

From command line:
    python3 init_db.py

Or:
    python3 -c "from app import init_db; init_db()"

SAFE TO RUN MULTIPLE TIMES:
===========================

This script is safe to run multiple times. It only creates tables that
don't exist, so it won't overwrite existing data or cause errors.
"""

from app import init_db

if __name__ == '__main__':
    print("Initializing database...")
    print()
    init_db()

