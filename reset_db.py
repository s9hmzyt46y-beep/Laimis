"""
Database Reset Script

This script fixes database schema mismatches by:
1. Dropping all existing tables
2. Creating new tables with the latest schema (including vat_amount column)
3. Re-creating the admin user

Usage:
    python3 reset_db.py
"""

# Import app and db from app.py
# The app instance is created at the bottom of app.py
from app import app, db
from werkzeug.security import generate_password_hash

# Wrap the logic in app context
# Flask-SQLAlchemy requires this to access the database
with app.app_context():
    print("=" * 60)
    print("RESETTING DATABASE SCHEMA")
    print("=" * 60)
    
    # STEP 1: Drop all existing tables
    # This deletes the old buggy database structure
    print("\n1. Dropping all existing tables...")
    db.drop_all()
    print("   ✓ All tables dropped")
    
    # STEP 2: Create all tables with current schema
    # This creates the new database with the vat_amount column
    print("\n2. Creating new tables with latest schema...")
    db.create_all()
    print("   ✓ All tables created (including vat_amount column in expenses)")
    
    # STEP 3: Create the admin user again
    print("\n3. Creating admin user...")
    try:
        # Try to import User model from models
        # Note: User might not exist in all versions, so we handle ImportError
        from models import User
        
        # Check if admin user already exists (shouldn't after drop_all, but just in case)
        admin_user = User.query.filter_by(username='admin').first()
        
        if not admin_user:
            # Create admin user with password 'admin'
            admin_user = User(
                username='admin',
                password_hash=generate_password_hash('admin')
            )
            db.session.add(admin_user)
            db.session.commit()
            print("   ✓ Admin user created: username='admin', password='admin'")
        else:
            # Update password if user exists
            admin_user.password_hash = generate_password_hash('admin')
            db.session.commit()
            print("   ✓ Admin user password updated: username='admin', password='admin'")
            
    except ImportError:
        # User model doesn't exist - skip user creation
        print("   ⚠ User model not found - skipping admin user creation")
        db.session.commit()
    except Exception as e:
        # Handle any other errors gracefully
        print(f"   ✗ Error creating admin user: {e}")
        db.session.rollback()
    
    print("\n" + "=" * 60)
    print("FIX COMPLETE: Database has been reset with the new columns.")
    print("=" * 60)
    print("\nYou can now:")
    print("  - Login with username='admin' and password='admin'")
    print("  - Use the application with the new vat_amount column")
    print()

