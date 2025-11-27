// Check if we're on a password reset page with a token
const urlParams = new URLSearchParams(window.location.search);
const token = urlParams.get('token');

if (token) {
    // Show password reset form
    showPasswordForm(token);
}

// Email form submission
document.getElementById('emailForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const email = document.getElementById('email').value;
    const btn = document.getElementById('sendEmailBtn');
    
    // Disable button and show loading
    btn.disabled = true;
    btn.textContent = 'Sending...';
    
    // Simulate API call - replace with actual endpoint
    setTimeout(() => {
        showSuccessState(email);
    }, 1000);
});

// Password form submission
document.getElementById('passwordForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const newPassword = document.getElementById('new_password').value;
    const confirmPassword = document.getElementById('confirm_password').value;
    const token = document.getElementById('resetToken').value;
    const btn = document.getElementById('resetPasswordBtn');
    
    // Validate passwords match
    if (newPassword !== confirmPassword) {
        showPasswordMatchError();
        return;
    }
    
    // Validate password requirements
    if (!validatePassword(newPassword)) {
        showMessage('passwordMessageContainer', 'Please ensure your password meets all requirements.', 'error');
        return;
    }
    
    // Disable button and show loading
    btn.disabled = true;
    btn.textContent = 'Resetting...';
    
    // Simulate API call - replace with actual endpoint
    setTimeout(() => {
        showPasswordResetSuccess();
    }, 1000);
});

// Password validation
document.getElementById('new_password').addEventListener('input', function() {
    const password = this.value;
    validatePasswordRequirements(password);
    hidePasswordMatchError();
});

document.getElementById('confirm_password').addEventListener('input', function() {
    hidePasswordMatchError();
});

function showEmailForm() {
    document.getElementById('email-form-state').classList.remove('hidden');
    document.getElementById('password-form-state').classList.add('hidden');
    document.getElementById('success-state').classList.add('hidden');
    
    document.getElementById('pageTitle').textContent = 'Reset Password';
    document.getElementById('pageSubtitle').textContent = 'Regain access to your account';
    
    // Reset form
    document.getElementById('emailForm').reset();
    document.getElementById('sendEmailBtn').disabled = false;
    document.getElementById('sendEmailBtn').textContent = 'Send Reset Link';
}

function showPasswordForm(token) {
    document.getElementById('email-form-state').classList.add('hidden');
    document.getElementById('password-form-state').classList.remove('hidden');
    document.getElementById('success-state').classList.add('hidden');
    
    document.getElementById('pageTitle').textContent = 'New Password';
    document.getElementById('pageSubtitle').textContent = 'Create a secure password';
    
    document.getElementById('resetToken').value = token;
}

function showSuccessState(email) {
    document.getElementById('email-form-state').classList.add('hidden');
    document.getElementById('password-form-state').classList.add('hidden');
    document.getElementById('success-state').classList.remove('hidden');
    
    document.getElementById('pageTitle').textContent = 'Check Your Email';
    document.getElementById('pageSubtitle').textContent = 'Reset link sent';
    
    document.getElementById('successIcon').style.display = 'flex';
    document.getElementById('successTitle').textContent = 'Email Sent!';
    document.getElementById('successMessage').textContent = 
        `We've sent a password reset link to you. Click the link in the email to reset your password.`;
}

function showPasswordResetSuccess() {
    document.getElementById('email-form-state').classList.add('hidden');
    document.getElementById('password-form-state').classList.add('hidden');
    document.getElementById('success-state').classList.remove('hidden');
    
    document.getElementById('pageTitle').textContent = 'Password Reset!';
    document.getElementById('pageSubtitle').textContent = 'Success';
    
    document.getElementById('successIcon').style.display = 'flex';
    document.getElementById('successTitle').textContent = 'Password Updated!';
    document.getElementById('successMessage').textContent = 
        'Your password has been successfully reset. You can now sign in with your new password.';
    
    // Update the links
    const linksDiv = document.querySelector('#success-state .auth-links');
    linksDiv.innerHTML = `
        <a href="/login">← Sign In Now</a>
        <div class="link-divider">or</div>
        <a href="/">Go to Homepage</a>
    `;
}

function validatePasswordRequirements(password) {
    const requirements = {
        'req-length': password.length >= 8,
        'req-uppercase': /[A-Z]/.test(password),
        'req-lowercase': /[a-z]/.test(password),
        'req-number': /\d/.test(password),
        'req-special': /[!@#$%^&*(),.?":{}|<>]/.test(password)
    };
    
    for (const [reqId, isValid] of Object.entries(requirements)) {
        const element = document.getElementById(reqId);
        if (isValid) {
            element.classList.add('valid');
        } else {
            element.classList.remove('valid');
        }
    }
    
    return Object.values(requirements).every(req => req);
}

function validatePassword(password) {
    return password.length >= 8 &&
            /[A-Z]/.test(password) &&
            /[a-z]/.test(password) &&
            /\d/.test(password) &&
            /[!@#$%^&*(),.?":{}|<>]/.test(password);
}

function showPasswordMatchError() {
    document.getElementById('passwordMatchMessage').classList.remove('hidden');
}

function hidePasswordMatchError() {
    document.getElementById('passwordMatchMessage').classList.add('hidden');
}

function showMessage(containerId, message, type) {
    const container = document.getElementById(containerId);
    container.innerHTML = `<div class="form-message ${type}">${message}</div>`;
}

document.getElementById('resendEmailBtn')?.addEventListener('click', function(e) {
    e.preventDefault();
    
    const btn = this;
    const originalText = btn.textContent;
    btn.textContent = 'Sending...';
    btn.style.pointerEvents = 'none';
    
    fetch('/resend-password-reset', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: `email={{ email }}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            btn.textContent = 'Email Sent!';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.pointerEvents = 'auto';
            }, 3000);
        } else {
            btn.textContent = 'Failed - Try Again';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.pointerEvents = 'auto';
            }, 2000);
        }
    });
});