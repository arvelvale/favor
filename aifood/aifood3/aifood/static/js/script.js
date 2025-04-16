const ingredientInput = document.getElementById('ingredientInput');
const suggestions = document.getElementById('suggestions');
const selectedIngredients = document.getElementById('selectedIngredients');
const generateBtn = document.getElementById('generateBtn');
const recipeResult = document.getElementById('recipeResult');
const loading = document.getElementById('loading');
const saveRecipeBtn = document.getElementById('saveRecipeBtn');

let selectedItems = [];
// 存储完整的Markdown内容
let fullMarkdownContent = '';
// 存储当前生成的菜谱文本
let currentRecipe = '';

// 添加全局变量跟踪最近保存的菜谱
let lastSavedRecipe = {
    content: '',
    timestamp: 0
};

// Autocomplete functionality
ingredientInput.addEventListener('input', async () => {
    const query = ingredientInput.value.trim().toLowerCase();
    if (query.length === 0) {
        suggestions.innerHTML = '';
        return;
    }
    
    try {
        const response = await fetch(`/api/autocomplete?q=${query}`);
        const data = await response.json();
        
        suggestions.innerHTML = '';
        data.forEach(item => {
            const div = document.createElement('div');
            div.className = 'suggestion-item';
            div.textContent = item;
            div.addEventListener('click', () => {
                if (!selectedItems.includes(item)) {
                    selectedItems.push(item);
                    updateSelectedIngredients();
                }
                ingredientInput.value = '';
                suggestions.innerHTML = '';
            });
            suggestions.appendChild(div);
        });
    } catch (error) {
        console.error('Error fetching suggestions:', error);
    }
});

// Handle keydown events on input field
ingredientInput.addEventListener('keydown', (e) => {
    // If Enter key is pressed
    if (e.key === 'Enter') {
        e.preventDefault();
        
        const input = ingredientInput.value.trim().toLowerCase();
        if (!input) return;
        
        // Split input by comma to support multiple ingredients
        const ingredients = input.split(',').map(item => item.trim()).filter(item => item);
        
        // Add each ingredient if it's not already in the list
        let added = false;
        ingredients.forEach(ingredient => {
            if (ingredient && !selectedItems.includes(ingredient)) {
                selectedItems.push(ingredient);
                added = true;
            }
        });
        
        if (added) {
            updateSelectedIngredients();
        }
        
        // Clear input and suggestions
        ingredientInput.value = '';
        suggestions.innerHTML = '';
    }
});

// Update the selected ingredients display
function updateSelectedIngredients() {
    selectedIngredients.innerHTML = '';
    selectedItems.forEach(item => {
        const tag = document.createElement('div');
        tag.className = 'ingredient-tag';
        tag.innerHTML = `
            ${item}
            <span class="remove-ingredient" data-item="${item}">✕</span>
        `;
        selectedIngredients.appendChild(tag);
    });
    
    // Add event listeners to remove buttons
    document.querySelectorAll('.remove-ingredient').forEach(btn => {
        btn.addEventListener('click', () => {
            const item = btn.getAttribute('data-item');
            selectedItems = selectedItems.filter(i => i !== item);
            updateSelectedIngredients();
        });
    });
}

