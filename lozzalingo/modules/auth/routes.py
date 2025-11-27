from flask import flash, render_template, request, redirect, url_for, Blueprint, session, jsonify
import secrets
from datetime import datetime, timedelta

# Optional import for app-specific database integration
try:
    from database import Database
except ImportError:
    Database = None

from .database import SignInDatabase
from .email import send_password_reset_email, send_password_changed_email, send_verification_email
from .utils import validate_password_strength

signin_bp = Blueprint(
    'auth',
    __name__,
    static_folder='static',
    static_url_path='/auth/static',
    template_folder='templates'
)

# Store the oauth instance here - it will be set by the init function
oauth = None

def init_oauth(oauth_instance):
    """Initialize the oauth instance for this module"""
    global oauth
    oauth = oauth_instance

@signin_bp.route('/sign-in')
def signin():
    """Sign-in page route"""
    return render_template('auth/sign-in.html')

@signin_bp.route('/login')
def login():
    """Login route alias for compatibility"""
    return render_template('auth/sign-in.html')

@signin_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Register page route"""
    if request.method == 'POST':
        # Get form data
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        # Validate required fields
        if not all([first_name, last_name, email, password]):
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        
        # Validate password strength
        if not validate_password_strength(password):
            return jsonify({'success': False, 'message': 'Password does not meet requirements'}), 400
        
        # Check if user already exists
        if SignInDatabase.get_user_by_email(email):
            return jsonify({'success': False, 'message': 'Account already exists with this email'}), 400
        
        # Create user (unverified)
        user_id = SignInDatabase.create_user(email, first_name, last_name, password=password, verified=False)
        
        if user_id:
            # Generate verification token
            token = secrets.token_urlsafe(32)
            expires = datetime.utcnow() + timedelta(hours=24)  # Token expires in 24 hours
            
            # Store verification token
            SignInDatabase.save_verification_token(user_id, token, expires)
            
            # Send verification email
            verification_link = f"{request.host_url}verify-email?token={token}"
            email_sent = send_verification_email(email, first_name, verification_link)
            
            if email_sent:
                return jsonify({
                    'success': True, 
                    'message': 'Account created! Please check your email to verify your account.',
                    'redirect': url_for('auth.signin')
                })
            else:
                # If email fails, still allow the user to sign in but show message
                return jsonify({
                    'success': True,
                    'message': 'Account created! Please sign in (verification email could not be sent).',
                    'redirect': url_for('auth.signin')
                })
        else:
            return jsonify({'success': False, 'message': 'Failed to create account'}), 500
    
    return render_template('auth/register.html')

@signin_bp.route('/verify-email')
def verify_email():
    """Verify email address with token"""
    token = request.args.get('token')
    
    if not token:
        flash('Invalid verification link.', 'error')
        return redirect(url_for('auth.signin'))
    
    # Check if token exists and is valid
    verification_data = SignInDatabase.get_verification_token(token)
    
    if not verification_data:
        flash('Invalid or expired verification link. Please sign in to request a new one.', 'error')
        return redirect(url_for('auth.signin'))
    
    # Mark user as verified
    success = SignInDatabase.verify_user_email(verification_data['user_id'])
    
    if success:
        # Delete the verification token
        SignInDatabase.delete_verification_token(token)
        flash('Email verified successfully! You can now sign in.', 'success')
    else:
        flash('Failed to verify email. Please try again.', 'error')
    
    return redirect(url_for('auth.signin'))

@signin_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend verification email for unverified users"""
    email = request.form.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400
    
    # Get user
    user = SignInDatabase.get_user_by_email(email)
    
    if not user:
        return jsonify({'success': False, 'message': 'No account found with this email'}), 400
    
    if user.get('email_verified', False):
        return jsonify({'success': False, 'message': 'Email is already verified'}), 400
    
    # Generate new verification token
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=24)
    
    # Save token
    SignInDatabase.save_verification_token(user['id'], token, expires)
    
    # Send verification email
    verification_link = f"{request.host_url}verify-email?token={token}"
    email_sent = send_verification_email(user['email'], user['first_name'], verification_link)
    
    if email_sent:
        return jsonify({'success': True, 'message': 'Verification email sent!'})
    else:
        return jsonify({'success': False, 'message': 'Failed to send verification email'}), 500

