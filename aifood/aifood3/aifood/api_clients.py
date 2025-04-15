import os
import logging
import traceback
import requests
import config
from openai import OpenAI
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get proxy settings
proxies = config.get_proxies()
if proxies:
    logger.info(f"Proxy settings detected: {proxies}")
    
    # Temporarily save current proxy environment variables
    original_http_proxy = os.environ.pop('HTTP_PROXY', None)
    original_https_proxy = os.environ.pop('HTTPS_PROXY', None)

# Create HTTP client without proxy settings
http_client = httpx.Client()

# Configure OpenAI client for DeepSeek
client = OpenAI(
    base_url=config.DEEPSEEK_BASE_URL,
    api_key=config.DEEPSEEK_API_KEY,
    timeout=config.API_TIMEOUT,
    http_client=http_client  # Explicitly provide client without proxy configuration
)

# Restore original proxy environment variables (if any)
if proxies:
    if original_http_proxy:
        os.environ['HTTP_PROXY'] = original_http_proxy
    if original_https_proxy:
        os.environ['HTTPS_PROXY'] = original_https_proxy

def generate_recipe_images(recipe_text):
    """Use Gemini API to generate images related to the recipe"""
    model = "gemini-2.0-flash-exp"
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    params = {"key": ""}  # Replace with your API key
    headers = {"content-type": "application/json"}
    
    # Always use English
    prompt = f"""Here is a recipe. Please generate detailed step-by-step cooking instructions with images.

For EACH key step, please follow this exact format:
1. First write "Image X: [step description]" (where X is the step number)
2. Then generate an image for that specific step

For example:
"Image 1: Preheat the oven to 180°C (350°F)."
[Here the image for preheating would be shown]

"Image 2: Mix the flour, sugar, and eggs in a large bowl."
[Here the image for mixing ingredients would be shown]

Please make sure EVERY important step has both a text label in the exact "Image X:" format AND a corresponding image.

Here is the recipe content:

{recipe_text}"""
    
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"]
        }
    }

    logger.info("Requesting Gemini API to generate recipe images...")
    
    # Use proxies if configured
    gemini_proxies = {}
    if proxies:
        gemini_proxies = proxies
    
    try:
        response = requests.post(
            url=url,
            params=params,
            json=data,
            headers=headers,
            proxies=gemini_proxies,
            timeout=60  # Set 60 second timeout
        )
        
        if response.status_code != 200:
            logger.error(f"Gemini API error: {response.status_code} - {response.text}")
            return {"error": f"API error: {response.status_code}"}
        
        result = response.json()
        
        # 提取文本和图片
        text_content = ""
        images = []
        
        if "candidates" in result and len(result["candidates"]) > 0:
            parts = result["candidates"][0].get("content", {}).get("parts", [])
            
            for part in parts:
                if "text" in part:
                    text_content += part["text"]
                if "inlineData" in part and part["inlineData"]["mimeType"].startswith("image/"):
                    images.append({
                        "mime_type": part["inlineData"]["mimeType"],
                        "data": part["inlineData"]["data"]
                    })
        
        # 返回文本和图片
        return {
            "success": True,
            "text": text_content,
            "images": images
        }
        
    except Exception as e:
        logger.error(f"Error generating images: {str(e)}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": f"Failed to generate images: {str(e)}"}