// Generate recipe
// 修改生成按钮的事件处理
generateBtn.addEventListener('click', async () => {
    // 新增：检查用户是否登录
    // 尝试查找 base.html 中登录后才会渲染的用户信息或头像元素
    const loggedInUserElement = document.querySelector('.user-info') || document.querySelector('.user-avatar'); 
    if (!loggedInUserElement) {
        // 如果找不到用户登录元素，则跳转到登录页
        window.location.href = '/login'; 
        return; // 阻止后续代码执行
    }

    if (selectedItems.length === 0) {
        // 创建自定义提示框而不是使用alert
        showIngredientAlert('Please select at least one ingredient');
        return;
    }
    
    // Always use English
    const language = 'en';
    const mode = document.querySelector('input[name="mode"]:checked').value;
    
    // 为不同的模式添加特定的指令
    let additionalInstructions = "";
    if (mode === "all") {
        additionalInstructions = "IMPORTANT: You must ONLY use the exact ingredients listed. Do not add any other ingredients that are not in the list, including common ingredients like salt, pepper, or spices unless they are explicitly listed. Water and heat for cooking are allowed.";
    } else {
        additionalInstructions = "You can suggest additional ingredients to enhance the recipe beyond what's listed.";
    }
    
    // 先检查是否已达到限制
    try {
        const usageResponse = await fetch('/api/get-usage-info');
        const usageData = await usageResponse.json();
        
        if (usageData.success) {
            const usage = usageData.usage;
            // 如果是免费用户且已达到限制，直接显示提示而不调用API
            if (!usage.is_premium && usage.remaining === 0) {
                showLimitReachedMessage('You have reached your daily limit of 3 recipe generations. Upgrade to premium for unlimited access!');
                return;
            }
        }
    } catch (error) {
        console.error('Error checking usage limits:', error);
        // 如果无法检查限制，继续尝试生成食谱
    }
    
    loading.style.display = 'block';
    recipeResult.innerHTML = '';
    
    // 重置Markdown内容
    fullMarkdownContent = '';
    currentRecipe = '';
    
    try {
        // 使用流式API
        const response = await fetch('/api/generate-recipe-stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                ingredients: selectedItems,
                language,
                mode,
                temperature: 0.7,
                max_tokens: 2000,
                instructions: additionalInstructions
            })
        });
        
        // 检查是否有错误响应
        if (!response.ok) {
            const errorData = await response.json();
            if (errorData.limit_reached) {
                // 显示限制达到提示
                showLimitReachedMessage(errorData.error || 'You have reached your daily limit of recipe generations.');
                loading.style.display = 'none';
                // 更新使用情况显示
                checkUsageInfo();
                return;
            }
            throw new Error(errorData.error || 'An error occurred while generating the recipe');
        }
        
        // 创建一个新的EventSource来处理流式响应
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        // 创建一个容器用于显示格式化的文本
        recipeResult.innerHTML = '<div class="recipe-content markdown-content"></div>';
        const contentDiv = recipeResult.querySelector('.recipe-content');
        
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            // 解码并添加到缓冲区
            buffer += decoder.decode(value, { stream: true });
            
            // 处理缓冲区中的所有完整事件
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || ''; // 保留最后一个不完整的行
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.substring(6);
                    
                    try {
                        const parsedData = JSON.parse(data);
                        
                        // 根据状态处理不同类型的消息
                        if (parsedData.status === 'start') {
                            // 初始消息，可以显示一个提示
                            contentDiv.innerHTML = '<p class="loading-text">Generating recipe...</p>';
                        } 
                        else if (parsedData.status === 'generating' && parsedData.content) {
                            // 移除初始加载文本
                            if (contentDiv.querySelector('.loading-text')) {
                                contentDiv.innerHTML = '';
                            }
                            
                            // 累积Markdown内容
                            fullMarkdownContent += parsedData.content;
                            currentRecipe += parsedData.content;
                            
                            // 使用marked.js解析Markdown并显示
                            contentDiv.innerHTML = marked.parse(fullMarkdownContent);
                            
                            // 自动滚动到底部
                            contentDiv.scrollTop = contentDiv.scrollHeight;
                        } 
                        else if (parsedData.status === 'error') {
                            contentDiv.innerHTML += `<p class="error">${parsedData.error || 'Error generating recipe, please try again'}</p>`;
                        }
                        else if (parsedData.status === 'done') {
                            // 完成生成，最终解析一次确保格式正确
                            contentDiv.innerHTML = marked.parse(fullMarkdownContent);
                            console.log('Recipe generation completed');
                            
                            // 自动保存到历史记录
                            autoSaveRecipe(fullMarkdownContent, selectedItems);
                            
                            // 在recipe-content中添加图片生成按钮（放在文本内容后但在语音朗读按钮之前）
                            addImageButtonToContent(contentDiv, language);
                            
                            // 显示语音朗读按钮（在文本下方居中）
                            const recipeActions = document.getElementById('recipeActions');
                            if (recipeActions) {
                                recipeActions.style.display = 'flex';
                            }
                            
                            // 更新使用情况显示
                            checkUsageInfo();
                        }
                    } catch (e) {
                        console.error('Error parsing JSON:', e, data);
                    }
                }
            }
        }
    } catch (error) {
        console.error('Error generating recipe:', error);
        
        // 检查是否是使用限制错误
        if (error.message && error.message.includes('limit')) {
            // 显示限制达到提示
            showLimitReachedMessage('You have reached your daily limit of 3 recipe generations. Upgrade to premium for unlimited access!');
        } else {
            recipeResult.innerHTML = `<p class="error">Error generating recipe: ${error.message}. Please try again.</p>`;
        }
    } finally {
        loading.style.display = 'none';
        
        // 更新使用情况显示
        checkUsageInfo();
    }
});

// 显示食材选择提示框函数
function showIngredientAlert(message) {
    // 检查是否已存在提示框
    const existingAlert = document.querySelector('.ingredient-alert');
    if (existingAlert) {
        existingAlert.remove();
    }
    
    // 创建提示框元素
    const alertBox = document.createElement('div');
    alertBox.className = 'ingredient-alert';
    alertBox.innerHTML = `
        <div class="ingredient-alert-content">
            <p>${message}</p>
            <button class="alert-confirm-btn">确定</button>
        </div>
    `;
    
    // 添加到body
    document.body.appendChild(alertBox);
    
    // 点击确定按钮关闭提示框
    const confirmBtn = alertBox.querySelector('.alert-confirm-btn');
    confirmBtn.addEventListener('click', () => {
        alertBox.remove();
    });
    
    // 点击外部区域关闭提示框
    alertBox.addEventListener('click', (e) => {
        if (e.target === alertBox) {
            alertBox.remove();
        }
    });
}

