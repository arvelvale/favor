/**
 * 通用弹窗组件 - toast-message.js
 * 提供简单易用的消息通知功能
 */

// 创建一个立即执行的匿名函数，避免污染全局命名空间
(function() {
    // 创建存放弹窗的容器
    let container = null;
    
    // 初始化容器
    function initContainer() {
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }
    
    // 创建弹窗元素
    function createToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast-message toast-${type}`;
        
        // 根据类型选择图标
        let icon = '';
        switch (type) {
            case 'success':
                icon = '<i class="fas fa-check-circle"></i>';
                break;
            case 'error':
                icon = '<i class="fas fa-times-circle"></i>';
                break;
            case 'warning':
                icon = '<i class="fas fa-exclamation-triangle"></i>';
                break;
            default:
                icon = '<i class="fas fa-info-circle"></i>';
                break;
        }
        
        // 构建弹窗HTML结构
        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-content">${message}</div>
            <div class="toast-close"><i class="fas fa-times"></i></div>
            <div class="toast-progress">
                <div class="toast-progress-bar"></div>
            </div>
        `;
        
        // 设置进度条动画时长
        const progressBar = toast.querySelector('.toast-progress-bar');
        progressBar.style.animationDuration = `${duration}ms`;
        
        // 添加关闭事件
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => {
            removeToast(toast);
        });
        
        // 自动关闭
        if (duration > 0) {
            setTimeout(() => {
                removeToast(toast);
            }, duration);
        }
        
        return toast;
    }
    
    // 移除弹窗
    function removeToast(toast) {
        toast.classList.add('toast-hide');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
            
            // 如果容器中没有弹窗了，移除容器
            if (container && container.children.length === 0) {
                document.body.removeChild(container);
                container = null;
            }
        }, 300); // 等待动画完成
    }
    
    // 暴露给全局的API
    window.toastMessage = {
        // 显示一般信息
        info: function(message, duration = 3000) {
            const containerElem = initContainer();
            const toast = createToast(message, 'info', duration);
            containerElem.appendChild(toast);
            return toast;
        },
        
        // 显示成功信息
        success: function(message, duration = 3000) {
            const containerElem = initContainer();
            const toast = createToast(message, 'success', duration);
            containerElem.appendChild(toast);
            return toast;
        },
        
        // 显示警告信息
        warning: function(message, duration = 3000) {
            const containerElem = initContainer();
            const toast = createToast(message, 'warning', duration);
            containerElem.appendChild(toast);
            return toast;
        },
        
        // 显示错误信息
        error: function(message, duration = 3000) {
            const containerElem = initContainer();
            const toast = createToast(message, 'error', duration);
            containerElem.appendChild(toast);
            return toast;
        },
        
        // 关闭指定的弹窗
        close: function(toast) {
            if (toast) {
                removeToast(toast);
            }
        },
        
        // 关闭所有弹窗
        closeAll: function() {
            if (container) {
                const toasts = container.querySelectorAll('.toast-message');
                toasts.forEach(toast => {
                    removeToast(toast);
                });
            }
        }
    };
})(); 