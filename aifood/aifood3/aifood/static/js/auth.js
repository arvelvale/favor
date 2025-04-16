// Countdown timer function
function startCountdown(button, seconds) {
    button.classList.add('disabled');
    const originalText = button.textContent;
    
    let remainingSeconds = seconds;
    
    button.textContent = `${remainingSeconds}s`;
    
    const countdownInterval = setInterval(() => {
        remainingSeconds--;
        
        if (remainingSeconds <= 0) {
            clearInterval(countdownInterval);
            button.textContent = originalText;
            button.classList.remove('disabled');
        } else {
            button.textContent = `${remainingSeconds}s`;
        }
    }, 1000);
    
    // 保存倒计时interval ID以便可以停止
    button.dataset.countdownInterval = countdownInterval;
}

// 添加全局停止倒计时函数
function stopCountdown(button) {
    if (button.dataset.countdownInterval) {
        clearInterval(button.dataset.countdownInterval);
    }
    button.classList.remove('disabled');
    button.textContent = 'Get Code';
}

// 防抖函数 - 防止短时间内多次触发同一事件
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

document.addEventListener('DOMContentLoaded', function() {
    // Form validation tools
    const validators = {
        username: {
            pattern: /^[a-zA-Z0-9_]{3,20}$/,
            errorMessage: 'Username must be 3-20 characters and can only contain letters, numbers, and underscores'
        },
        email: {
            pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
            errorMessage: 'Please enter a valid email address'
        },
        password: {
            // 修改密码验证规则，要求同时包含数字、字母和特殊字符
            pattern: /^(?=.*[0-9])(?=.*[a-zA-Z])(?=.*[@#!%^&*;'":,.?/])[a-zA-Z0-9@#!%^&*;'":,.?/]{8,}$/,
            errorMessage: 'Password must be at least 8 characters and include numbers, letters, and special characters (@#!%^&*;\'":,.?/)'
        },
        // Add phone number validation
        phone: {
            pattern: /^1[3-9]\d{9}$/,
            errorMessage: 'Phone number should be 11 digits and start with 1'
        },
        // Add verification code validation
        verificationCode: {
            pattern: /^\d{6}$/,
            errorMessage: 'Verification code should be 6 digits'
        }
    };
    
    // 通用函数：显示错误消息
    function showError(message) {
        const errorMessage = document.getElementById('error-message');
        if (errorMessage) {
            errorMessage.textContent = message;
            errorMessage.style.opacity = 1;
            
            // 5秒后隐藏错误消息
            setTimeout(() => {
                errorMessage.style.opacity = 0;
            }, 5000);
        }
    }
    
    // 初始化获取验证码按钮
    function initGetCodeButtons() {
        const getCodeBtn = document.getElementById('get-code-btn');
        if (getCodeBtn) {
            // 标记按钮状态，防止重复点击
            getCodeBtn.dataset.isProcessing = 'false';
            
            // 使用防抖处理点击事件
            const handleGetCodeClick = debounce(function() {
                // 如果按钮已禁用或正在处理中，直接返回
                if (this.classList.contains('disabled') || this.dataset.isProcessing === 'true') return;
                
                const emailInput = document.getElementById('email');
                if (!emailInput) return;
                
                const emailValue = emailInput.value.trim();
                // 使用严格的邮箱验证
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                
                if (!emailValue || !emailRegex.test(emailValue)) {
                    showError('Please enter a valid email address');
                    emailInput.focus();
                    
                    // 在错误的输入框旁添加可视化反馈
                    const feedbackEl = document.getElementById('email-feedback');
                    if (feedbackEl) {
                        feedbackEl.textContent = 'Please enter a valid email address';
                        feedbackEl.style.color = 'var(--error-color)';
                        
                        // 5秒后清除反馈
                        setTimeout(() => {
                            feedbackEl.textContent = '';
                        }, 5000);
                    }
                    return;
                }
                
                // 设置按钮为处理中状态
                this.dataset.isProcessing = 'true';
                
                // 立即禁用按钮，防止重复点击
                this.classList.add('disabled');
                
                // 显示按钮加载状态
                this.classList.add('loading');
                
                // 发送验证码请求
                
                // <<< 新增：判断当前操作场景 >>>
                let action = 'login'; // 默认是登录
                if (window.location.pathname.includes('/register')) {
                    action = 'register';
                } else if (window.location.pathname.includes('/verification-login')) {
                    // verification-login 页面同时用于登录和重置密码，
                    // 但后端逻辑目前将 'login' 和 'reset_password' 处理逻辑相同
                    // （都需要邮箱已注册），所以用 'login' 或 'reset_password' 都可以。
                    // 为清晰起见，可以维持 'login' 或明确指定 'reset_password'
                    action = 'login'; // 或者 'reset_password'
                }
                // <<< 结束新增 >>>
                
                fetch('/api/send-verification-code', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        email: emailValue,
                        action: action // <<< 修改：添加 action 参数 >>>
                    })
                })
                .then(response => response.json())
                .then(data => {
                    // 隐藏加载状态
                    this.classList.remove('loading');
                    
                    // 重置处理状态
                    this.dataset.isProcessing = 'false';
                    
                    if (data.success) {
                        // 显示成功消息
                        const feedbackEl = document.getElementById('email-feedback');
                        if (feedbackEl) {
                            feedbackEl.textContent = 'Verification code sent!';
                            feedbackEl.style.color = 'var(--success-color)';
                        }
                        
                        // 开始倒计时
                        startCountdown(this, 60);
                    } else {
                        // 显示错误消息
                        showError(data.message || 'Failed to send verification code. Please try again.');
                        
                        // 如果失败，重新启用按钮
                        this.classList.remove('disabled');
                    }
                })
                .catch(error => {
                    // 隐藏加载状态
                    this.classList.remove('loading');
                    
                    // 重置处理状态
                    this.dataset.isProcessing = 'false';
                    
                    // 重新启用按钮
                    this.classList.remove('disabled');
                    
                    showError('An error occurred. Please try again later.');
                    console.error('Error:', error);
                });
            }, 300); // 300ms防抖延迟
            
            getCodeBtn.addEventListener('click', handleGetCodeClick);
        }
    }
    
    // 在DOM加载完成后初始化获取验证码按钮
    initGetCodeButtons();
    
    // Add field validation
    function addFieldValidation(input, type, isLoginForm = false) {
        if (!validators[type]) return;
        
        const validator = validators[type];
        const formGroup = input.closest('.form-group'); // 找到最近的 .form-group 父元素
        if (!formGroup) return; // 如果找不到，则退出
        
        // 查找或创建验证消息元素，确保它在 form-group 内，但在 input/button 行之后
        let validationMessage = formGroup.querySelector('.validation-message');
        if (!validationMessage) {
            validationMessage = document.createElement('div');
            validationMessage.className = 'validation-message';
            formGroup.appendChild(validationMessage); // 添加到 form-group 的末尾
        }
        
        // Add input event listener
        input.addEventListener('input', function() {
            const value = input.value.trim();
            
            if (value === '') {
                validationMessage.textContent = '';
                validationMessage.className = 'validation-message';
                return;
            }
            
            // 修改：对邮箱输入也使用严格的实时格式验证
            // 不再对 email 类型做特殊处理，统一使用 validator.pattern
            if (validator.pattern.test(value)) {
                validationMessage.textContent = '✓ Valid format';
                validationMessage.className = 'validation-message validation-success';
                
                // 如果是用户名字段且格式正确，移除可能的"用户名已存在"错误
                if (type === 'username' && input.dataset.usernameExists === 'true') {
                    input.dataset.usernameExists = 'false';
                }
            } else {
                validationMessage.textContent = validator.errorMessage;
                validationMessage.className = 'validation-message validation-error';
            }
        });
        
        // 对用户名字段添加额外的唯一性检查 - 仅在注册表单中
        if (type === 'username' && !isLoginForm) {
            // 初始化dataset标记
            input.dataset.usernameExists = 'false';
            input.dataset.checkingUsername = 'false';
            
            // 添加失焦事件监听器
            input.addEventListener('blur', function() {
                const value = input.value.trim();
                
                // 如果用户名为空或格式不正确，不检查唯一性
                if (value === '' || !validator.pattern.test(value)) {
                    return;
                }
                
                // 避免重复检查相同的用户名
                if (input.dataset.lastCheckedUsername === value) {
                    return;
                }
                
                // 设置正在检查状态
                input.dataset.checkingUsername = 'true';
                input.dataset.lastCheckedUsername = value;
                
                // 更新验证消息
                validationMessage.textContent = 'Checking username availability...';
                validationMessage.className = 'validation-message validation-checking';
                
                // 调用API检查用户名是否已存在
                fetch('/api/check-username', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        username: value
                    })
                })
                .then(response => response.json())
                .then(data => {
                    // 重置检查状态
                    input.dataset.checkingUsername = 'false';
                    
                    if (data.available) {
                        // 用户名可用
                        validationMessage.textContent = '✓ Username available';
                        validationMessage.className = 'validation-message validation-success';
                        input.dataset.usernameExists = 'false';
                    } else {
                        // 用户名已存在
                        validationMessage.textContent = data.message || 'Username already exists';
                        validationMessage.className = 'validation-message validation-error';
                        input.dataset.usernameExists = 'true';
                    }
                })
                .catch(error => {
                    // 处理错误
                    input.dataset.checkingUsername = 'false';
                    validationMessage.textContent = 'Error checking username';
                    validationMessage.className = 'validation-message validation-error';
                    console.error('Error checking username:', error);
                });
            });
        }
    }
    
    // Login form handling
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        const usernameInput = loginForm.querySelector('#username');
        const passwordInput = loginForm.querySelector('#password');
        const submitButton = loginForm.querySelector('.btn-submit');
        
        // Add field validation
        addFieldValidation(usernameInput, 'username', true);
        addFieldValidation(passwordInput, 'password', true);
        
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const username = usernameInput.value.trim();
            const password = passwordInput.value.trim();
            const remember = loginForm.querySelector('#remember').checked;
            
            // Form validation
            if (!username || !password) {
                showError('Please fill in all required fields');
                return;
            }
            
            // Show loading state
            submitButton.classList.add('loading');
            
            // Login request
            fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    username: username,
                    password: password,
                    remember: remember
                })
            })
            .then(response => response.json())
            .then(data => {
                // Hide loading state
                submitButton.classList.remove('loading');
                
                if (data.success) {
                    // Login successful, show success animation
                    submitButton.innerHTML = '<i class="fas fa-check"></i> Success';
                    submitButton.style.backgroundColor = 'var(--success-color)';
                    
                    // Redirect to home page
                    setTimeout(() => {
                    window.location.href = '/';
                    }, 1000);
                } else {
                    // Show error message
                    showError(data.message || 'Login failed. Please check your username and password');
                    
                    // Slightly shake the form
                    loginForm.classList.add('shake');
                    setTimeout(() => {
                        loginForm.classList.remove('shake');
                    }, 500);
                }
            })
            .catch(error => {
                // Hide loading state
                submitButton.classList.remove('loading');
                
                showError('An error occurred. Please try again later');
                console.error('Error:', error);
            });
        });
    }
    
    // Registration form handling
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        const usernameInput = registerForm.querySelector('#username');
        const emailInput = registerForm.querySelector('#email');
        const verificationCodeInput = registerForm.querySelector('#verification-code');
        const passwordInput = registerForm.querySelector('#password');
        const confirmPasswordInput = registerForm.querySelector('#confirm-password');
        const submitButton = registerForm.querySelector('.btn-submit');
        const getCodeBtn = registerForm.querySelector('#get-code-btn');
        const errorMessage = document.getElementById('error-message');
        const successMessage = document.getElementById('success-message');
        
        // 为输入字段添加验证
        addFieldValidation(usernameInput, 'username');
        addFieldValidation(emailInput, 'email');
        addFieldValidation(verificationCodeInput, 'verificationCode');
        addFieldValidation(passwordInput, 'password');
        
        // 添加密码强度检测
        passwordInput.addEventListener('input', function() {
            const password = this.value;
            const requirements = [];
            
            // 检查各项要求
            const hasNumber = /[0-9]/.test(password);
            const hasLetter = /[a-zA-Z]/.test(password);
            const hasSpecial = /[@#!%^&*;'":,.?/]/.test(password);
            const isLongEnough = password.length >= 8;
            
            // 计算强度分数 (0-3)
            let score = 0;
            if (hasNumber) score++;
            if (hasLetter) score++;
            if (hasSpecial) score++;
            
            // 获取或创建强度指示器
            let strengthIndicator = this.parentNode.parentNode.querySelector('.password-strength');
            if (!strengthIndicator) {
                strengthIndicator = document.createElement('div');
                strengthIndicator.className = 'password-strength';
                this.parentNode.parentNode.insertBefore(strengthIndicator, document.querySelector('.password-requirements'));
            }
            
            // 显示强度
            if (password.length === 0) {
                strengthIndicator.style.display = 'none';
            } else {
                strengthIndicator.style.display = 'block';
                
                // 设置强度等级
                if (score === 3 && isLongEnough) {
                    strengthIndicator.textContent = 'Strong password';
                    strengthIndicator.className = 'password-strength strong';
                } else if (score >= 2 && isLongEnough) {
                    strengthIndicator.textContent = 'Medium password';
                    strengthIndicator.className = 'password-strength medium';
                } else {
                    strengthIndicator.textContent = 'Weak password';
                    strengthIndicator.className = 'password-strength weak';
                }
            }
        });
        
        // 添加密码确认验证
        confirmPasswordInput.addEventListener('input', function() {
            const password = passwordInput.value;
            const confirmPassword = this.value;
            
            // 获取或创建验证消息元素
            let confirmMessage = this.parentNode.parentNode.querySelector('.confirm-validation-message');
            if (!confirmMessage) {
                confirmMessage = document.createElement('div');
                confirmMessage.className = 'validation-message confirm-validation-message';
                this.parentNode.parentNode.appendChild(confirmMessage);
            }
            
            // 验证密码匹配
            if (confirmPassword === '') {
                confirmMessage.textContent = '';
                confirmMessage.className = 'validation-message confirm-validation-message';
            } else if (password === confirmPassword) {
                confirmMessage.textContent = '✓ Passwords match';
                confirmMessage.className = 'validation-message confirm-validation-message validation-success';
            } else {
                confirmMessage.textContent = 'Passwords do not match';
                confirmMessage.className = 'validation-message confirm-validation-message validation-error';
            }
        });
        
        // 表单提交处理
        registerForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // 获取表单数据
            const username = usernameInput.value.trim();
            const email = emailInput.value.trim();
            const verificationCode = verificationCodeInput.value.trim();
            const password = passwordInput.value.trim();
            const confirmPassword = confirmPasswordInput.value.trim();
            
            // 表单验证
            if (!username || !email || !verificationCode || !password || !confirmPassword) {
                showError('Please fill in all required fields');
                return;
            }
            
            // 验证用户名格式
            if (!validators.username.pattern.test(username)) {
                showError(validators.username.errorMessage);
                usernameInput.focus();
                return;
            }
            
            // 验证邮箱格式
            if (!validators.email.pattern.test(email)) {
                showError(validators.email.errorMessage);
                emailInput.focus();
                return;
            }
            
            // 验证验证码格式
            if (!validators.verificationCode.pattern.test(verificationCode)) {
                showError(validators.verificationCode.errorMessage);
                verificationCodeInput.focus();
                return;
            }
            
            // 新增：验证密码格式
            if (!validators.password.pattern.test(password)) {
                showError(validators.password.errorMessage);
                // 同时在密码输入框下方显示错误（如果验证消息元素存在）
                const passwordValidationMsg = passwordInput.parentNode.parentNode.querySelector('.validation-message');
                if (passwordValidationMsg) {
                    passwordValidationMsg.textContent = validators.password.errorMessage;
                    passwordValidationMsg.className = 'validation-message validation-error';
                }
                passwordInput.focus();
                return;
            }
            
            // 验证密码匹配
            if (password !== confirmPassword) {
                showError('Passwords do not match');
                confirmPasswordInput.focus();
                return;
            }
            
            // 检查用户名是否正在验证中
            if (usernameInput.dataset.checkingUsername === 'true') {
                showError('Please wait while we check username availability');
                return;
            }
            
            // 检查用户名是否已存在
            if (usernameInput.dataset.usernameExists === 'true') {
                showError('Username is already taken');
                usernameInput.focus();
                return;
            }
            
            // 显示加载状态
            submitButton.classList.add('loading');
            
            // 首先验证验证码
            fetch('/api/verify-code', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email,
                    code: verificationCode
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // 验证码验证成功，继续注册
                    return fetch('/api/register', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            username: username,
                            email: email,
                            password: password
                        })
                    });
                } else {
                    // 验证码验证失败
                    throw new Error(data.message || 'Invalid verification code');
                }
            })
            .then(response => response.json())
            .then(data => {
                // 隐藏加载状态
                submitButton.classList.remove('loading');
                
                if (data.success) {
                    // 注册成功，显示成功动画
                    submitButton.innerHTML = '<i class="fas fa-check"></i> Success';
                    submitButton.style.backgroundColor = 'var(--success-color)';
                    
                    // 显示成功消息
                    if (successMessage) {
                        successMessage.textContent = 'Registration successful! Redirecting to login page...';
                        successMessage.style.opacity = 1;
                    }
                    
                    // 重定向到登录页面
                    setTimeout(() => {
                        window.location.href = '/login';
                    }, 2000);
                } else {
                    // 显示错误消息
                    showError(data.message || 'Registration failed. Please try again.');
                    
                    // 轻微抖动表单
                    registerForm.classList.add('shake');
                    setTimeout(() => {
                        registerForm.classList.remove('shake');
                    }, 500);
                }
            })
            .catch(error => {
                // 隐藏加载状态
                submitButton.classList.remove('loading');
                
                showError(error.message || 'An error occurred. Please try again later.');
                console.error('Error:', error);
            });
        });
    }
    
    // Verification login form handling
    const verificationForm = document.getElementById('verification-form');
    if (verificationForm) {
        const emailInput = verificationForm.querySelector('#email');
        const verificationCodeInput = verificationForm.querySelector('#verification-code');
        const submitButton = verificationForm.querySelector('.btn-submit');
        
        // 添加字段验证
        addFieldValidation(emailInput, 'email');
        addFieldValidation(verificationCodeInput, 'verificationCode');
        
        // 表单提交处理
        verificationForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // 获取表单数据
            const email = emailInput.value.trim();
            const verificationCode = verificationCodeInput.value.trim();
            
            // 表单验证
            if (!email || !verificationCode) {
                showError('Please fill in all required fields');
                return;
            }
            
            // 验证邮箱格式
            if (!validators.email.pattern.test(email)) {
                showError(validators.email.errorMessage);
                emailInput.focus();
                return;
            }
            
            // 验证验证码格式
            if (!validators.verificationCode.pattern.test(verificationCode)) {
                showError(validators.verificationCode.errorMessage);
                verificationCodeInput.focus();
                return;
            }
            
            // 显示加载状态
            submitButton.classList.add('loading');
            
            // 发送验证码登录请求
            fetch('/api/verify-code-login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email,
                    code: verificationCode
                })
            })
            .then(response => response.json())
            .then(data => {
                // 隐藏加载状态
                submitButton.classList.remove('loading');
                
                if (data.success) {
                    // 登录成功，显示成功动画
                    submitButton.innerHTML = '<i class="fas fa-check"></i> Success';
                    submitButton.style.backgroundColor = 'var(--success-color)';
                    
                    // 重定向到指定页面或首页
                    setTimeout(() => {
                        window.location.href = data.redirect || '/';
                    }, 1000);
                } else {
                    // 显示错误消息
                    showError(data.message || 'Login failed. Please check your email and verification code.');
                    
                    // 轻微抖动表单
                    verificationForm.classList.add('shake');
                    setTimeout(() => {
                        verificationForm.classList.remove('shake');
                    }, 500);
                }
            })
            .catch(error => {
                // 隐藏加载状态
                submitButton.classList.remove('loading');
                
                showError('An error occurred. Please try again later.');
                console.error('Error:', error);
            });
        });
    }
});
