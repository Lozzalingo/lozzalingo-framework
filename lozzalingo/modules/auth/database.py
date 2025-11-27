import sqlite3
import hashlib
import secrets
from datetime import datetime
from config import Config

class SignInDatabase:
    @staticmethod
    def _get_connection():
        """Get database connection"""
        conn = sqlite3.connect(Config.USER_DB)
        conn.row_factory = sqlite3.Row
        return conn
    
    @staticmethod
    def _hash_password(password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def _verify_password(password, password_hash):
        """Verify password against hash"""
        return hashlib.sha256(password.encode()).hexdigest() == password_hash
    
    @staticmethod
    def get_user_by_email(email):
        """Get user by email address"""
        conn = SignInDatabase._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM users WHERE email = ? AND is_active = 1
            """, (email,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    @staticmethod
    def get_user_by_id(user_id):
        """Get user by ID"""
        conn = SignInDatabase._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM users WHERE id = ? AND is_active = 1
            """, (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    @staticmethod
    def create_user(email, first_name, last_name, password=None, oauth_provider=None, 
                   oauth_provider_id=None, avatar_url=None, verified=False):
        """Create a new user"""
        conn = SignInDatabase._get_connection()
        try:
            cursor = conn.cursor()
            password_hash = SignInDatabase._hash_password(password) if password else None
            
            cursor.execute("""
                INSERT INTO users (email, password_hash, first_name, last_name, 
                                 oauth_provider, oauth_provider_id, avatar_url, 
                                 email_verified, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (email, password_hash, first_name, last_name, oauth_provider, 
                  oauth_provider_id, avatar_url, verified, datetime.utcnow(), datetime.utcnow()))
            
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None  # User already exists
        finally:
            conn.close()
    
    @staticmethod
    def verify_user_credentials(email, password):
        """Verify user login credentials"""
        conn = SignInDatabase._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM users WHERE email = ? AND is_active = 1
            """, (email,))
            row = cursor.fetchone()
            
            if row and row['password_hash'] and SignInDatabase._verify_password(password, row['password_hash']):
                # Update last login
                cursor.execute("""
                    UPDATE users SET last_login = ? WHERE id = ?
                """, (datetime.utcnow(), row['id']))
                conn.commit()
                return dict(row)
            return None
        finally:
            conn.close()
    
    @staticmethod
    def save_password_reset_token(user_id, token, expires_at):
        """Save password reset token"""
        conn = SignInDatabase._get_connection()
        try:
            cursor = conn.cursor()
            # Delete any existing tokens for this user
            cursor.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,))
            
            # Insert new token
            cursor.execute("""
                INSERT INTO password_reset_tokens (user_id, token, expires_at, created_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, token, expires_at, datetime.utcnow()))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error saving password reset token: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_password_reset_token(token):
        """Get password reset token data"""
        conn = SignInDatabase._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM password_reset_tokens 
                WHERE token = ? AND expires_at > ? AND used = 0
            """, (token, datetime.utcnow()))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    @staticmethod
    def delete_password_reset_token(token):
        """Delete/mark password reset token as used"""
        conn = SignInDatabase._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE password_reset_tokens SET used = 1 WHERE token = ?
            """, (token,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    @staticmethod
    def update_user_password(user_id, new_password):
        """Update user password"""
        conn = SignInDatabase._get_connection()
        try:
            cursor = conn.cursor()
            password_hash = SignInDatabase._hash_password(new_password)
            cursor.execute("""
                UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?
            """, (password_hash, datetime.utcnow(), user_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    @staticmethod
    def save_verification_token(user_id, token, expires_at):
        """Save email verification token"""
        conn = SignInDatabase._get_connection()
        try:
            cursor = conn.cursor()
            # Delete any existing tokens for this user
            cursor.execute("DELETE FROM email_verification_tokens WHERE user_id = ?", (user_id,))
            
            # Insert new token
            cursor.execute("""
                INSERT INTO email_verification_tokens (user_id, token, expires_at, created_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, token, expires_at, datetime.utcnow()))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error saving verification token: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_verification_token(token):
        """Get email verification token data"""
        conn = SignInDatabase._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM email_verification_tokens 
                WHERE token = ? AND expires_at > ? AND used = 0
            """, (token, datetime.utcnow()))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    @staticmethod
    def delete_verification_token(token):
        """Delete/mark verification token as used"""
        conn = SignInDatabase._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE email_verification_tokens SET used = 1 WHERE token = ?
            """, (token,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    @staticmethod
    def verify_user_email(user_id):
        """Mark user email as verified"""
        conn = SignInDatabase._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET email_verified = 1, updated_at = ? WHERE id = ?
            """, (datetime.utcnow(), user_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    @staticmethod
    def update_user_oauth_info(user_id, provider, provider_id):
        """Update user's OAuth information"""
        conn = SignInDatabase._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET oauth_provider = ?, oauth_provider_id = ?, updated_at = ?
                WHERE id = ?
            """, (provider, provider_id, datetime.utcnow(), user_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()