// 显示已达到限制的消息
function showLimitReachedMessage(message) {
    const resultContainer = document.getElementById('recipeResult');
    if (resultContainer) {
        resultContainer.innerHTML = `
            <div class="limit-reached-message">
                <p>${message}</p>
                <p>Free users are limited to 3 recipe generations per day.</p>
                <a href="/premium" class="premium-link">
                    <i class="fas fa-crown"></i> Upgrade to Premium
                </a>
            </div>
        `;
    }
    
    // 同时更新使用信息显示
    checkUsageInfo();
}

// 设置图片生成按钮事件
function setupImageGenerationButton(container, language) {
    // 获取container中的按钮和图片容器
    const generateImagesBtn = container.querySelector('.generate-images-btn');
    if (!generateImagesBtn) return;
    
    // 获取图片容器
    let imagesContainer = container.querySelector('.recipe-images-container');
    if (!imagesContainer) {
        // 创建图片容器
        imagesContainer = document.createElement('div');
        imagesContainer.className = 'recipe-images-container';
        imagesContainer.style.display = 'none';
        container.appendChild(imagesContainer);
    }
    
    // 防止重复点击
    if (generateImagesBtn.disabled) return;
    
    generateImagesBtn.disabled = true;
    const originalText = generateImagesBtn.innerHTML;
    generateImagesBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Generating images...`;
    
    imagesContainer.innerHTML = '';
    imagesContainer.style.display = 'block';
    
    try {
        // 获取食谱内容
        const recipeText = container.textContent;
        
        // 发送请求生成图片
        fetch('/api/generate-images', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                recipe: recipeText,
                language: language || 'en'
            })
        })
        .then(response => response.json())
        .then(data => {
            generateImagesBtn.disabled = false;
            generateImagesBtn.innerHTML = originalText;
            
            if (data.images && data.images.length > 0) {
                // 改为处理文本和图片的完整内容
                displayGeneratedContent(data, imagesContainer, recipeText);
            } else {
                imagesContainer.innerHTML = `<p class="error">${data.error || 'Error generating images'}</p>`;
            }
        })
        .catch(error => {
            console.error('Error generating images:', error);
            generateImagesBtn.disabled = false;
            generateImagesBtn.innerHTML = originalText;
            imagesContainer.innerHTML = `<p class="error">${data.error || 'Error generating images'}</p>`;
        });
    } catch (error) {
        console.error('Error in image generation:', error);
        generateImagesBtn.disabled = false;
        generateImagesBtn.innerHTML = originalText;
    }
}

// 处理图片和文本，把图片插入到文本的适当位置
function processImagesWithText(text, images, container, language) {
    if (!text || !images.length) {
        return;
    }
    
    // 创建标题
    const title = document.createElement('h3');
    title.textContent = 'Recipe Steps with Images';
    container.appendChild(title);
    
    // 创建内容区域
    const contentDiv = document.createElement('div');
    contentDiv.className = 'recipe-illustrated-content';
    
    // 查找包含"Image X:"的段落模式 - 增强正则表达式匹配能力
    const imageRegexPattern = /Image\s*(\d+)[：:.]\s*(.*)/i;
    
    // 将文本分成段落，确保正确处理各种换行符
    const paragraphs = text.split(/\n+/).filter(p => p.trim());
    
    // 提取图片标签与描述
    const imageLabels = [];
    let currentParagraph = '';
    
    paragraphs.forEach(paragraph => {
        const match = paragraph.match(imageRegexPattern);
        if (match) {
            const imageNumber = parseInt(match[1]);
            const description = match[2].trim();
            imageLabels.push({
                number: imageNumber,
                description: description,
                paragraph: paragraph
            });
        }
    });
    
    console.log('Found image labels:', imageLabels);
    console.log('Available images:', images.length);
    
    // 根据图片标签顺序处理段落和图片
    if (imageLabels.length > 0) {
        // 按照图片编号排序
        imageLabels.sort((a, b) => a.number - b.number);
        
        // 为每个图片创建内容
        imageLabels.forEach((label, index) => {
            if (index < images.length) {
                const stepDiv = document.createElement('div');
                stepDiv.className = 'recipe-step-with-image';
                
                // 添加描述文本
                const textDiv = document.createElement('div');
                textDiv.className = 'step-description';
                textDiv.innerHTML = marked.parse(label.paragraph);
                stepDiv.appendChild(textDiv);
                
                // 添加图片
                const img = document.createElement('img');
                img.src = `data:${images[index].mime_type};base64,${images[index].data}`;
                img.alt = label.description;
                img.className = 'recipe-step-image';
                
                // 点击图片放大查看
                img.addEventListener('click', () => {
                    openImageModal(img.src);
                });
                
                stepDiv.appendChild(img);
                contentDiv.appendChild(stepDiv);
            }
        });
    } else {
        // 如果没有找到图片标签，尝试简单地将图片和文本按顺序组合
        const warningDiv = document.createElement('div');
        warningDiv.className = 'warning-message';
        warningDiv.textContent = 'Could not match images to specific steps. Showing images in sequence.';
        contentDiv.appendChild(warningDiv);
        
        // 每段文本显示最多一张图片，最多处理与图片数量相同的段落
        for (let i = 0; i < Math.min(paragraphs.length, images.length); i++) {
            const stepDiv = document.createElement('div');
            stepDiv.className = 'recipe-step-with-image';
            
            // 添加文本
            const textDiv = document.createElement('div');
            textDiv.className = 'step-description';
            textDiv.innerHTML = marked.parse(paragraphs[i]);
            stepDiv.appendChild(textDiv);
            
            // 添加图片
            const img = document.createElement('img');
            img.src = `data:${images[i].mime_type};base64,${images[i].data}`;
            img.alt = `Recipe step ${i + 1}`;
            img.className = 'recipe-step-image';
            
            // 点击图片放大查看
            img.addEventListener('click', () => {
                openImageModal(img.src);
            });
            
            stepDiv.appendChild(img);
            contentDiv.appendChild(stepDiv);
        }
    }
    
    // 如果还有剩余的图片，将它们添加到底部
    const unmatchedImages = Math.max(0, images.length - (imageLabels.length || paragraphs.length));
    if (unmatchedImages > 0) {
        const remainingImagesDiv = document.createElement('div');
        remainingImagesDiv.className = 'remaining-images';
        
        const subtitle = document.createElement('h4');
        subtitle.textContent = 'Additional Step Images';
        remainingImagesDiv.appendChild(subtitle);
        
        const imageGrid = document.createElement('div');
        imageGrid.className = 'image-grid';
        
        const startIndex = images.length - unmatchedImages;
        for (let i = startIndex; i < images.length; i++) {
            const imageBox = document.createElement('div');
            imageBox.className = 'image-box';
            
            const img = document.createElement('img');
            img.src = `data:${images[i].mime_type};base64,${images[i].data}`;
            img.alt = `Recipe step ${i + 1}`;
            
            // 点击图片放大查看
            img.addEventListener('click', () => {
                openImageModal(img.src);
            });
            
            imageBox.appendChild(img);
            imageGrid.appendChild(imageBox);
        }
        
        remainingImagesDiv.appendChild(imageGrid);
        contentDiv.appendChild(remainingImagesDiv);
    }
    
    container.appendChild(contentDiv);
}

// 打开图片模态框
function openImageModal(imageUrl) {
    const modal = document.createElement('div');
    modal.className = 'image-modal';
    
    const img = document.createElement('img');
    img.src = imageUrl;
    
    const closeBtn = document.createElement('div');
    closeBtn.className = 'modal-close';
    closeBtn.innerHTML = '&times;';
    
    // 关闭模态框
    closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        document.body.removeChild(modal);
    });
    
    modal.addEventListener('click', () => {
        document.body.removeChild(modal);
    });
    
    img.addEventListener('click', (e) => {
        e.stopPropagation();
    });
    
    modal.appendChild(img);
    modal.appendChild(closeBtn);
    document.body.appendChild(modal);
}

// Close suggestions when clicking outside
document.addEventListener('click', (e) => {
    if (e.target !== ingredientInput && e.target !== suggestions) {
        suggestions.innerHTML = '';
    }
});

// Allow pressing Enter to add the first suggestion
ingredientInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && suggestions.firstChild) {
        suggestions.firstChild.click();
    }
});

// 添加保存菜谱的事件监听
if (saveRecipeBtn) {
    saveRecipeBtn.addEventListener('click', async () => {
        if (!currentRecipe) {
            alert('Please generate a recipe first');
            return;
        }
        
        try {
            // 从菜谱内容中提取标题
            let recipeTitle = '美味菜谱';
            const titleMatch = currentRecipe.match(/^# (.+?)$/m) || currentRecipe.match(/^(.+?)[\n\r]/);
            if (titleMatch && titleMatch[1]) {
                recipeTitle = titleMatch[1].trim();
            }
            
            const language = document.querySelector('input[name="language"]:checked').value;
            
            const response = await fetch('/api/save-recipe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    recipe_name: recipeTitle,
                    recipe_content: currentRecipe,
                    ingredients: selectedItems.join(', '),
                    language: language
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                saveRecipeBtn.textContent = '✓ 已保存';
                saveRecipeBtn.disabled = true;
                
                setTimeout(() => {
                    saveRecipeBtn.innerHTML = '<i class="fas fa-save"></i> 保存此菜谱';
                    saveRecipeBtn.disabled = false;
                }, 3000);
            } else {
                alert(data.message || '保存失败，请重试');
            }
        } catch (error) {
            console.error('保存菜谱时出错:', error);
            alert('保存失败，请检查网络连接后重试');
        }
    });
}

// 显示已保存的菜谱列表
// 修改 fetchSavedRecipes 函数，添加更多调试信息
function fetchSavedRecipes() {
    const recipesContainer = document.getElementById('saved-recipes');
    if (!recipesContainer) {
        console.error('找不到 saved-recipes 容器元素');
        return;
    }
    
    console.log('开始获取用户菜谱...');
    
    // 显示加载状态
    recipesContainer.innerHTML = `
        <div class="loading-recipes">
            <i class="fas fa-spinner fa-spin"></i> Loading recipes...
        </div>
    `;
    
    // 发起请求
    fetch('/api/my-recipes')
        .then(response => {
            console.log('API 响应状态:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('API 响应数据:', data);
            if (data.success) {
                if (data.recipes && data.recipes.length > 0) {
                    console.log(`找到 ${data.recipes.length} 个菜谱`);
                    displaySavedRecipes(data.recipes);
                } else {
                    console.log('没有找到菜谱');
                    recipesContainer.innerHTML = '<div class="empty-recipes">No saved recipes</div>';
                }
            } else {
                throw new Error(data.message || 'Failed to get recipe list');
            }
        })
        .catch(error => {
            console.error('获取菜谱时出错:', error);
            recipesContainer.innerHTML = '<div class="empty-recipes">Error loading recipes. Please try again.</div>';
        });
}

// 显示已保存的菜谱
function displaySavedRecipes(recipes) {
    const recipesContainer = document.getElementById('saved-recipes');
    if (!recipesContainer) return;
    
    console.log('Displaying recipes:', recipes);
    
    if (!recipes || recipes.length === 0) {
        recipesContainer.innerHTML = '<div class="empty-recipes">No saved recipes</div>';
        return;
    }
    
    let html = '';
    recipes.forEach(recipe => {
        console.log('Processing recipe:', recipe);
        const recipeDate = new Date(recipe.created_at).toLocaleDateString();
        
        html += `
            <div class="recipe-card" data-id="${recipe.id}">
                <h3>${recipe.recipe_name || 'Untitled Recipe'}</h3>
                <div class="recipe-card-info">
                    <span><i class="fas fa-calendar"></i> ${recipeDate}</span>
                    <span><i class="fas fa-utensils"></i> Ingredients: ${recipe.ingredients || 'No ingredients listed'}</span>
                </div>
                <div class="recipe-actions">
                    <button class="view-btn" onclick="viewRecipe(${recipe.id})"><i class="fas fa-eye"></i> View</button>
                    <button class="delete-btn" onclick="deleteRecipe(${recipe.id})"><i class="fas fa-trash"></i> Delete</button>
                </div>
            </div>
        `;
    });
    
    recipesContainer.innerHTML = html;
}

// 查看菜谱详情
function viewRecipe(recipeId) {
    window.location.href = `/my-recipes/${recipeId}`;
}

// 删除菜谱
function deleteRecipe(recipeId) {
    if (!confirm('确定要删除这个菜谱吗？此操作不可撤销。')) {
        return;
    }
    
    fetch(`/api/delete-recipe/${recipeId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const recipeCard = document.querySelector(`.recipe-card[data-id="${recipeId}"]`);
            if (recipeCard) {
                recipeCard.remove();
            }
            
            // 如果没有菜谱了，显示空状态
            const recipesContainer = document.getElementById('saved-recipes');
            if (recipesContainer && recipesContainer.children.length === 0) {
                recipesContainer.innerHTML = '<div class="empty-recipes">暂无保存的菜谱</div>';
            }
        } else {
            alert(data.message || '删除失败，请重试');
        }
    })
    .catch(error => {
        console.error('删除菜谱时出错:', error);
        alert('删除失败，请检查网络连接后重试');
    });
}