@signin_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgotpassword():
    """Forgot password page - handles email submission"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('auth/forgot-password.html')
        
        # Check if user exists
        user = SignInDatabase.get_user_by_email(email)
        
        if user:
            # Generate password reset token
            token = secrets.token_urlsafe(32)
            expires = datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour
            
            # Store the reset token in database
            success = SignInDatabase.save_password_reset_token(user['id'], token, expires)
            
            if success:
                # Send reset email
                reset_link = f"{request.host_url}password-reset?token={token}"
                email_sent = send_password_reset_email(user['email'], user['first_name'], reset_link)
                
                if email_sent:
                    flash(f'Password reset link sent to {email}', 'success')
                    return render_template('auth/forgot-password.html', email_sent=True)
                else:
                    flash('Failed to send reset email. Please try again.', 'error')
            else:
                flash('Failed to generate reset token. Please try again.', 'error')
        else:
            # Don't reveal if email exists or not for security
            flash(f'If an account with {email} exists, a password reset link has been sent.', 'info')
            return render_template('auth/forgot-password.html', email_sent=True)
    
    return render_template('auth/forgot-password.html')

@signin_bp.route('/password-reset', methods=['GET', 'POST'])
def passwordreset():
    token = request.args.get('token') or request.form.get('token')
    
    if request.method == 'GET' and not token:
        return redirect(url_for('auth.forgotpassword'))
    
    if request.method == 'GET':
        # Validate token exists and hasn't expired
        reset_data = SignInDatabase.get_password_reset_token(token)
        
        if not reset_data:
            flash('Invalid or expired reset token. Please request a new one.', 'error')
            return redirect(url_for('auth.forgotpassword'))
        
        return render_template('auth/password-reset.html', token=token, valid_token=True)
    
    elif request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate passwords
        if not new_password or not confirm_password:
            flash('Please fill in both password fields.', 'error')
            return render_template('auth/password-reset.html', token=token, valid_token=True)
        
        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/password-reset.html', token=token, valid_token=True)
        
        # Validate password strength
        if not validate_password_strength(new_password):
            flash('Password does not meet security requirements.', 'error')
            return render_template('auth/password-reset.html', token=token, valid_token=True)
        
        # Get and validate token
        reset_data = SignInDatabase.get_password_reset_token(token)
        
        if not reset_data:
            flash('Invalid or expired reset token.', 'error')
            return redirect(url_for('auth.forgotpassword'))
        
        # Update user password
        success = SignInDatabase.update_user_password(reset_data['user_id'], new_password)
        
        if success:
            # Delete the used token
            SignInDatabase.delete_password_reset_token(token)
            
            # Get user info for email
            user = SignInDatabase.get_user_by_id(reset_data['user_id'])
            
            # Send confirmation email
            send_password_changed_email(user['email'], user['first_name'])
            
            flash('Password successfully updated! You can now sign in with your new password.', 'success')
            return render_template('auth/password-reset.html', password_reset_success=True)
        else:
            flash('Failed to update password. Please try again.', 'error')
            return render_template('auth/password-reset.html', token=token, valid_token=True)

@signin_bp.route('/auth/<provider>')
def oauth_login(provider):
    """Initiate OAuth login"""
    if provider not in ['google', 'github']:
        flash('Invalid authentication provider', 'error')
        return redirect(url_for('auth.signin'))
    
    if oauth is None:
        flash('OAuth not configured', 'error')
        return redirect(url_for('auth.signin'))
    
    client = oauth.create_client(provider)
    redirect_uri = url_for('auth.oauth_callback', provider=provider, _external=True)
    return client.authorize_redirect(redirect_uri)

@signin_bp.route('/auth/<provider>/callback')
def oauth_callback(provider):
    """Handle OAuth callback"""
    if provider not in ['google', 'github']:
        flash('Invalid authentication provider', 'error')
        return redirect(url_for('auth.signin'))
    
    if oauth is None:
        flash('OAuth not configured', 'error')
        return redirect(url_for('auth.signin'))
    
    client = oauth.create_client(provider)
    token = client.authorize_access_token()
    
    if provider == 'google':
        # Get user info from Google API
        resp = client.get('https://www.googleapis.com/oauth2/v3/userinfo', token=token)
        user_info = resp.json()
        if user_info:
            email = user_info['email']
            first_name = user_info.get('given_name', '')
            last_name = user_info.get('family_name', '')
            provider_id = user_info['sub']
            avatar_url = user_info.get('picture', '')
    
    elif provider == 'github':
        # Get user info from GitHub API
        resp = client.get('user')
        user_info = resp.json()
        
        # Get email separately as it might be private
        email_resp = client.get('user/emails')
        emails = email_resp.json()
        primary_email = next((email['email'] for email in emails if email['primary']), None)
        
        email = primary_email or user_info.get('email', '')
        full_name = user_info.get('name', '').split(' ', 1)
        first_name = full_name[0] if full_name else ''
        last_name = full_name[1] if len(full_name) > 1 else ''
        provider_id = str(user_info['id'])
        avatar_url = user_info.get('avatar_url', '')
    
    if not email:
        flash('Unable to retrieve email from your account. Please try again.', 'error')
        return redirect(url_for('auth.signin'))
    
    # Check if user exists or create new user
    user = SignInDatabase.get_user_by_email(email)
    
    if user:
        # Update existing user's OAuth info
        SignInDatabase.update_user_oauth_info(user['id'], provider, provider_id)
        user_id = user['id']
        
        # Link any existing submissions/donations from this email to the user account
        if Database is not None:
            try:
                Database.link_submission_to_user(email, user_id)
            except AttributeError:
                # Method doesn't exist yet, skip for now
                pass
    else:
        # Check if we have enough info to create user
        if not first_name and not last_name:
            # Store OAuth temp data in session instead of database
            session['oauth_temp_data'] = {
                'email': email,
                'provider': provider,
                'provider_id': provider_id,
                'avatar_url': avatar_url
            }
            return redirect(url_for('auth.complete_profile'))
        
        # Create new user - OAuth users are auto-verified
        user_id = SignInDatabase.create_user(
            email=email, 
            first_name=first_name, 
            last_name=last_name, 
            oauth_provider=provider, 
            oauth_provider_id=provider_id, 
            avatar_url=avatar_url,
            verified=True  # OAuth users are pre-verified
        )
        
        # Link any existing submissions/donations from this email to the new user account
        if user_id and Database is not None:
            try:
                Database.link_submission_to_user(email, user_id)
            except AttributeError:
                # Method doesn't exist yet, skip for now
                pass
    
    # Set session
    session['user_id'] = user_id
    session['email'] = email
    session['first_name'] = first_name
    session['last_name'] = last_name

    # Check if user is admin
    user_data = SignInDatabase.get_user_by_email(email)
    if user_data and user_data.get('user_level') == 'admin':
        session['admin_id'] = user_id
        session['admin_email'] = email

    flash(f'Successfully signed in with {provider.title()}!', 'success')
    return redirect(url_for('index'))

@signin_bp.route('/complete-profile')
def complete_profile():
    """Complete profile for OAuth users missing name information"""
    if 'oauth_temp_data' not in session:
        flash('Invalid access to profile completion.', 'error')
        return redirect(url_for('auth.signin'))
    
    return render_template('auth/complete-profile.html')

@signin_bp.route('/sign-in-form', methods=['POST'])
def signin_form():
    """Handle traditional email/password sign-in"""
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    remember = request.form.get('remember') == 'on'
    
    if not email or not password:
        return jsonify({
            'success': False,
            'message': 'Please enter both email and password'
        }), 400
    
    # Verify user credentials
    user = SignInDatabase.verify_user_credentials(email, password)
    
    if not user:
        return jsonify({
            'success': False,
            'message': 'Invalid email or password'
        }), 401
    
    # Check if email is verified
    if not user.get('email_verified', False):
        return jsonify({
            'success': False,
            'message': 'Please verify your email address before signing in.',
            'show_resend': True,
            'email': email
        }), 403
    
    # Set session
    session['user_id'] = user['id']
    session['email'] = user['email']
    session['first_name'] = user['first_name']
    session['last_name'] = user['last_name']

    # Check if user is admin
    if user.get('user_level') == 'admin':
        session['admin_id'] = user['id']
        session['admin_email'] = user['email']

    # Handle remember me functionality
    if remember:
        session.permanent = True

    return jsonify({
        'success': True,
        'message': 'Sign-in successful',
        'redirect': url_for('index')
    })

@signin_bp.route('/sign-out')
def signout():
    """Sign out user"""
    session.clear()
    flash('You have been signed out successfully.', 'success')
    return redirect(url_for('index'))

@signin_bp.route('/logout')
def logout():
    """Logout route alias for compatibility"""
    session.clear()
    flash('You have been signed out successfully.', 'success')
    return redirect(url_for('index'))

@signin_bp.route('/dashboard')
def dashboard():
    """Dashboard route - redirects to home page"""
    return redirect(url_for('index'))

@signin_bp.route('/change-password')
def change_password():
    """Change password route - placeholder for future implementation"""
    flash('Password change functionality coming soon.', 'info')
    return redirect(url_for('auth.signin'))