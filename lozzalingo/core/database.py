import sqlite3
import threading
from datetime import datetime, timedelta
from .config import Config

class Database:
    # Add threading lock for thread-safe ID reservation
    _lock = threading.Lock()
    
    @staticmethod
    def connect(path):
        return sqlite3.connect(path)
    
    @staticmethod
    def get_next_id():
        with Database.connect(Config.ITEMS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT MAX(id) FROM {Config.ITEMS_TABLE}")
            last_id = cursor.fetchone()[0]
        return (last_id or 0) + 1

    
    @staticmethod
    def update_submission_progress(submission_id, progress_text):
        """
        Update the progress field for a submission.
        """
        try:
            with Database.connect(Config.ITEMS_DB) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    UPDATE {Config.ITEMS_TABLE} 
                    SET progress = ?
                    WHERE id = ?
                """, (progress_text, submission_id))
                conn.commit()
                print(f"Updated progress for submission {submission_id}: {progress_text}")
                return True
        except Exception as e:
            print(f"Error updating progress: {e}")
            return False
    
    @staticmethod
    def update_submission_field(submission_id, field_name, value):
        """
        Update a specific field for a submission.
        Useful for updating new_image, new_title, etsy_link, etc.
        """
        try:
            with Database.connect(Config.ITEMS_DB) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    UPDATE {Config.ITEMS_TABLE} 
                    SET {field_name} = ?
                    WHERE id = ?
                """, (value, submission_id))
                conn.commit()
                print(f"Updated {field_name} for submission {submission_id}: {value}")
                return True
        except Exception as e:
            print(f"Error updating {field_name}: {e}")
            return False
    
    @classmethod
    def reserve_next_id(cls):
        """
        Atomically reserve the next available ID.
        Thread-safe method to prevent duplicate IDs.
        """
        with cls._lock:
            try:
                with cls.connect(Config.ITEMS_DB) as conn:
                    cursor = conn.cursor()
                    
                    # Get the current maximum ID
                    cursor.execute(f"SELECT MAX(id) FROM {Config.ITEMS_TABLE}")
                    result = cursor.fetchone()
                    
                    if result[0] is None:
                        next_id = 1
                    else:
                        next_id = result[0] + 1
                    
                    # Reserve this ID by inserting a placeholder row
                    cursor.execute(f"""
                        INSERT INTO {Config.ITEMS_TABLE} 
                        (id, title, original_image, design_size, sex, category, origin, date, shop_name, colour_group, progress)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        next_id, 
                        "RESERVED", 
                        "", 
                        "RESERVED", 
                        "RESERVED", 
                        "T-Shirts", 
                        "website", 
                        datetime.today().strftime('%Y-%m-%d'),
                        "RESERVED",
                        "RESERVED",
                        "starting"
                    ))
                    
                    conn.commit()
                    print(f"Reserved ID {next_id} in database")
                    return next_id
                    
            except Exception as e:
                print(f"Error in reserve_next_id: {e}")
                # Fallback to simple increment
                return cls.get_next_id()
    
    @classmethod
    def save_item_with_reserved_id(cls, item_data):
        """
        Update the reserved placeholder with actual data.
        Uses consistent column names.
        """
        try:
            with cls.connect(Config.ITEMS_DB) as conn:
                cursor = conn.cursor()
                
                # Update the reserved row with actual data
                # Using consistent column names: original_image, design_size
                cursor.execute(f"""
                    UPDATE {Config.ITEMS_TABLE} 
                    SET title = ?, original_image = ?, design_size = ?, sex = ?, 
                        category = ?, origin = ?, date = ?, shop_name = ?, colour_group = ?
                    WHERE id = ?
                """, (
                    item_data[1],  # title (prompt)
                    item_data[2],  # original_image (filepath)
                    item_data[3],  # design_size (design)
                    item_data[4],  # sex
                    item_data[5],  # category
                    item_data[6],  # origin (source)
                    item_data[7],  # date
                    item_data[8],  # shop_name (process)
                    item_data[9],  # colour_group
                    item_data[0]   # id (WHERE clause)
                ))
                
                conn.commit()
                print(f"Updated reserved ID {item_data[0]} with actual data")
                
        except Exception as e:
            print(f"Error in save_item_with_reserved_id: {e}")
            # Fallback to regular insert
            cls.save_item(item_data)
    
    @classmethod 
    def save_item(cls, item_data):
        """
        Regular save method - fallback if reserved method fails.
        Uses consistent column names.
        """
        try:
            with cls.connect(Config.ITEMS_DB) as conn:
                cursor = conn.cursor()
                
                cursor.execute(f"""
                    INSERT OR REPLACE INTO {Config.ITEMS_TABLE} 
                    (id, title, original_image, design_size, sex, category, origin, date, shop_name, colour_group)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, item_data)
                
                conn.commit()
                print(f"Saved item with regular method: {item_data[0]}")
                
        except Exception as e:
            print(f"Error in save_item: {e}")
            raise e
    
    @staticmethod
    def get_creation_notification_data(submission_id):
        """
        Get all data needed for creation notification email
        Combines submission and user data
        """
        try:
            # Get submission data
            submission = Database.get_submission_by_id(submission_id)
            if not submission:
                print(f"No submission found for ID: {submission_id}")
                return None
            
            # Get user data from submissions table
            with Database.connect(Config.USER_DB) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT email, first_name, last_name, location
                    FROM submissions
                    WHERE item_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (submission_id,))
                
                user_row = cursor.fetchone()
                
                if not user_row:
                    print(f"No user info found for submission ID: {submission_id}")
                    return None
            
            # Combine the data
            notification_data = {
                'submission_id': submission_id,
                'email': user_row[0],
                'first_name': user_row[1],
                'last_name': user_row[2],
                'location': user_row[3],
                'title': submission['title'],  # Original prompt
                'new_title': submission['new_title']  # Generated title
            }
            
            return notification_data
            
        except Exception as e:
            print(f"Error in get_creation_notification_data: {e}")
            return None
        
    @staticmethod
    def init_users_table():
        """Initialize the users table with proper schema"""
        with Database.connect(Config.USER_DB) as conn:
            cursor = conn.cursor()
            
            # Create users table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    location TEXT,
                    oauth_provider TEXT,
                    oauth_provider_id TEXT,
                    avatar_url TEXT,
                    email_verified BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            
            # Create index on email for faster lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            
            # Create index on oauth provider info
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_oauth ON users(oauth_provider, oauth_provider_id)")
            
            conn.commit()
            print("Users table initialized successfully")
    
    
    @staticmethod
    def get_user_by_id(user_id):
        """Get user by ID"""
        try:
            with Database.connect(Config.USER_DB) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT id, email, password_hash, first_name, last_name, display_name, location,
                           oauth_provider, oauth_provider_id, avatar_url, email_verified,
                           created_at, last_login, is_active
                    FROM users 
                    WHERE id = ? AND is_active = 1
                """, (user_id,))
                
                row = cursor.fetchone()
                
                if row:
                    columns = ['id', 'email', 'password_hash', 'first_name', 'last_name', 'display_name',
                              'location', 'oauth_provider', 'oauth_provider_id', 'avatar_url',
                              'email_verified', 'created_at', 'last_login', 'is_active']
                    return dict(zip(columns, row))
                else:
                    return None
                    
        except Exception as e:
            print(f"Error getting user by ID: {e}")
            return None
    
    
    @staticmethod
    def update_user_oauth_info(user_id, provider, provider_id):
        """Update user's OAuth information"""
        try:
            with Database.connect(Config.USER_DB) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    UPDATE users 
                    SET oauth_provider = ?, oauth_provider_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (provider, provider_id, user_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"Error updating OAuth info: {e}")
            return False
    
    @staticmethod
    def update_user_last_login(user_id):
        """Update user's last login timestamp"""
        try:
            with Database.connect(Config.USER_DB) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    UPDATE users 
                    SET last_login = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (user_id,))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"Error updating last login: {e}")
            return False
    
    @staticmethod
    def update_user_profile(user_id, **kwargs):
        """Update user profile information"""
        if not kwargs:
            return False
            
        try:
            with Database.connect(Config.USER_DB) as conn:
                cursor = conn.cursor()
                
                # Build dynamic update query
                set_clauses = []
                values = []
                
                allowed_fields = ['first_name', 'last_name', 'display_name' 'location', 'avatar_url']
                
                for field, value in kwargs.items():
                    if field in allowed_fields and value is not None:
                        set_clauses.append(f"{field} = ?")
                        values.append(value.strip() if isinstance(value, str) else value)
                
                if not set_clauses:
                    return False
                
                set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                values.append(user_id)
                
                query = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?"
                cursor.execute(query, values)
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"Error updating user profile: {e}")
            return False
    
    @staticmethod
    def get_user_submissions(user_id, limit=50):
        """Get submissions by user ID"""
        try:
            with Database.connect(Config.USER_DB) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT s.item_id, s.timestamp, s.prompt, s.design_choices,
                           i.title, i.new_title, i.progress, i.mockup_image_2
                    FROM submissions s
                    LEFT JOIN {Config.ITEMS_TABLE} i ON s.item_id = i.id
                    WHERE s.user_id = ?
                    ORDER BY s.timestamp DESC
                    LIMIT ?
                """, (user_id, limit))
                
                rows = cursor.fetchall()
                
                submissions = []
                for row in rows:
                    submissions.append({
                        'item_id': row[0],
                        'timestamp': row[1],
                        'prompt': row[2],
                        'design_choices': row[3],
                        'title': row[4],
                        'new_title': row[5],
                        'progress': row[6],
                        'mockup_image_2': row[7]
                    })
                
                return submissions
                
        except Exception as e:
            print(f"Error getting user submissions: {e}")
            return []
    
    @staticmethod
    def link_submission_to_user(email, user_id):
        """Link existing submissions to a user account when they register/sign in"""
        try:
            with Database.connect(Config.USER_DB) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    UPDATE submissions 
                    SET user_id = ?
                    WHERE email = ? AND (user_id IS NULL OR user_id = 0)
                """, (user_id, email.lower().strip()))
                
                affected_rows = cursor.rowcount
                conn.commit()
                
                if affected_rows > 0:
                    print(f"Linked {affected_rows} existing submissions to user {user_id}")
                
                return True
                
        except Exception as e:
            print(f"Error linking submissions to user: {e}")
            return False
    
    @staticmethod
    def save_submission(email, first_name, last_name, location, prompt, design_choices, item_id, user_id=None):
        """Save a submission (works for both authenticated and anonymous users)"""
        try:
            with Database.connect(Config.USER_DB) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    INSERT INTO submissions 
                    (user_id, item_id, email, first_name, last_name, location, prompt, design_choices)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,  # Can be None for anonymous users
                    item_id,
                    email.lower().strip(),
                    first_name.strip(),
                    last_name.strip(),
                    location.strip() if location else None,
                    prompt,
                    design_choices
                ))
                
                conn.commit()
                print(f"Saved submission for {email} (Item ID: {item_id})")
                return True
                
        except Exception as e:
            print(f"Error saving submission: {e}")
            return False
    
    @staticmethod
    def get_submissions_by_email(email, limit=50):
        """Get submissions by email (for anonymous users or linking accounts)"""
        try:
            with Database.connect(Config.USER_DB) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT s.item_id, s.timestamp, s.prompt, s.design_choices,
                           s.first_name, s.last_name, s.location, s.user_id
                    FROM submissions s
                    WHERE s.email = ?
                    ORDER BY s.timestamp DESC
                    LIMIT ?
                """, (email.lower().strip(), limit))
                
                rows = cursor.fetchall()
                
                submissions = []
                for row in rows:
                    submissions.append({
                        'item_id': row[0],
                        'timestamp': row[1],
                        'prompt': row[2],
                        'design_choices': row[3],
                        'first_name': row[4],
                        'last_name': row[5],
                        'location': row[6],
                        'user_id': row[7]
                    })
                
                return submissions
                
        except Exception as e:
            print(f"Error getting submissions by email: {e}")
            return []