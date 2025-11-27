// Password validation
const password = document.getElementById('password');
const confirmPassword = document.getElementById('confirm_password');
const lengthReq = document.getElementById('length-req');
const letterReq = document.getElementById('letter-req');
const numberReq = document.getElementById('number-req');

password.addEventListener('input', function() {
    const value = this.value;
    
    // Check length
    if (value.length >= 8) {
        lengthReq.classList.add('valid');
    } else {
        lengthReq.classList.remove('valid');
    }
    
    // Check uppercase letters
    if (/[A-Z]/.test(value)) {
        document.getElementById('upper-req').classList.add('valid');
    } else {
        document.getElementById('upper-req').classList.remove('valid');
    }
    
    // Check lowercase letters
    if (/[a-z]/.test(value)) {
        document.getElementById('lower-req').classList.add('valid');
    } else {
        document.getElementById('lower-req').classList.remove('valid');
    }
    
    // Check numbers
    if (/\d/.test(value)) {
        numberReq.classList.add('valid');
    } else {
        numberReq.classList.remove('valid');
    }
});

// Confirm password validation
confirmPassword.addEventListener('input', function() {
    if (this.value !== password.value) {
        this.setCustomValidity('Passwords do not match');
    } else {
        this.setCustomValidity('');
    }
});

// Form submission handler
// Form submission handler
document.getElementById('registerForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData(this);
    const messageContainer = document.getElementById('messageContainer');

    // Clear previous messages
    messageContainer.innerHTML = '';

    // Show loading state
    const submitBtn = this.querySelector('.submit-btn');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Creating Account...';
    submitBtn.disabled = true;

    // Send AJAX request
    fetch(this.action, {
        method: 'POST',
        body: formData
    })
    .then(response => {
        // Always parse JSON, even for errors
        return response.json().then(data => {
            if (!response.ok) {
                // Force error flow with backend's message
                throw data;
            }
            return data;
        });
    })
    .then(data => {
        // Reset button
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;

        if (data.success) {
            showMessageAboveButton(data.message, 'success');
            // Uncomment if you want redirect after short delay
            // setTimeout(() => window.location.href = data.redirect, 1500);
        } else {
            showMessage(data.message, 'error');
        }
    })
    .catch(error => {
        // Reset button
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;

        // Show backend message if available
        if (error && error.message) {
            showMessage(error.message, 'error');
        } else {
            showMessage('An unexpected error occurred. Please try again.', 'error');
        }

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

document.getElementById('resendEmailBtn')?.addEventListener('click', function(e) {
    e.preventDefault();
    
    const btn = this;
    const originalText = btn.textContent;
    btn.textContent = 'Sending...';
    
    fetch('/forgot-password', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: `email={{ email }}`
    })
    .then(() => {
        btn.textContent = 'Email Sent!';
        setTimeout(() => {
            btn.textContent = originalText;
        }, 3000);
    });
});

function showMessageAboveButton(text, type) {
    const submitBtn = document.querySelector('.submit-btn');
    const message = document.createElement('div');
    message.className = `form-message ${type}`;
    message.textContent = text;
    submitBtn.parentNode.insertBefore(message, submitBtn);
}

// Auto-focus first input if no OAuth messages
document.addEventListener('DOMContentLoaded', function() {
    if (!document.querySelector('.form-message')) {
        document.getElementById('first_name').focus();
    }
});

