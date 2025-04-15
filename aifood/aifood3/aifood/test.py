from openai import OpenAI
import os
import time
from dotenv import load_dotenv
import backoff  # 添加backoff库用于重试
import httpx  # 使用httpx而不是requests
import config  # 导入配置文件
import json
from config import logger # Import logger

# 加载环境变量
load_dotenv()

# 获取代理设置
proxies = config.get_proxies()
if proxies:
    print(f"DeepSeek API 使用代理: {proxies}")

# 配置OpenAI客户端
# 注意：我们不直接设置代理，而是通过环境变量设置
if proxies:
    # 设置环境变量，这样httpx会自动使用代理
    if 'http' in proxies:
        os.environ['HTTP_PROXY'] = proxies['http']
    if 'https' in proxies:
        os.environ['HTTPS_PROXY'] = proxies['https']
    print(f"已通过环境变量设置代理")

# 配置OpenAI客户端
client = OpenAI(
    base_url=config.DEEPSEEK_BASE_URL,
    api_key=config.DEEPSEEK_API_KEY,
    timeout=config.API_TIMEOUT
)

def generate_recipe(ingredients, temperature=0.7, max_tokens=2000):
    """
    Generate a recipe based on provided ingredients.
    
    Args:
        ingredients (list): List of ingredients
        temperature (float): Controls randomness (0-2)
        max_tokens (int): Maximum tokens to generate
        
    Returns:
        str: Generated recipe text
    """
    # Retry mechanism
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            # Always use English
            prompt = f"""Create a detailed recipe using some or all of these ingredients: {', '.join(ingredients)}.
            Format your response in Markdown with the following sections:
            
            ### Recipe Name
            
            ---
            
            ### Ingredients (Serves X)
            - **Ingredient 1**: amount
            - **Ingredient 2**: amount
            
            ---
            
            ### Step-by-Step Instructions
            
            #### **Preparation Time**: X minutes
            #### **Cooking Time**: X minutes
            
            1. **Step 1**:
               - Details
            
            2. **Step 2**:
               - Details
            
            ---
            
            ### Nutritional Information (Per Serving)
            - **Calories**: X kcal
            - **Protein**: Xg
            - **Carbohydrates**: Xg
            - **Fat**: Xg
            
            ---
            
            ### Tips for Preparation
            1. Tip 1
            2. Tip 2
            """
            
            # 调用API
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional chef and nutritionist. Provide detailed, accurate recipes in Markdown format."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            # 处理速率限制错误
            if "429" in str(e) and attempt < max_retries - 1:
                print(f"Rate limit exceeded, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数退避
                continue
            
            # 其他错误
            error_msg = f"Error generating recipe: {str(e)}"
            print(error_msg)
            return "Sorry, an error occurred while generating the recipe. Please try again later."

# 使用backoff装饰器自动处理重试
@backoff.on_exception(backoff.expo, 
                     (Exception),
                     max_tries=5,
                     max_time=60)
def create_streaming_response(messages, temperature, max_tokens):
    """创建流式响应，带有自动重试机制"""
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True
    )
    
    # 处理流式响应，将其转换为适当的格式
    def generate():
        for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta.content:
                    # 构建JSON响应
                    data = {
                        "status": "generating",
                        "content": delta.content
                    }
                    # 将JSON转换为字节格式
                    yield f"data: {json.dumps(data)}\n\n".encode('utf-8')
        
        # 发送完成信号
        yield f"data: {json.dumps({'status': 'done'})}\n\n".encode('utf-8')
    
    return generate()

def generate_recipe_stream(ingredients, temperature=0.7, max_tokens=2000, mode='partial', instructions=''):
    """Generate a recipe from a list of ingredients using a streaming approach"""
    import json
    import time
    
    # 根据模式调整提示词
    base_system_message = f"""You are an expert chef who creates delicious recipes based on available ingredients. 
Your task is to generate a creative, practical, and detailed recipe that uses the ingredients provided by the user.

{instructions}

Create your recipe in a clear, step-by-step format with the following sections:
1. Recipe title (as a markdown heading)
2. Brief introduction with flavor profile and dish type
3. List of ingredients with measurements
4. Preparation steps (numbered)
5. Cooking time and servings
6. Nutritional notes (optional)
7. Serving suggestions

Format your response using markdown."""

    # 构建API请求参数
    messages = [
        {"role": "system", "content": base_system_message},
        {"role": "user", "content": f"Please create a recipe using these ingredients: {', '.join(ingredients)}"}
    ]
    
    logger.info(f"Generating recipe stream with ingredients: {ingredients}")
    full_content = ""
    content_yielded = False # Flag to track if any content was yielded
    
    try:
        # 创建流式响应
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        
        # 为前端流式处理响应
        for chunk in response:
            try:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    chunk_content = chunk.choices[0].delta.content
                    full_content += chunk_content
                    content_yielded = True # Mark that we yielded content
                    
                    # Log the yielded chunk for debugging
                    # logger.debug(f"Yielding chunk: {chunk_content[:50]}...") 
                    
                    # 将内容包装成JSON格式
                    data = {
                        "status": "generating",
                        "content": chunk_content
                    }
                    yield f"data: {json.dumps(data)}\n\n".encode('utf-8')
                    
                    # 控制速率以模拟真实输出 (optional)
                    # time.sleep(0.02)
            except Exception as chunk_error:
                 logger.error(f"Error processing chunk: {chunk_error}")
                 # Optionally yield an error chunk here if needed
        
        # Check if any content was actually yielded before sending 'done'
        if not content_yielded:
             logger.warning("DeepSeek stream finished but no content was yielded.")
             # Yield an error instead of 'done' if no content came through
             error_data = {
                 "status": "error",
                 "error": "Failed to generate recipe content from AI. The stream was empty."
             }
             yield f"data: {json.dumps(error_data)}\n\n".encode('utf-8')
             return # Stop here, don't yield 'done'

        # If content was yielded, send the 'done' signal
        logger.info(f"Finished generating recipe stream. Total length: {len(full_content)}")
        done_data = {
            "status": "done",
            # "full_content": full_content # Frontend reconstructs this, no need to send again
        }
        yield f"data: {json.dumps(done_data)}\n\n".encode('utf-8')
        
    except Exception as e:
        logger.error(f"Error during DeepSeek API call or streaming: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        error_data = {
            "status": "error",
            "error": f"Failed to generate recipe: {str(e)}"
        }
        yield f"data: {json.dumps(error_data)}\n\n".encode('utf-8')