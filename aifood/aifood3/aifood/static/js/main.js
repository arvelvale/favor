// 全局变量
let selectedIngredients = [];
let recipeMode = 'partial'; // 默认为冒险模式

document.addEventListener('DOMContentLoaded', function() {
    // 初始化元素引用
    const ingredientSearch = document.getElementById('ingredient-search');
    const addIngredientBtn = document.getElementById('add-ingredient');
    const ingredientsList = document.getElementById('ingredients-list');
    const generateBtn = document.getElementById('generate-btn');
    const recipeResult = document.getElementById('recipe-result');
    const recipeContent = document.getElementById('recipe-content');
    const saveRecipeBtn = document.getElementById('save-recipe');
    const generateImagesBtn = document.getElementById('generate-images-btn');
    const recipeImages = document.getElementById('recipe-images');
    const loadingIndicator = document.getElementById('loading');
    const autocompleteResults = document.getElementById('autocomplete-results');
    const dynamicFeedback = document.getElementById('dynamic-feedback');
    const emptyState = document.getElementById('empty-state');
    
    // 模式选择
    const modePartial = document.getElementById('mode-partial');
    const modeAll = document.getElementById('mode-all');
    
    // 监听模式选择
    modePartial.addEventListener('change', function() {
        if (this.checked) {
            recipeMode = 'partial';
        }
    });
    
    modeAll.addEventListener('change', function() {
        if (this.checked) {
            recipeMode = 'all';
        }
    });
    
    // 自动完成功能
    let debounceTimer;
    ingredientSearch.addEventListener('input', function() {
        const query = this.value.trim();
        
        // 更新动态反馈
        updateDynamicFeedback(query);
        
        // 清除之前的定时器
        clearTimeout(debounceTimer);
        
        if (query.length < 2) {
            autocompleteResults.innerHTML = '';
            autocompleteResults.style.display = 'none';
            return;
        }
        
        // 设置新的定时器
        debounceTimer = setTimeout(() => {
            fetch(`/api/autocomplete?q=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(data => {
                    displayAutocompleteResults(data);
                })
                .catch(error => {
                    console.error('Error fetching autocomplete results:', error);
                });
        }, 300);
    });
    
    // 显示自动完成结果
    function displayAutocompleteResults(results) {
        autocompleteResults.innerHTML = '';
        
        if (results.length === 0) {
            autocompleteResults.style.display = 'none';
            return;
        }
        
        results.forEach(result => {
            const resultItem = document.createElement('div');
            resultItem.className = 'autocomplete-item';
            resultItem.textContent = result;
            resultItem.addEventListener('click', () => {
                ingredientSearch.value = result;
                autocompleteResults.style.display = 'none';
                addIngredient(result);
            });
            autocompleteResults.appendChild(resultItem);
        });
        
        autocompleteResults.style.display = 'block';
    }
    
    // 更新动态反馈
    function updateDynamicFeedback(query) {
        if (!query) {
            dynamicFeedback.style.display = 'none';
            return;
        }
        
        const ingredientCount = selectedIngredients.length;
        
        if (ingredientCount === 0) {
            dynamicFeedback.textContent = "Great! Click Generate to start";
        } else if (ingredientCount <= 2) {
            dynamicFeedback.textContent = "再加点料？AI在搓手等待～";
        } else if (ingredientCount >= 5) {
            dynamicFeedback.textContent = "Wow，食材派对开始！点击生成→";
        } else {
            dynamicFeedback.textContent = "继续添加更多食材，让AI发挥创意！";
        }
        
        dynamicFeedback.style.display = 'block';
    }
    
    // 添加食材按钮点击事件
    addIngredientBtn.addEventListener('click', function() {
        const ingredient = ingredientSearch.value.trim();
        if (ingredient) {
            addIngredient(ingredient);
        }
    });
    
    // 回车键添加食材
    ingredientSearch.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            const ingredient = this.value.trim();
            if (ingredient) {
                addIngredient(ingredient);
            }
        }
    });
    
    // 添加食材到列表
    function addIngredient(ingredient) {
        if (selectedIngredients.includes(ingredient)) {
            // 已经添加过这个食材
            ingredientSearch.value = '';
            return;
        }
        
        selectedIngredients.push(ingredient);
        
        const tag = document.createElement('div');
        tag.className = 'ingredient-tag';
        tag.innerHTML = `
            ${ingredient}
            <span class="remove-btn" data-ingredient="${ingredient}">×</span>
        `;
        
        ingredientsList.appendChild(tag);
        ingredientSearch.value = '';
        
        // 更新动态反馈
        updateDynamicFeedback('');
        
        // 隐藏空状态
        emptyState.classList.add('hidden');
        
        // 添加删除事件
        tag.querySelector('.remove-btn').addEventListener('click', function() {
            const ingredientToRemove = this.getAttribute('data-ingredient');
            removeIngredient(ingredientToRemove, tag);
        });
    }
    
    // 从列表中移除食材
    function removeIngredient(ingredient, tagElement) {
        const index = selectedIngredients.indexOf(ingredient);
        if (index !== -1) {
            selectedIngredients.splice(index, 1);
        }
        
        tagElement.remove();
        
        // 如果没有食材了，显示空状态
        if (selectedIngredients.length === 0) {
            emptyState.classList.remove('hidden');
        }
        
        // 更新动态反馈
        updateDynamicFeedback('');
    }
    
    // 生成食谱按钮点击事件
    generateBtn.addEventListener('click', function() {
        if (selectedIngredients.length === 0) {
            // 显示空状态提示
            emptyState.classList.remove('hidden');
            recipeResult.classList.add('hidden');
            return;
        }
        
        // 隐藏空状态
        emptyState.classList.add('hidden');
        
        // 显示加载指示器
        loadingIndicator.classList.remove('hidden');
        recipeResult.classList.add('hidden');
        
        // 准备请求数据
        const requestData = {
            ingredients: selectedIngredients,
            temperature: 0.7,
            max_tokens: 2000
        };
        
        // 发送请求
        fetch('/api/generate-recipe-stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            
            // 清空之前的内容
            recipeContent.innerHTML = '';
            
            // 创建一个新的 EventSource 读取器
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            // 显示结果区域
            recipeResult.classList.remove('hidden');
            loadingIndicator.classList.add('hidden');
            
            // 处理流式响应
            function processStream({ done, value }) {
                if (done) {
                    // 流结束，显示生成图片按钮
                    generateImagesBtn.classList.remove('hidden');
                    return;
                }
                
                // 解码并添加到内容
                const chunk = decoder.decode(value, { stream: true });
                recipeContent.innerHTML += marked.parse(chunk);
                
                // 自动滚动到底部
                recipeContent.scrollTop = recipeContent.scrollHeight;
                
                // 继续读取下一块
                return reader.read().then(processStream);
            }
            
            // 开始读取流
            return reader.read().then(processStream);
        })
        .catch(error => {
            console.error('Error generating recipe:', error);
            loadingIndicator.classList.add('hidden');
            recipeContent.innerHTML = '<div class="error-message">Error generating recipe. Please try again.</div>';
            recipeResult.classList.remove('hidden');
        });
    });
    
    // 生成图片按钮点击事件
    generateImagesBtn.addEventListener('click', function() {
        // 显示加载指示器
        loadingIndicator.classList.remove('hidden');
        generateImagesBtn.classList.add('hidden');
        
        // 准备请求数据
        const requestData = {
            recipe: recipeContent.textContent
        };
        
        // 发送请求
        fetch('/api/generate-images', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        })
        .then(response => response.json())
        .then(data => {
            // 隐藏加载指示器
            loadingIndicator.classList.add('hidden');
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            // 显示图片
            displayImages(data.images);
        })
        .catch(error => {
            console.error('Error generating images:', error);
            loadingIndicator.classList.add('hidden');
            generateImagesBtn.classList.remove('hidden');
            alert('Error generating images. Please try again.');
        });
    });
    
    // 显示生成的图片
    function displayImages(images) {
        const imagesContainer = recipeImages.querySelector('.images-container');
        imagesContainer.innerHTML = '';
        
        images.forEach(imageUrl => {
            const imgElement = document.createElement('img');
            imgElement.src = imageUrl;
            imgElement.alt = 'Recipe Visualization';
            imgElement.className = 'recipe-image';
            imagesContainer.appendChild(imgElement);
        });
        
        recipeImages.classList.remove('hidden');
    }
    
    // 保存食谱按钮点击事件
    if (saveRecipeBtn) {
        saveRecipeBtn.addEventListener('click', function() {
            // 获取食谱标题
            const recipeTitle = prompt('请输入食谱名称:', '美味食谱');
            
            if (!recipeTitle) {
                return; // 用户取消
            }
            
            // 准备请求数据
            const requestData = {
                recipe_name: recipeTitle,
                recipe_content: recipeContent.innerHTML,
                ingredients: selectedIngredients.join(', ')
            };
            
            // 发送请求
            fetch('/api/save-recipe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Recipe saved successfully!');
                } else {
                    throw new Error(data.message || 'Failed to save');
                }
            })
            .catch(error => {
                console.error('Error saving recipe:', error);
                alert('Error saving recipe: ' + error.message);
            });
        });
    }
    
    // 点击页面其他地方关闭自动完成
    document.addEventListener('click', function(e) {
        if (!ingredientSearch.contains(e.target) && !autocompleteResults.contains(e.target)) {
            autocompleteResults.style.display = 'none';
        }
    });
});


// 检查并显示使用情况信息
function checkUsageInfo() {
    if (!isUserLoggedIn()) return; // 检查用户是否登录
    
    fetch('/api/get-usage-info')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const usageInfo = document.getElementById('usageInfo');
                const usageMessage = document.getElementById('usageMessage');
                const upgradeBtn = document.getElementById('upgradeToPremium');
                
                usageInfo.style.display = 'block';
                
                const usage = data.usage;
                if (usage.is_premium) {
                    usageInfo.classList.remove('usage-limit-reached');
                    usageInfo.classList.add('premium-user-info');
                    usageMessage.innerHTML = `<strong><i class="fas fa-crown"></i> Premium Member:</strong> Enjoy unlimited recipe generations and exclusive features!`;
                    upgradeBtn.style.display = 'none';
                } else {
                    usageInfo.classList.remove('premium-user-info');
                    usageMessage.innerHTML = `<strong>Free User:</strong> You have used ${usage.used}/${usage.limit} recipe generations today.`;
                    upgradeBtn.style.display = 'inline-block';
                    
                    // 如果已经达到限制，使用红色强调显示
                    if (usage.remaining === 0) {
                        usageInfo.classList.add('usage-limit-reached');
                        usageMessage.innerHTML = `<strong>Limit Reached:</strong> You've used all your free generations today.`;
                    } else {
                        usageInfo.classList.remove('usage-limit-reached');
                    }
                }
            }
        })
        .catch(error => console.error('Error checking usage:', error));
}

// 辅助函数，判断用户是否登录
function isUserLoggedIn() {
    // 检查是否有用户菜单元素或其他登录状态指示
    return document.querySelector('.user-menu') !== null || 
           document.getElementById('userDropdown') !== null;
}

// 显示已达到限制的信息
function showLimitReachedMessage(message) {
    const resultContainer = document.getElementById('recipeResult');
    if (resultContainer) {
        resultContainer.innerHTML = `
            <div class="limit-reached-message">
                <p>${message}</p>
                <a href="/premium" class="premium-link">
                    <i class="fas fa-crown"></i> Upgrade to Premium
                </a>
            </div>
        `;
    }
    
    // 同时更新使用信息显示
    checkUsageInfo();
}

// 修改生成食谱的函数，添加错误处理
function generateRecipe() {
    // 显示加载状态
    showLoading();
    
    // 获取选中的食材
    const ingredients = getSelectedIngredients();
    
    if (ingredients.length === 0) {
        hideLoading();
        showMessage('error', '请至少选择一种食材');
        return;
    }
    
    // 发送请求到后端
    fetch('/api/generate-recipe', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            ingredients: ingredients,
            temperature: 0.7,
            max_tokens: 2000
        })
    })
    .then(response => {
        if (!response.ok) {
            throw response;
        }
        return response.json();
    })
    .then(data => {
        hideLoading();
        
        if (data.recipe) {
            displayRecipe(data.recipe);
            
            // 更新使用情况信息
            if (data.usage) {
                checkUsageInfo();
            }
        } else {
            showMessage('error', 'Error generating recipe. Please try again');
        }
    })
    .catch(error => {
        hideLoading();
        
        // 检查是否是API返回的错误
        if (error.json) {
            error.json().then(errorData => {
                if (errorData.limit_reached) {
                    // 显示限制错误并提示升级
                    showLimitReachedMessage(errorData.error);
                } else {
                    // 显示一般错误
                    showMessage('error', errorData.error || 'Error generating recipe. Please try again');
                }
            }).catch(() => {
                // 如果无法解析JSON，显示一般错误
                showMessage('error', 'Error generating recipe. Please try again');
            });
        } else {
            // 网络错误等
            showMessage('error', '连接服务器时出错，请检查您的网络连接');
        }
    });
}



// 添加一个变量来跟踪是否正在保存
let isSavingRecipe = false;

// 修改保存食谱的函数
function saveRecipe(recipeName, recipeContent, ingredients) {
    // 如果已经在保存中，则返回
    if (isSavingRecipe) return;
    
    // 设置标志为正在保存
    isSavingRecipe = true;
    
    const requestData = {
        recipe_name: recipeName,
        recipe_content: recipeContent,
        ingredients: ingredients
    };
    
    fetch('/api/save-recipe', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Recipe saved successfully!');
        } else {
            throw new Error(data.message || 'Failed to save');
        }
    })
    .catch(error => {
        console.error('Error saving recipe:', error);
        alert('Error saving recipe: ' + error.message);
    })
    .finally(() => {
        // 无论成功还是失败，都重置标志
        isSavingRecipe = false;
    });
}