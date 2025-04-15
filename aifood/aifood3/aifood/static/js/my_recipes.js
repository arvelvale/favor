// my_recipes.js - 菜谱历史页面专用脚本

document.addEventListener('DOMContentLoaded', function() {
    console.log('my_recipes.js: DOMContentLoaded 事件触发');
    fetchRecipes();
});

// 获取用户菜谱记录
function fetchRecipes() {
    console.log('my_recipes.js: 开始获取用户菜谱记录');
    const recipesContainer = document.getElementById('saved-recipes');
    
    if (!recipesContainer) {
        console.error('my_recipes.js: 找不到 saved-recipes 容器元素');
        return;
    }
    
    // 显示加载状态
    recipesContainer.innerHTML = `
        <div class="loading-recipes">
            <i class="fas fa-spinner fa-spin"></i> Loading recipes...
        </div>
    `;
    
    // 发起API请求
    fetch('/api/my-recipes')
        .then(response => {
            console.log('my_recipes.js: API响应状态:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('my_recipes.js: API响应数据:', data);
            
            if (data.success) {
                if (data.recipes && data.recipes.length > 0) {
                    console.log(`my_recipes.js: 找到 ${data.recipes.length} 个菜谱`);
                    displayRecipes(data.recipes);
                } else {
                    console.log('my_recipes.js: 没有找到菜谱');
                    recipesContainer.innerHTML = `
                        <div class="empty-recipes">
                            <p>You haven't saved any recipes yet.</p>
                            <a href="/" class="action-btn">Create Your First Recipe</a>
                        </div>
                    `;
                }
            } else {
                throw new Error(data.message || 'Failed to get recipe list');
            }
        })
        .catch(error => {
            console.error('my_recipes.js: 获取菜谱记录出错:', error);
            recipesContainer.innerHTML = `
                <div class="error-message">
                    <p>Error loading recipes: ${error.message}</p>
                    <button class="action-btn" onclick="fetchRecipes()">Try Again</button>
                </div>
            `;
        });
}

// 显示菜谱列表
function displayRecipes(recipes) {
    console.log('my_recipes.js: 显示菜谱列表', recipes);
    const recipesContainer = document.getElementById('saved-recipes');
    
    let html = '';
    recipes.forEach(recipe => {
        const recipeDate = new Date(recipe.created_at).toLocaleDateString();
        const ingredients = recipe.ingredients ? recipe.ingredients : 'No ingredients listed';
        
        html += `
            <div class="recipe-card" data-id="${recipe.id}">
                <h3>${recipe.recipe_name || 'Untitled Recipe'}</h3>
                <div class="recipe-card-info">
                    <span><i class="fas fa-calendar"></i> ${recipeDate}</span>
                    <span><i class="fas fa-utensils"></i> Ingredients: ${ingredients}</span>
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
    if (!confirm('Are you sure you want to delete this recipe? This action cannot be undone.')) {
        return;
    }
    
    console.log('my_recipes.js: 删除菜谱 ID:', recipeId);
    
    fetch(`/api/delete-recipe/${recipeId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // 从DOM中移除菜谱卡片
            const recipeCard = document.querySelector(`.recipe-card[data-id="${recipeId}"]`);
            if (recipeCard) {
                recipeCard.remove();
            }
            
            // 检查是否还有剩余菜谱
            const recipesContainer = document.getElementById('saved-recipes');
            if (recipesContainer && recipesContainer.querySelectorAll('.recipe-card').length === 0) {
                recipesContainer.innerHTML = `
                    <div class="empty-recipes">
                        <p>You haven't saved any recipes yet.</p>
                        <a href="/" class="action-btn">Create Your First Recipe</a>
                    </div>
                `;
            }
        } else {
            alert(data.message || 'Failed to delete recipe. Please try again.');
        }
    })
    .catch(error => {
        console.error('my_recipes.js: 删除菜谱出错:', error);
        alert('Failed to delete recipe. Please check your connection and try again.');
    });
} 