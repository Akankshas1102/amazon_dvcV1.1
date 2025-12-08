// frontend/login.js - FIXED VERSION
// ============================================
// Login page with proper redirect logic
// ============================================

console.log('[Login] Page loaded');

document.addEventListener('DOMContentLoaded', () => {
    console.log('[Login] DOM ready, checking authentication...');
    
    // Check if already logged in
    const token = localStorage.getItem('adminToken');
    if (token) {
        console.log('[Login] Token found, verifying...');
        // Verify token is still valid
        verifyTokenAndRedirect(token);
    } else {
        console.log('[Login] No token found, showing login form');
    }
    
    // Setup form submission
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
        console.log('[Login] Form handler attached');
    } else {
        console.error('[Login] Login form not found!');
    }
});

/**
 * Verify if stored token is still valid
 */
async function verifyTokenAndRedirect(token) {
    try {
        console.log('[Login] Verifying token with server...');
        const response = await fetch('http://127.0.0.1:7070/api/admin/queries', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            console.log('[Login] Token is valid, redirecting to main app...');
            // Token is valid, redirect to main app
            window.location.replace('/');
        } else {
            console.log('[Login] Token is invalid, clearing...');
            // Token is invalid, clear it
            localStorage.removeItem('adminToken');
            localStorage.removeItem('adminUsername');
        }
    } catch (error) {
        console.error('[Login] Token verification error:', error);
        // On error, clear token to be safe
        localStorage.removeItem('adminToken');
        localStorage.removeItem('adminUsername');
    }
}

/**
 * Handle login form submission
 */
async function handleLogin(event) {
    event.preventDefault();
    
    const loginButton = document.getElementById('loginButton');
    const errorMessage = document.getElementById('errorMessage');
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    console.log('[Login] Login attempt for user:', username);
    
    // Disable button and show loading state
    loginButton.disabled = true;
    loginButton.textContent = 'Logging in...';
    errorMessage.classList.remove('show');
    
    try {
        console.log('[Login] Sending login request...');
        const response = await fetch('http://127.0.0.1:7070/api/admin/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                password: password
            })
        });
        
        const data = await response.json();
        console.log('[Login] Server response:', response.ok ? 'Success' : 'Failed');
        
        if (response.ok) {
            // Login successful
            console.log('[Login] Login successful, storing token...');
            
            // Store token and username in localStorage
            localStorage.setItem('adminToken', data.access_token);
            localStorage.setItem('adminUsername', data.username);
            
            console.log('[Login] Token stored, redirecting to main app...');
            
            // Show success message briefly
            showError('Login successful! Redirecting...', false);
            
            // Redirect after a brief delay
            setTimeout(() => {
                window.location.replace('/');
            }, 500);
        } else {
            // Login failed
            console.log('[Login] Login failed:', data.detail);
            showError(data.detail || 'Invalid credentials. Please try again.');
            loginButton.disabled = false;
            loginButton.textContent = 'Login';
        }
    } catch (error) {
        console.error('[Login] Login error:', error);
        showError('Connection error. Please check if the server is running.');
        loginButton.disabled = false;
        loginButton.textContent = 'Login';
    }
}

/**
 * Display error/success message
 */
function showError(message, isError = true) {
    const errorMessage = document.getElementById('errorMessage');
    errorMessage.textContent = message;
    errorMessage.style.backgroundColor = isError ? '#fee2e2' : '#d1fae5';
    errorMessage.style.color = isError ? '#dc2626' : '#059669';
    errorMessage.classList.add('show');
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        errorMessage.classList.remove('show');
    }, 5000);
}