// 初始化页面
document.addEventListener('DOMContentLoaded', function() {
    // 检查当前页面是否为菜谱历史页面
    if (window.location.pathname === '/my-recipes') {
        fetchSavedRecipes();
    }
    
    // 检查是否在主页
    if (window.location.pathname === '/' || window.location.pathname === '/index') {
        // Check premium status when page loads
        checkPremiumStatus().then(() => {
            // 检查使用情况并显示
            checkUsageInfo();
        });
    }
    
    // 使用toast显示欢迎消息
    if (window.toastMessage) {
        // 使用sessionStorage检查是否已显示过欢迎信息
        const hasShownWelcome = sessionStorage.getItem('hasShownWelcome');
        
        if (!hasShownWelcome) {
            setTimeout(() => {
                toastMessage.info('Welcome to Flavor Fusion!');
                // 标记为已显示
                sessionStorage.setItem('hasShownWelcome', 'true');
            }, 1000);
        }
    }
    
    // 初始化功能
    initIngredientInput();
    initModeSelector();
});

// 修改原来的处理菜谱生成内容的函数
function displayRecipe(recipeText, requestedIngredients, language) {
    // Always use English
    language = 'en';
    
    // 保存当前生成的菜谱文本
    currentRecipe = recipeText;
    
    // 解析Markdown并显示
    recipeResult.innerHTML = '<div class="recipe-content markdown-content"></div>';
    const contentDiv = recipeResult.querySelector('.recipe-content');
    contentDiv.innerHTML = marked.parse(recipeText);
    
    // 自动保存菜谱到历史记录
    autoSaveRecipe(recipeText, requestedIngredients);
    
    // 如果用户已登录，显示保存按钮
    if (saveRecipeBtn) {
        saveRecipeBtn.style.display = 'none'; // 隐藏保存按钮，因为已经自动保存
    }
}

