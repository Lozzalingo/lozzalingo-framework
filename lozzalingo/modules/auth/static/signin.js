// Form submission handler
document.getElementById('signinForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    const messageContainer = document.getElementById('messageContainer');
    
    // Clear previous messages
    messageContainer.innerHTML = '';
    
    // Show loading state
    const submitBtn = this.querySelector('.submit-btn');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Signing In...';
    submitBtn.disabled = true;
    
    // Send AJAX request
    fetch(this.action, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        // Reset button
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
        
        if (data.success) {
            showMessage(data.message, 'success');
            setTimeout(() => {
                window.location.href = data.redirect;
            }, 1500);
        } else {
            showMessage(data.message, 'error');

            // Show resend verification email option if needed
            if (data.show_resend && data.email) {
                showResendVerificationOption(data.email);
            }

            // Show registration prompt on invalid credentials
            if (data.message === 'Invalid email or password') {
                showRegistrationPrompt();
            }
        }
    })
    .catch(error => {
        // Reset button
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
        
        showMessage('An error occurred. Please try again.', 'error');
        console.error('Error:', error);
    });
});

function showMessage(text, type) {
    const messageContainer = document.getElementById('messageContainer');
    const message = document.createElement('div');
    message.className = `form-message ${type}`;
    message.textContent = text;
    messageContainer.appendChild(message);
}

function showResendVerificationOption(email) {
    const messageContainer = document.getElementById('messageContainer');
    
    // Create resend verification container
    const resendContainer = document.createElement('div');
    resendContainer.className = 'resend-verification-container';
    
    // Create resend button
    const resendBtn = document.createElement('button');
    resendBtn.type = 'button';
    resendBtn.className = 'resend-verification-btn';
    resendBtn.textContent = 'Resend Verification Email';
    
    // Add click handler for resend functionality
    resendBtn.addEventListener('click', function() {
        resendVerificationEmail(email, this);
    });
    
    resendContainer.appendChild(resendBtn);
    messageContainer.appendChild(resendContainer);
}

function resendVerificationEmail(email, button) {
    // Show loading state
    const originalText = button.textContent;
    button.textContent = 'Sending...';
    button.disabled = true;
    
    // Create form data
    const formData = new FormData();
    formData.append('email', email);
    
    // Send resend request
    fetch('/resend-verification', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        // Reset button
        button.textContent = originalText;
        button.disabled = false;
        
        if (data.success) {
            showMessage(data.message, 'success');
            // Hide the resend container after successful send
            button.parentElement.style.display = 'none';
        } else {
            showMessage(data.message, 'error');
        }
    })
    .catch(error => {
        // Reset button
        button.textContent = originalText;
        button.disabled = false;
        
        showMessage('Failed to resend verification email. Please try again.', 'error');
        console.error('Error:', error);
    });
}

function showRegistrationPrompt() {
    const messageContainer = document.getElementById('messageContainer');
    const prompt = document.createElement('div');
    prompt.className = 'form-message info';
    prompt.innerHTML = 'Don\'t have an account? <a href="/register" style="font-weight:700;text-decoration:underline;">Create one here</a>';
    messageContainer.appendChild(prompt);
}

// Auto-focus first input if no OAuth messages
document.addEventListener('DOMContentLoaded', function() {
    if (!document.querySelector('.form-message')) {
        document.getElementById('email').focus();
    }
});