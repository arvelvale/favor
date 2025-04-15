/**
 * My Recipe Collection 页面的交互脚本
 * 实现食谱搜索、筛选、批量操作和分页功能
 */

document.addEventListener('DOMContentLoaded', function() {
    // 全局变量
    let allRecipes = []; // 存储所有食谱数据
    let filteredRecipes = []; // 存储经过筛选后的食谱
    let currentPage = 1;  // 当前页码
    const recipesPerPage = 9; // 每页显示的食谱数量
    let isSelectionMode = false; // 是否处于选择模式
    let selectedRecipes = new Set(); // 存储选中的食谱ID
    
    // DOM元素
    const recipesContainer = document.getElementById('saved-recipes');
    const searchInput = document.getElementById('recipe-search');
    const filterBtn = document.getElementById('filter-btn');
    const filterOptions = document.getElementById('filter-options');
    const selectBtn = document.getElementById('select-btn');
    const bulkActions = document.getElementById('bulk-actions');
    const selectedCountText = document.getElementById('selected-count');
    const bulkDeleteBtn = document.getElementById('bulk-delete-btn');
    const bulkCancelBtn = document.getElementById('bulk-cancel-btn');
    const paginationContainer = document.getElementById('pagination');
    
    // 1. 初始化加载食谱数据
    fetchSavedRecipes();
    
    // 2. 事件监听器
    // 搜索框输入事件
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function() {
            filterRecipes();
        }, 300));
    }
    
    // 筛选按钮点击事件
    if (filterBtn) {
        filterBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            filterOptions.classList.toggle('show');
        });
    }
    
    // 选择筛选选项事件
    if (filterOptions) {
        filterOptions.addEventListener('click', function(e) {
            if (e.target.type === 'radio' || e.target.tagName === 'LABEL') {
                setTimeout(() => {
                    filterOptions.classList.remove('show');
                    filterRecipes();
                }, 100);
            }
        });
    }
    
    // 点击页面其他地方关闭筛选选项
    document.addEventListener('click', function() {
        filterOptions.classList.remove('show');
    });
    
    // 选择模式按钮事件
    if (selectBtn) {
        selectBtn.addEventListener('click', function() {
            toggleSelectionMode();
        });
    }
    
    // 批量删除按钮事件
    if (bulkDeleteBtn) {
        bulkDeleteBtn.addEventListener('click', function() {
            if (selectedRecipes.size > 0) {
                confirmBulkDelete();
            }
        });
    }
    
    // 取消选择按钮事件
    if (bulkCancelBtn) {
        bulkCancelBtn.addEventListener('click', function() {
            toggleSelectionMode(false);
        });
    }
    
    // 3. 函数定义
    
    // 获取保存的食谱
    function fetchSavedRecipes() {
        // 显示加载中提示
        recipesContainer.innerHTML = `
            <div class="loading-recipes">
                <i class="fas fa-spinner fa-spin"></i> Loading recipes...
            </div>
        `;
        
        // 如果加载时间超过3秒，显示超时提示
        setTimeout(() => {
            const loadingElement = document.querySelector('.loading-recipes');
            if (loadingElement) {
                loadingElement.innerHTML += `
                    <div class="loading-timeout-message">
                        Taking longer than expected. If no recipes appear, you may not have saved any recipes yet.
                    </div>
                `;
            }
        }, 3000);
        
        // 发送API请求获取食谱
        fetch('/api/my-recipes')
            .then(response => response.json())
            .then(data => {
                console.log('API响应:', data);
                
                if (data.success && data.recipes && data.recipes.length > 0) {
                    allRecipes = data.recipes;
                    filteredRecipes = [...allRecipes]; // 初始显示所有食谱
                    renderRecipes(); // 渲染食谱列表
                } else {
                    // 显示空状态
                    showEmptyState();
                }
            })
            .catch(error => {
                console.error('获取食谱失败:', error);
                recipesContainer.innerHTML = `
                    <div class="empty-recipes">
                        <i class="fas fa-exclamation-circle"></i>
                        <h3>Error Loading Recipes</h3>
                        <p>Something went wrong while loading your recipes. Please try again later.</p>
                        <button class="create-recipe-btn" onclick="location.reload()">
                            <i class="fas fa-sync"></i> Reload
                        </button>
                    </div>
                `;
            });
    }
    
    // 显示空状态
    function showEmptyState() {
        recipesContainer.innerHTML = `
            <div class="empty-recipes">
                <i class="fas fa-book-open"></i>
                <h3>No Recipes Found</h3>
                <p>Start creating delicious recipes to build your collection!</p>
                <a href="/" class="create-recipe-btn">
                    <i class="fas fa-plus"></i> Create New Recipe
                </a>
            </div>
        `;
    }
    
    // 筛选食谱
    function filterRecipes() {
        const searchTerm = searchInput.value.toLowerCase().trim();
        const filterValue = document.querySelector('input[name="filter"]:checked').value;
        
        // 先按搜索词筛选
        if (searchTerm) {
            filteredRecipes = allRecipes.filter(recipe => {
                const recipeName = (recipe.recipe_name || '').toLowerCase();
                let ingredientsText = '';
                
                // 处理 ingredients 可能是字符串或数组的情况
                if (recipe.ingredients) {
                    if (Array.isArray(recipe.ingredients)) {
                        ingredientsText = recipe.ingredients.join(' ').toLowerCase();
                    } else {
                        ingredientsText = recipe.ingredients.toString().toLowerCase();
                    }
                }
                
                return recipeName.includes(searchTerm) || ingredientsText.includes(searchTerm);
            });
        } else {
            filteredRecipes = [...allRecipes];
        }
        
        // 再按选定的筛选条件排序
        switch (filterValue) {
            case 'recent':
                filteredRecipes.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                break;
            case 'alphaAZ':
                filteredRecipes.sort((a, b) => {
                    const nameA = (a.recipe_name || 'Untitled').toLowerCase();
                    const nameB = (b.recipe_name || 'Untitled').toLowerCase();
                    return nameA.localeCompare(nameB);
                });
                break;
            case 'alphaZA':
                filteredRecipes.sort((a, b) => {
                    const nameA = (a.recipe_name || 'Untitled').toLowerCase();
                    const nameB = (b.recipe_name || 'Untitled').toLowerCase();
                    return nameB.localeCompare(nameA);
                });
                break;
            // 'all' 不需要特殊排序，保持默认顺序
        }
        
        // 重置页码并重新渲染
        currentPage = 1;
        renderRecipes();
    }
    
    // 渲染食谱卡片
    function renderRecipes() {
        if (filteredRecipes.length === 0) {
            recipesContainer.innerHTML = `
                <div class="empty-recipes">
                    <i class="fas fa-search"></i>
                    <h3>No Matching Recipes</h3>
                    <p>Try adjusting your search or filter criteria.</p>
                    <button class="create-recipe-btn" onclick="clearFilters()">
                        <i class="fas fa-times"></i> Clear Filters
                    </button>
                </div>
            `;
            paginationContainer.innerHTML = '';
            return;
        }
        
        // 计算分页
        const totalPages = Math.ceil(filteredRecipes.length / recipesPerPage);
        const startIndex = (currentPage - 1) * recipesPerPage;
        const endIndex = Math.min(startIndex + recipesPerPage, filteredRecipes.length);
        const recipesToShow = filteredRecipes.slice(startIndex, endIndex);
        
        // 渲染食谱卡片
        let html = '';
        recipesToShow.forEach(recipe => {
            const recipeDate = new Date(recipe.created_at).toLocaleDateString();
            const recipeId = recipe.id;
            const isSelected = selectedRecipes.has(recipeId);
            
            html += `
                <div class="recipe-card ${isSelected ? 'selected' : ''}" data-id="${recipeId}">
                    ${isSelectionMode ? `<input type="checkbox" class="recipe-select" ${isSelected ? 'checked' : ''}>` : ''}
                    <h3>${recipe.recipe_name || 'Untitled Recipe'}</h3>
                    <div class="recipe-card-info">
                        <span><i class="fas fa-calendar"></i> ${recipeDate}</span>
                        <span><i class="fas fa-utensils"></i> ${recipe.ingredients ? (recipe.ingredients.length + ' ingredients') : 'No ingredients listed'}</span>
                    </div>
                    <div class="recipe-actions">
                        <button class="view-btn" onclick="viewRecipe(${recipeId}, event)">
                            <i class="fas fa-eye"></i> View
                        </button>
                        <button class="delete-btn" onclick="deleteRecipe(${recipeId}, event)">
                            <i class="fas fa-trash"></i> Delete
                        </button>
                        <button class="share-btn" onclick="shareRecipe(${recipeId}, event)">
                            <i class="fas fa-share-alt"></i> Share
                        </button>
                    </div>
                </div>
            `;
        });
        
        recipesContainer.innerHTML = html;
        
        // 如果处于选择模式，添加复选框变更事件
        if (isSelectionMode) {
            document.querySelectorAll('.recipe-select').forEach(checkbox => {
                checkbox.addEventListener('change', function() {
                    const recipeId = this.closest('.recipe-card').dataset.id;
                    if (this.checked) {
                        selectedRecipes.add(recipeId);
                        this.closest('.recipe-card').classList.add('selected');
                    } else {
                        selectedRecipes.delete(recipeId);
                        this.closest('.recipe-card').classList.remove('selected');
                    }
                    updateSelectedCount();
                });
            });
        }
        
        // 渲染分页
        renderPagination(totalPages);
    }
    
    // 渲染分页控件
    function renderPagination(totalPages) {
        if (totalPages <= 1) {
            paginationContainer.innerHTML = '';
            return;
        }
        
        let paginationHtml = '';
        // 添加上一页按钮
        paginationHtml += `
            <button class="pagination-btn prev-btn ${currentPage === 1 ? 'disabled' : ''}" 
                ${currentPage === 1 ? 'disabled' : 'onclick="changePage(' + (currentPage - 1) + ')"'}>
                <i class="fas fa-chevron-left"></i>
            </button>
        `;
        
        // 添加页码按钮
        // 如果页数较多，只显示附近的几页
        if (totalPages <= 5) {
            for (let i = 1; i <= totalPages; i++) {
                paginationHtml += `
                    <button class="pagination-btn ${i === currentPage ? 'active' : ''}" 
                        onclick="changePage(${i})">
                        ${i}
                    </button>
                `;
            }
        } else {
            // 显示第一页
            paginationHtml += `
                <button class="pagination-btn ${1 === currentPage ? 'active' : ''}" 
                    onclick="changePage(1)">
                    1
                </button>
            `;
            
            // 省略号
            if (currentPage > 3) {
                paginationHtml += `<span class="pagination-ellipsis">...</span>`;
            }
            
            // 当前页附近的页码
            for (let i = Math.max(2, currentPage - 1); i <= Math.min(totalPages - 1, currentPage + 1); i++) {
                paginationHtml += `
                    <button class="pagination-btn ${i === currentPage ? 'active' : ''}" 
                        onclick="changePage(${i})">
                        ${i}
                    </button>
                `;
            }
            
            // 省略号
            if (currentPage < totalPages - 2) {
                paginationHtml += `<span class="pagination-ellipsis">...</span>`;
            }
            
            // 显示最后一页
            paginationHtml += `
                <button class="pagination-btn ${totalPages === currentPage ? 'active' : ''}" 
                    onclick="changePage(${totalPages})">
                    ${totalPages}
                </button>
            `;
        }
        
        // 添加下一页按钮
        paginationHtml += `
            <button class="pagination-btn next-btn ${currentPage === totalPages ? 'disabled' : ''}" 
                ${currentPage === totalPages ? 'disabled' : 'onclick="changePage(' + (currentPage + 1) + ')"'}>
                <i class="fas fa-chevron-right"></i>
            </button>
        `;
        
        paginationContainer.innerHTML = paginationHtml;
    }
    
    // 切换选择模式
    function toggleSelectionMode(force = null) {
        isSelectionMode = force !== null ? force : !isSelectionMode;
        
        if (isSelectionMode) {
            selectBtn.innerHTML = '<i class="fas fa-times"></i><span>Cancel</span>';
            selectBtn.classList.add('active');
            bulkActions.classList.add('show');
            document.body.classList.add('selection-mode');
        } else {
            selectBtn.innerHTML = '<i class="fas fa-check-square"></i><span>Select</span>';
            selectBtn.classList.remove('active');
            bulkActions.classList.remove('show');
            document.body.classList.remove('selection-mode');
            selectedRecipes.clear();
        }
        
        updateSelectedCount();
        renderRecipes();
    }
    
    // 更新选中食谱计数
    function updateSelectedCount() {
        selectedCountText.textContent = selectedRecipes.size;
    }
    
    // 删除单个食谱
    function deleteRecipe(recipeId) {
        // 创建确认对话框元素
        const confirmDialog = document.createElement('div');
        confirmDialog.className = 'confirm-dialog';
        confirmDialog.innerHTML = `
            <div class="confirm-dialog-content">
                <h3>Confirm Deletion</h3>
                <p>Are you sure you want to delete this recipe? This action cannot be undone.</p>
                <div class="confirm-buttons">
                    <button class="cancel-btn">Cancel</button>
                    <button class="confirm-btn">Delete</button>
                </div>
            </div>
        `;
        
        // 添加到页面
        document.body.appendChild(confirmDialog);
        
        // 设置按钮事件
        const cancelBtn = confirmDialog.querySelector('.cancel-btn');
        const confirmBtn = confirmDialog.querySelector('.confirm-btn');
        
        // 取消操作
        cancelBtn.addEventListener('click', () => {
            document.body.removeChild(confirmDialog);
        });
        
        // 确认删除
        confirmBtn.addEventListener('click', async () => {
            // 移除确认对话框
            document.body.removeChild(confirmDialog);
            
            try {
                const response = await fetch(`/api/delete-recipe/${recipeId}`, {
                    method: 'DELETE'
                });
                const data = await response.json();
                
                if (data.success) {
                    // 使用toast显示成功消息
                    if (window.toastMessage) {
                        toastMessage.success('Recipe deleted successfully');
                    }
                    
                    // 移除菜谱卡片
                    const recipeCard = document.querySelector(`.recipe-card[data-id="${recipeId}"]`);
                    if (recipeCard) {
                        recipeCard.remove();
                    }
                    
                    // 如果没有菜谱了，显示空状态
                    const recipesContainer = document.getElementById('saved-recipes');
                    if (recipesContainer && recipesContainer.children.length === 0) {
                        recipesContainer.innerHTML = '<div class="empty-recipes">No saved recipes</div>';
                    }
                } else {
                    // 使用toast显示错误消息
                    if (window.toastMessage) {
                        toastMessage.error(data.message || 'Failed to delete recipe');
                    } else {
                        alert(data.message || 'Failed to delete recipe');
                    }
                }
            } catch (error) {
                console.error('Error deleting recipe:', error);
                // 使用toast显示错误消息
                if (window.toastMessage) {
                    toastMessage.error('Failed to delete recipe. Please check your connection and try again.');
                } else {
                    alert('Failed to delete recipe. Please check your connection and try again.');
                }
            }
        });
    }
    
    // 确认批量删除
    function confirmBulkDelete() {
        if (!confirm(`确定要删除已选择的 ${selectedRecipes.size} 个菜谱吗？此操作无法撤销。`)) {
            return;
        }
        
        const deletePromises = Array.from(selectedRecipes).map(recipeId => {
            return fetch(`/api/delete-recipe/${recipeId}`, {
                method: 'DELETE'
            }).then(response => response.json());
        });
        
        Promise.all(deletePromises)
            .then(results => {
                // 检查所有删除操作是否成功
                const failedDeletes = results.filter(result => !result.success);
                
                if (failedDeletes.length > 0) {
                    toastMessage.warning(`${failedDeletes.length} 个菜谱删除失败。`);
                }
                
                // 从列表中移除已删除的食谱
                allRecipes = allRecipes.filter(recipe => !selectedRecipes.has(recipe.id));
                filteredRecipes = filteredRecipes.filter(recipe => !selectedRecipes.has(recipe.id));
                
                // 退出选择模式
                toggleSelectionMode(false);
                
                // 重新渲染
                if (allRecipes.length === 0) {
                    showEmptyState();
                } else {
                    renderRecipes();
                }
                
                const successCount = results.length - failedDeletes.length;
                if (successCount > 0) {
                    toastMessage.success(`已成功删除 ${successCount} 个菜谱！`);
                }
            })
            .catch(error => {
                console.error('Error in bulk delete:', error);
                toastMessage.error('批量删除操作出错，请重试。');
            });
    }
    
    // 分享食谱
    function shareRecipe(recipeId, event) {
        if (event) {
            event.stopPropagation();
        }
        
        // 构建分享链接
        const shareUrl = `${window.location.origin}/my-recipes/${recipeId}`;
        
        // 检查Web Share API是否可用
        if (navigator.share) {
            navigator.share({
                title: 'Check out this recipe from Flavor Fusion!',
                url: shareUrl
            }).catch(err => {
                console.error('Share failed:', err);
                fallbackShare(shareUrl);
            });
        } else {
            fallbackShare(shareUrl);
        }
    }
    
    // 分享功能的后备方案
    function fallbackShare(url) {
        // 创建一个临时输入框，复制链接到剪贴板
        const tempInput = document.createElement('input');
        tempInput.value = url;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);
        
        toastMessage.success('链接已复制到剪贴板: ' + url);
    }
    
    // 清除所有筛选条件
    function clearFilters() {
        // 重置搜索框
        if (searchInput) {
            searchInput.value = '';
        }
        
        // 重置筛选选项为"全部"
        const allFilterOption = document.getElementById('filter-all');
        if (allFilterOption) {
            allFilterOption.checked = true;
        }
        
        // 重新加载所有食谱
        filteredRecipes = [...allRecipes];
        currentPage = 1;
        renderRecipes();
    }
    
    // 防抖函数，限制搜索频率
    function debounce(func, wait) {
        let timeout;
        return function() {
            const context = this, args = arguments;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), wait);
        };
    }
    
    // 切换页码
    function changePage(page) {
        currentPage = page;
        renderRecipes();
        // 滚动到页面顶部
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    
    // 查看菜谱详情
    function viewRecipe(recipeId, event) {
        if (event) {
            event.preventDefault(); // 阻止默认事件
            event.stopPropagation(); // 阻止事件冒泡
        }
        // 使用延时确保任何可能的事件处理已完成
        setTimeout(() => {
            window.location.href = `/my-recipes/${recipeId}`;
        }, 10);
    }
    
    // 在window对象上暴露需要在HTML中直接调用的函数
    window.deleteRecipe = deleteRecipe;
    window.shareRecipe = shareRecipe;
    window.clearFilters = clearFilters;
    window.changePage = changePage;
    window.viewRecipe = viewRecipe;
}); 