// 自动保存菜谱到历史记录
async function autoSaveRecipe(recipeText, ingredients) {
    // 检查是否登录
    const saveButton = document.getElementById('saveRecipeBtn'); // Check if save button exists as proxy for login status
    if (!saveButton) {
        // logger.info('User not logged in, skipping auto-save.');
        return; // 未登录，不保存
    }

    // Add check for empty recipe text
    if (!recipeText || recipeText.trim() === '') {
        console.warn('autoSaveRecipe called with empty recipeText. Skipping save.');
        return; // Don't save if content is empty
    }
    
    // 检查是否是相同的菜谱内容，并且距离上次保存不超过5秒
    const currentTime = Date.now();
    if (recipeText === lastSavedRecipe.content && 
        (currentTime - lastSavedRecipe.timestamp) < 5000) {
        console.log('相同菜谱已在最近保存过，跳过重复保存');
        return;
    }
    
    try {
        // 从菜谱文本中提取标题
        let recipeTitle = '未命名菜谱';
        // 修改正则表达式以匹配任何级别的Markdown标题（#、##或###）
        const titleMatch = recipeText.match(/#+ (.+?)(\n|$)/);
        if (titleMatch && titleMatch[1]) {
            recipeTitle = titleMatch[1].trim();
        }
        
        // 添加调试日志，查看实际的食谱文本开头和匹配结果
        console.log('食谱标题匹配结果:', titleMatch);
        console.log('提取的标题:', recipeTitle);
        console.log('食谱文本前100个字符:', recipeText.substring(0, 100));
        
        const response = await fetch('/api/save-recipe', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                recipe_name: recipeTitle,
                recipe_content: recipeText,
                ingredients: ingredients.join(', '),
                language: 'en'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            console.log('菜谱已自动保存到历史记录');
            // 更新最近保存的菜谱记录
            lastSavedRecipe = {
                content: recipeText,
                timestamp: currentTime
            };
        } else {
            // Avoid showing error for duplicate saves, which are now handled
            if (data.message !== "Recipe already saved") { 
                console.error('自动保存菜谱失败:', data.message);
            }
        }
    } catch (error) {
        console.error('自动保存菜谱时出错:', error);
    }
}

// When loading saved recipes, always use English
async function loadSavedRecipes() {
    const savedRecipesContainer = document.getElementById('saved-recipes');
    if (!savedRecipesContainer) return;
    
    savedRecipesContainer.innerHTML = `
        <div class="loading-recipes">
            <i class="fas fa-spinner fa-spin"></i> Loading recipes...
        </div>
    `;
    
    try {
        const response = await fetch('/api/saved-recipes');
        const data = await response.json();
        
        if (data.success && data.recipes.length > 0) {
            savedRecipesContainer.innerHTML = '';
            
            // Always use English for any text
            const language = 'en';
            
            data.recipes.forEach(recipe => {
                const recipeCard = createRecipeCard(recipe, language);
                savedRecipesContainer.appendChild(recipeCard);
            });
        } else {
            savedRecipesContainer.innerHTML = `
                <div class="empty-recipes">
                    <i class="fas fa-book-open"></i>
                    <p>You haven't saved any recipes yet.</p>
                    <a href="/" class="create-recipe-btn">Create Your First Recipe</a>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading saved recipes:', error);
        savedRecipesContainer.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-circle"></i>
                <p>Failed to load your recipes. Please try again later.</p>
            </div>
        `;
    }
}

// 在食谱生成完成后显示操作按钮
function showRecipeActions() {
    const recipeActions = document.getElementById('recipeActions');
    if (recipeActions) {
        recipeActions.style.display = 'flex';
    }
}

// 在处理食谱生成响应的函数中添加调用
function handleRecipeResponse(data) {
    // 显示食谱结果
    recipeResult.innerHTML = marked.parse(data.recipe);
    
    // 显示操作按钮
    showRecipeActions();
    
    // 自动保存到历史记录 - 这可能会导致重复保存，因为其他地方可能已经调用了autoSaveRecipe
    // 检查是否最近已保存过相同内容
    if (data.recipe !== lastSavedRecipe.content) {
        autoSaveRecipe(data.recipe, selectedItems);
    }
    
    // 添加生成图片按钮
    addGenerateImagesButton(contentDiv, language);
}

// 在recipe-content中添加图片生成按钮
function addImageButtonToContent(contentDiv, language) {
    // 创建一个包装容器，放在内容的末尾
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'image-button-container';
    buttonContainer.style.textAlign = 'center';
    buttonContainer.style.marginTop = '-20px';
    buttonContainer.style.position = 'relative';
    buttonContainer.style.zIndex = '10';
    
    // 创建按钮
    const generateImagesBtn = document.createElement('button');
    generateImagesBtn.id = 'generate-images-btn';
    generateImagesBtn.className = 'action-btn generate-images-btn';
    generateImagesBtn.innerHTML = '<i class="fas fa-images"></i> Generate Recipe Images';
    
    // 添加事件监听
    generateImagesBtn.addEventListener('click', () => {
        setupImageGenerationButton(contentDiv, language);
    });
    
    // 创建图片容器
    const imagesContainer = document.createElement('div');
    imagesContainer.className = 'recipe-images-container';
    imagesContainer.style.display = 'none';
    
    // 添加到DOM
    buttonContainer.appendChild(generateImagesBtn);
    contentDiv.appendChild(buttonContainer);
    contentDiv.appendChild(imagesContainer);
    
    // 确保按钮可见 - 滚动到按钮位置
    setTimeout(() => {
        generateImagesBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 100);
}

// 显示生成的图片和文本内容
function displayGeneratedContent(data, container, recipeText) {
    if (!data || (!data.images || data.images.length === 0) && !data.text) {
        container.innerHTML = '<p class="error">No content was generated</p>';
        return;
    }
    
    // 清空容器
    container.innerHTML = '';
    
    // 使用 processImagesWithText 函数处理文本和图片
    if (data.text && data.images && data.images.length > 0) {
        processImagesWithText(data.text, data.images, container, 'en');
    } else {
        // 如果只有文本内容，显示文本
        if (data.text) {
            const textContent = document.createElement('div');
            textContent.className = 'recipe-gemini-text';
            textContent.innerHTML = marked.parse(data.text);
            container.appendChild(textContent);
        }
        
        // 如果只有图片，使用原来的方式显示
        if (data.images && data.images.length > 0) {
            const titleElement = document.createElement('h3');
            titleElement.textContent = 'Recipe Visualized';
            container.appendChild(titleElement);
            
            // 创建图片网格
            const imageGrid = document.createElement('div');
            imageGrid.className = 'image-grid';
            
            // 添加图片到网格
            data.images.forEach((image, index) => {
                const imageBox = document.createElement('div');
                imageBox.className = 'image-box';
                
                const img = document.createElement('img');
                // 处理base64格式的图片数据
                if (image.data && image.mime_type) {
                    img.src = `data:${image.mime_type};base64,${image.data}`;
                } else if (typeof image === 'string') {
                    // 处理URL格式的图片
                    img.src = image;
                }
                img.alt = `Recipe image ${index + 1}`;
                img.loading = 'lazy';
                
                // 图片点击放大
                img.addEventListener('click', () => {
                    openImageModal(img.src);
                });
                
                imageBox.appendChild(img);
                imageGrid.appendChild(imageBox);
            });
            
            container.appendChild(imageGrid);
        }
    }
    
    // 显示图片和文本内容
    container.style.display = 'block';
    
    // 滚动到内容区域
    container.scrollIntoView({ behavior: 'smooth' });
}

// Check if user has premium subscription
function checkPremiumStatus() {
    return fetch('/api/check-subscription-status')
        .then(response => response.json())
        .then(data => {
            // Store the premium status in local storage for quick access
            localStorage.setItem('isPremium', data.is_premium);
            
            // 如果用户是会员，显示会员徽章和特殊样式
            if (data.is_premium) {
                // 显示会员徽章
                const premiumBadge = document.getElementById('premiumBadge');
                if (premiumBadge) {
                    premiumBadge.style.display = 'inline-flex';
                }
                
                // 为用户信息容器添加特殊样式
                const userInfo = document.querySelector('.user-info');
                if (userInfo) {
                    userInfo.classList.add('premium-user');
                }
                
                // 为用户头像添加高级边框
                const avatarContainer = document.querySelector('.avatar-container');
                if (avatarContainer) {
                    avatarContainer.classList.add('premium-avatar');
                }
            }
            
            return data.is_premium;
        })
        .catch(error => {
            console.error('Error checking premium status:', error);
            return false;
        });
}

// 检查并显示使用情况信息
function checkUsageInfo() {
    // 确保 usageInfo 元素存在
    const usageInfo = document.getElementById('usageInfo');
    if (!usageInfo) return;
    
    fetch('/api/get-usage-info')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const usageMessage = document.getElementById('usageMessage');
                const upgradeBtn = document.getElementById('upgradeToPremium');
                
                usageInfo.style.display = 'block';
                
                const usage = data.usage;
                if (usage.is_premium) {
                    usageInfo.classList.remove('usage-limit-reached');
                    usageInfo.classList.add('premium-user-info');
                    usageMessage.innerHTML = `<strong><i class="fas fa-crown"></i> Premium Member:</strong> Enjoy unlimited recipe generations and exclusive features!`;
                    if (upgradeBtn) {
                        upgradeBtn.style.display = 'none';
                    }
                } else {
                    usageInfo.classList.remove('premium-user-info');
                    usageMessage.innerHTML = `<strong>Free User:</strong> You have used ${usage.used}/${usage.limit} recipe generations today.`;
                    if (upgradeBtn) {
                        upgradeBtn.style.display = 'inline-block';
                    }
                    
                    // 如果已经达到限制，使用红色强调显示
                    if (usage.remaining === 0) {
                        usageInfo.classList.add('usage-limit-reached');
                        usageMessage.innerHTML = `<strong>Limit Reached:</strong> You've used all your free generations today.`;
                        
                        // 如果用户已达到限制，显示提示消息
                        if (generateBtn) {
                            generateBtn.disabled = true;
                            generateBtn.title = 'Daily limit reached. Upgrade to premium for unlimited generations.';
                            
                            // 在生成按钮后显示提示
                            const buttonContainer = generateBtn.parentElement;
                            if (buttonContainer && !document.querySelector('.limit-notification')) {
                                const notification = document.createElement('div');
                                notification.className = 'limit-notification';
                                notification.innerHTML = `
                                    <i class="fas fa-exclamation-circle"></i> 
                                    Daily limit reached. <a href="/premium">Upgrade to Premium</a> for unlimited access.
                                `;
                                buttonContainer.appendChild(notification);
                            }
                        }
                    } else {
                        usageInfo.classList.remove('usage-limit-reached');
                        
                        // 移除限制提示
                        if (generateBtn) {
                            generateBtn.disabled = false;
                            generateBtn.title = '';
                            
                            const notification = document.querySelector('.limit-notification');
                            if (notification) {
                                notification.remove();
                            }
                        }
                    }
                }
            }
        })
        .catch(error => console.error('Error checking usage:', error));
}

