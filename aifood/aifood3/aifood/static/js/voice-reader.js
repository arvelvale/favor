/**
 * 简化版语音朗读功能
 * 为 Flavor Fusion 生成的食谱提供语音朗读功能
 */

// 全局变量存储语音朗读器实例
let globalVoiceReader = null;

class SimpleVoiceReader {
    constructor() {
        // 初始化语音合成对象
        this.synth = window.speechSynthesis;
        this.voices = [];
        this.currentVoice = null;
        this.utterance = null;
        this.isPlaying = false;
        this.isPaused = false;
        this.rate = 1.0; // 默认语速
        
        // 开场白和结束语
        this.introText = "Welcome to Flavor Fusion! Let's create something delicious together.";
        this.outroText = "Well done, chef! Your dish is ready to impress.";
        
        // 获取DOM元素
        this.voiceBtn = document.getElementById('voice-reader-btn');
        this.speedSelector = document.getElementById('speed-selector');
        this.speedBtns = document.querySelectorAll('.speed-btn');
        
        // 初始化事件监听
        this.initEventListeners();
        
        // 加载可用的语音
        this.loadVoices();
    }
    
    // 初始化事件监听
    initEventListeners() {
        // 播放按钮点击事件
        if (this.voiceBtn) {
            this.voiceBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // 阻止事件冒泡
                
                if (this.isPlaying) {
                    this.stopSpeech();
                } else {
                    // 显示语速选择器
                    this.toggleSpeedSelector();
                }
            });
        }
        
        // 语速按钮点击事件
        this.speedBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation(); // 阻止事件冒泡
                
                this.speedBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.rate = parseFloat(btn.getAttribute('data-rate'));
                
                // 隐藏语速选择器并开始朗读
                this.speedSelector.classList.add('hidden');
                this.startSpeech();
            });
        });
        
        // 点击页面其他地方关闭语速选择器
        document.addEventListener('click', (e) => {
            if (!this.speedSelector.contains(e.target) && e.target !== this.voiceBtn) {
                this.speedSelector.classList.add('hidden');
            }
        });
        
        // 监听语音合成事件
        this.synth.addEventListener('voiceschanged', () => {
            this.loadVoices();
        });
    }
    
    // 切换语速选择器显示状态
    toggleSpeedSelector() {
        if (this.speedSelector.classList.contains('hidden')) {
            // 计算位置
            const btnRect = this.voiceBtn.getBoundingClientRect();
            this.speedSelector.style.top = `${btnRect.bottom + window.scrollY}px`;
            this.speedSelector.style.left = `${btnRect.left + window.scrollX}px`;
            
            this.speedSelector.classList.remove('hidden');
        } else {
            this.speedSelector.classList.add('hidden');
        }
    }
    
    // 加载可用的语音
    loadVoices() {
        this.voices = this.synth.getVoices();
        
        // 优先选择英语语音
        this.currentVoice = this.voices.find(voice => 
            voice.lang.includes('en-US') && voice.name.includes('Female')
        );
        
        // 如果没有找到英语女声，则选择任何英语语音
        if (!this.currentVoice) {
            this.currentVoice = this.voices.find(voice => 
                voice.lang.includes('en')
            );
        }
        
        // 如果仍然没有找到，使用第一个可用的语音
        if (!this.currentVoice && this.voices.length > 0) {
            this.currentVoice = this.voices[0];
        }
    }
    
    // 获取要朗读的文本
    getRecipeText() {
        const recipeResult = document.getElementById('recipeResult');
        if (!recipeResult) return '';
        
        // 将HTML内容转换为纯文本
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = recipeResult.innerHTML;
        return tempDiv.textContent || tempDiv.innerText || '';
    }
    
    // 开始语音朗读
    startSpeech() {
        const recipeText = this.getRecipeText();
        if (!recipeText) {
            console.error('没有可朗读的内容');
            return;
        }
        
        // 添加开场白和结束语
        const fullText = `${this.introText} ${recipeText} ${this.outroText}`;
        
        this.utterance = new SpeechSynthesisUtterance(fullText);
        
        // 设置语音参数
        if (this.currentVoice) {
            this.utterance.voice = this.currentVoice;
        }
        this.utterance.rate = this.rate;
        this.utterance.pitch = 1.0;
        
        // 设置事件监听
        this.utterance.onstart = () => {
            this.isPlaying = true;
            this.voiceBtn.classList.add('reading-active');
            this.voiceBtn.innerHTML = '<i class="fas fa-volume-up"></i> Reading...';
        };
        
        this.utterance.onend = () => {
            this.isPlaying = false;
            this.voiceBtn.classList.remove('reading-active');
            this.voiceBtn.innerHTML = '<i class="fas fa-volume-up"></i> Read Recipe';
        };
        
        this.utterance.onerror = (e) => {
            console.error('Speech synthesis error:', e);
            this.isPlaying = false;
            this.voiceBtn.classList.remove('reading-active');
            this.voiceBtn.innerHTML = '<i class="fas fa-volume-up"></i> Read Recipe';
        };
        
        // 开始朗读
        this.synth.speak(this.utterance);
    }
    
    // 停止朗读
    stopSpeech() {
        if (this.isPlaying) {
            this.synth.cancel();
            this.isPlaying = false;
            this.voiceBtn.classList.remove('reading-active');
            this.voiceBtn.innerHTML = '<i class="fas fa-volume-up"></i> Read Recipe';
        }
    }
}

// 全局函数获取语音朗读器实例
function getVoiceReader() {
    return globalVoiceReader;
}

// 在页面加载完成后初始化语音朗读功能
document.addEventListener('DOMContentLoaded', function() {
    globalVoiceReader = new SimpleVoiceReader();
    
    // 监听食谱生成完成事件
    const recipeResult = document.getElementById('recipeResult');
    const recipeActions = document.getElementById('recipeActions');
    
    // 监听食谱内容变化
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' && 
                recipeResult && 
                recipeResult.textContent.trim() !== '' && 
                !recipeResult.querySelector('.empty-recipe')) {
                
                // 当食谱内容生成完成后，显示操作按钮
                if (recipeActions) {
                    recipeActions.style.display = 'flex';
                }
            }
        });
    });
    
    // 开始观察
    if (recipeResult) {
        observer.observe(recipeResult, { childList: true, subtree: true });
    }
});