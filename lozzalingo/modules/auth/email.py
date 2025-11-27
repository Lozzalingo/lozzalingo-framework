from email_service import EmailService

def send_password_reset_email(email, first_name, reset_link):
    """Send password reset email"""
    subject = "Reset Your Crowd Sauced Password"
    
    body = f"""Hi {first_name},

You requested a password reset for your Crowd Sauced account.

Click the link below to reset your password:
{reset_link}

This link will expire in 1 hour for security reasons.

If you didn't request this reset, you can safely ignore this email.

Best regards,
The Crowd Sauced Team

---
🌐 crowdsauced.com
📧 Need help? Reply to this email"""
    
    return EmailService.send_email(email, subject, body)


def send_password_changed_email(email, first_name):
    """Send confirmation email after password change"""
    subject = "Password Changed - Crowd Sauced"
    
    body = f"""Hi {first_name},

Your Crowd Sauced account password has been successfully changed.

If you didn't make this change, please contact us immediately by replying to this email.

Best regards,
The Crowd Sauced Team

---
🌐 crowdsauced.com
📧 Need help? Reply to this email"""
    
    return EmailService.send_email(email, subject, body)


def send_verification_email(email, first_name, verification_link):
    """Send email verification for new users"""
    subject = "Welcome to Crowd Sauced - Verify Your Email"
    
    body = f"""Hi {first_name},

Welcome to Crowd Sauced! 

Please verify your email address by clicking the link below:
{verification_link}

This link will expire in 24 hours.

Once verified, you'll be able to access all features of your account.

Best regards,
The Crowd Sauced Team

---
🌐 crowdsauced.com
📧 Need help? Reply to this email"""
    
    return EmailService.send_email(email, subject, body)