// 更新生成按钮的错误处理
const originalClickHandler = generateBtn.onclick;
generateBtn.addEventListener('click', async (event) => {
    // 先检查是否已达到限制
    try {
        const response = await fetch('/api/get-usage-info');
        const data = await response.json();
        
        if (data.success) {
            const usage = data.usage;
            // 如果是免费用户且已达到限制，直接显示提示而不调用API
            if (!usage.is_premium && usage.remaining === 0) {
                loading.style.display = 'none';
                showLimitReachedMessage('You have reached your daily limit of 3 recipe generations. Upgrade to premium for unlimited access!');
                event.stopPropagation(); // 阻止原始事件处理器执行
                return false;
            }
        }
    } catch (error) {
        console.error('Error checking usage limits:', error);
    }
});

// 页面加载时检查使用情况
document.addEventListener('DOMContentLoaded', function() {
    // 检查当前页面是否为主页
    if (window.location.pathname === '/' || window.location.pathname === '/index.html') {
        // 检查会员状态和使用情况
        checkPremiumStatus().then(() => {
            checkUsageInfo();
        });
    }
});

function showUserInfo(userData) {
    const userInfoElement = document.getElementById("user-info");
    const userNavElement = document.getElementById("user-nav");
    
    if (userInfoElement && userData) {
        // 更新用户名
        const usernameElement = userInfoElement.querySelector(".username");
        if (usernameElement) {
            usernameElement.textContent = userData.username || "User";
        }
        
        // 更新头像URL - 使用新的API路由
        const avatarImg = userInfoElement.querySelector(".user-avatar");
        if (avatarImg) {
            // 检查用户是否有自定义头像
            if (userData.profile_image) {
                // 使用新的API路由并添加时间戳防止缓存
                avatarImg.src = `/api/avatar/${userData.id}?v=${new Date().getTime()}`;
            } else {
                avatarImg.src = "/static/images/default-avatar.png";
            }
        }
        
        // 显示用户信息区域
        userInfoElement.style.display = "flex";
        
        // 如果有用户导航区域，显示它
        if (userNavElement) {
            userNavElement.style.display = "flex";
        }
        
        // 检查用户是否为高级会员并添加会员徽章
        checkPremiumStatus();
    }
}