# 決定採用 AWS＋Perplexity＋StableDiffusion＋Hugo＋Netligy 架構
# 021 同步儲存文章圖片到 /tmp/content/post、/tmp/static/images並上傳S3，在 Markdown 檔案的最前面插入 front matter，內容包含標題（title）、日期（date）、以及圖片路徑（image）。
import os
import sys
import json
import re
import boto3
import base64
import requests
import feedparser
import jwt
import time
from io import BytesIO
from datetime import datetime

# 定義一個全域變數 S3_IMG_URL
S3_IMG_URL = None

# SD圖像生成 API 解析度參數
SD_RESOLUTION = "1152x896"
SD_RESOLUTION_RATIO = 1.33

# 從 S3 讀取提示詞載入程式碼
def load_file_from_s3(bucket, key):
    """從 S3 讀取文字檔案並回傳字串"""
    s3 = boto3.client('s3')
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj['Body'].read().decode('utf-8')

# 添加依賴層路徑
sys.path.append('/opt/python')

# 提示詞層路徑
PROMPTS_DIR = '/opt/assets/prompts'

# Hugo靜態網頁圖檔存放位置&內容目錄
# HUGO_STATIC_DIR = "static/images"
# HUGO_CONTENT_DIR = "content/posts"
HUGO_CONTENT_DIR = "/tmp/content/posts"
HUGO_STATIC_DIR = "/tmp/static/images"


def generate_save_and_upload_image(sd_prompt, bucket_name):
    """
    1. 生成 Stable Diffusion 圖片
    2. 同步儲存到本地 /tmp/static/images/ 目錄（使用固定常數 HUGO_STATIC_DIR）
    3. 上傳同一份圖片到 S3
    4. 回傳圖片檔名供 Markdown front matter 使用；失敗回傳 None
    """
    try:
        # 1. 呼叫 SDXL 1.0 API
        width, height = [int(x) for x in SD_RESOLUTION.split('x')]
        url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
        headers = {
            "Authorization": f"Bearer {os.environ['STABILITY_API_KEY']}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        body = {
            "text_prompts": [
                {"text": sd_prompt}
            ],
            "cfg_scale": 7.5,
            "height": height,
            "width": width,
            "samples": 1
        }
        resp = requests.post(url, headers=headers, json=body)
        resp.raise_for_status()
        artifact = resp.json()["artifacts"][0]["base64"]
        img_data = BytesIO(base64.b64decode(artifact))

        # 2. 儲存到本地 Hugo static/images/
        os.makedirs(HUGO_STATIC_DIR, exist_ok=True)
        filename = f"{int(time.time())}.png"
        local_path = os.path.join(HUGO_STATIC_DIR, filename)
        with open(local_path, "wb") as f:
            f.write(img_data.getbuffer())

        # 3. 上傳到 S3
        img_data.seek(0)
        s3 = boto3.client('s3')
        image_key = f"images/{filename}"
        s3.upload_fileobj(
            img_data,
            bucket_name,
            image_key,
            ExtraArgs={'ContentType': 'image/png'}
        )

        # 4. 設定全域變數 S3_IMG_URL
        global S3_IMG_URL
        S3_IMG_URL = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': image_key},
            ExpiresIn=604800
        )

        print(f"✅ 圖片已儲存至本地: {local_path}，並上傳 S3 路徑: {image_key}")
        return filename
        
    except requests.exceptions.HTTPError as e:
        print(f"[API 錯誤] HTTP {e.response.status_code}: {e.response.text}")
    except (boto3.exceptions.Boto3Error, Exception) as e:
        print(f"[圖片同步/上傳失敗] {str(e)}")

    return None
    
def create_hugo_post(title, content, image_filename=None):
    """
    建立 Hugo 格式的 Markdown 文章並儲存到 /tmp/content/posts/ 目錄
    
    Args:
        title (str): 文章標題
        content (str): 文章內容
        image_filename (str, optional): 圖片檔名（如果有的話）
    
    Returns:
        str: 建立的文章檔案路徑，失敗時回傳 None
    """
    try:
        # 確保目錄存在
        os.makedirs(HUGO_CONTENT_DIR, exist_ok=True)
        
        # 產生檔案名稱（使用時間戳避免重複）
        timestamp = int(time.time())
        safe_title = title.replace(" ", "-").replace("/", "-").replace(":", "-")[:50]
        filename = f"{timestamp}-{safe_title}.md"
        filepath = os.path.join(HUGO_CONTENT_DIR, filename)
        
        # 建立 front matter
        current_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
        front_matter = f"""---
title: "{title}"
date: {current_date}
draft: false"""
        
        # 如果有圖片，加入 image 欄位
        if image_filename:
            front_matter += f'\nimage: "/images/{image_filename}"'
        
        front_matter += "\n---\n\n"
        
        # 如果有圖片，在內容開頭加入圖片
        if image_filename:
            markdown_content = f"{front_matter}![文章配圖](/images/{image_filename})\n\n{content}"
        else:
            markdown_content = f"{front_matter}{content}"
        
        # 寫入檔案
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        print(f"✅ Hugo 文章已建立：{filepath}")
        return filepath
        
    except Exception as e:
        print(f"[錯誤] 建立 Hugo 文章失敗：{str(e)}")
        return None
    
def process_perplexity_content(parsed_title, parsed_content, sd_prompt):
    """
    處理 Perplexity 內容，生成圖片並建立 Hugo 文章
    
    Args:
        parsed_title (str): 解析後的標題
        parsed_content (str): 解析後的內容
        sd_prompt (str): Stable Diffusion 提示詞
    
    Returns:
        str: 建立的文章檔案路徑
    """
    try:
        # 生成插圖並上傳到 S3 + 同步到本地
        image_filename = generate_save_and_upload_image(
            sd_prompt=sd_prompt,
            bucket_name=os.environ['S3_BUCKET_NAME']
        )
        
        # 建立 Hugo 文章
        article_filepath = create_hugo_post(
            title=parsed_title,
            content=parsed_content,
            image_filename=image_filename
        )
        
        # 上傳到 S3
        if article_filepath:
            save_content_to_s3(
                article_filepath, 
                parsed_title, 
                os.environ['S3_BUCKET_NAME']
            )

        return article_filepath
        
    except Exception as e:
        print(f"[錯誤] 處理 Perplexity 內容失敗：{str(e)}")
        return None

# 如果你需要自動推送到 GitHub，可以加入以下函式
def commit_and_push_to_github(filepath, title):
    """
    將新建立的文章推送到 GitHub
    
    Args:
        filepath (str): 文章檔案路徑
        title (str): 文章標題
    """
    try:
        import subprocess
        
        # Git 操作
        subprocess.run(["git", "add", filepath], check=True)
        subprocess.run(["git", "commit", "-m", f"新增文章: {title}"], check=True)
        subprocess.run(["git", "push"], check=True)
        
        print(f"✅ 文章已推送至 GitHub: {title}")
        
    except subprocess.CalledProcessError as e:
        print(f"[Git 錯誤] 推送失敗：{str(e)}")
    except Exception as e:
        print(f"[錯誤] GitHub 推送失敗：{str(e)}")

# 移除 Git 操作，改用 S3 或其他方式儲存：
def save_content_to_s3(filepath, title, bucket_name):
    """
    將生成的內容上傳到 S3，而不是使用 Git 推送
    """
    try:
        s3 = boto3.client('s3')
        
        # 上傳 Markdown 檔案到 S3
        with open(filepath, 'rb') as f:
            s3.upload_fileobj(
                f,
                bucket_name,
                f"posts/{os.path.basename(filepath)}",
                ExtraArgs={'ContentType': 'text/markdown'}
            )
        
        print(f"✅ 內容已上傳至 S3: {title}")
        return True
        
    except Exception as e:
        print(f"[錯誤] S3 上傳失敗：{str(e)}")
        return False

def generate_ghost_token(admin_key):
    """生成 Ghost 專用 JWT 授權令牌"""
    try:
        id, secret = admin_key.split(':')
        iat = int(time.time())
        header = {'alg': 'HS256', 'typ': 'JWT', 'kid': id}
        payload = {'iat': iat, 'exp': iat + 300, 'aud': '/admin/'}
        return jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers=header)
    except Exception as e:  
        print(f"JWT生成失敗: {str(e)}")
        raise

def load_prompt_template():
    """從提示詞層載入提示詞模板"""
    try:
        bucket = os.environ['S3_BUCKET_NAME']
        key = 'prompts/ghost_prompt_tw.txt'
        return load_file_from_s3(bucket, key).strip()
    except Exception as e:
        print(f"提示詞載入失敗: {str(e)}")
        raise

def test_layers():
    """測試 Layer 是否正確載入"""
    print("=== Layer 測試開始 ===")
    
    # 測試依賴層
    try:
        print("✅ 成功導入 requests 版本:", requests.__version__)
        print("✅ 成功導入 feedparser 版本:", feedparser.__version__)
        print("✅ 成功導入 jwt 模組")
    except Exception as e:
        print("❌ 依賴層載入失敗:", str(e))
    
    # 測試提示詞層
    try:
        if os.path.exists(PROMPTS_DIR):
            files = os.listdir(PROMPTS_DIR)
            print(f"✅ 提示詞目錄存在，內容: {files}")
            
            # 測試主提示詞
            prompt = load_prompt_template()
            print(f"✅ 提示詞載入成功，長度: {len(prompt)} 字元")
            print(f"✅ 提示詞開頭: {prompt[:50]}...")
        else:
            print("❌ 提示詞目錄不存在")
    except Exception as e:
        print("❌ 提示詞層測試失敗:", str(e))
    
    print("=== Layer 測試結束 ===")

def check_Perplexity(ai_output, source, url):
    print(f"=== Perplexity API 檢查內容開始 ===")
    print(f"回應長度: {len(ai_output)} 字元")   
            
    # 檢查關鍵字與格式
    title_matches = re.findall(r'【標題：】\s*(.+?)(?:\n|【內文：】|$)', ai_output, re.DOTALL)
    content_matches = re.findall(r'【內文：】\s*(.+?)(?:\*\*授權與免責聲明\*\*|$)', ai_output, re.DOTALL)
    disclaimer_matches = re.findall(r'\*\*授權與免責聲明\*\*.*?(?:\n\n|$)', ai_output, re.DOTALL)

    print(f"📋 找到標題數量: {len(title_matches)}")
    print(f"📋 找到內文數量: {len(content_matches)}")  
    print(f"📋 找到免責聲明數量: {len(disclaimer_matches)}")

    if title_matches:
        print(f"📋 標題內容: {title_matches[0][:50]}...")
    if content_matches:
        print(f"📋 內文開頭: {content_matches[0][:100]}...")
    if disclaimer_matches:
        print(f"📋 免責聲明內容: {disclaimer_matches[0][:100]}...")

    # 解析後的內容檢查
    parsed_title, parsed_content, parsed_sd_prompt = parse_ai_response(ai_output)
    print(f"📋 解析後標題長度: {len(parsed_title)} 字元")
    print(f"📋 解析後內文長度: {len(parsed_content)} 字元")
    print(f"📋 解析後SD提示詞長度: {len(parsed_sd_prompt)} 字元")
    print(f"📋 解析後內容包含免責聲明: {'✅' if has_disclaimer(parsed_content) else '❌'}")

    # 最終組裝檢查
    final_markdown = build_markdown_output(parsed_title, parsed_content, source, url)
    print(f"📋 最終Markdown長度: {len(final_markdown)} 字元")
    print(f"📋 最終內容包含免責聲明: {'✅' if has_disclaimer(final_markdown) else '❌'}")
    print(f"📋 最終內容後100字元: {final_markdown[-100:]}")
            
    print(f"=== Perplexity API 檢查內容結束 ===")

def parse_ai_response(ai_output):
    """使用正則表達式解析 AI 回應，並確保提示詞不為空"""
    try:
        title_match = re.search(r'【標題：】\s*(.+?)(?:\n|【內文：】|$)', ai_output, re.DOTALL)
        content_match = re.search(r'【內文：】\s*(.+?)(?:\n*【圖像提示詞：】|$)', ai_output, re.DOTALL)
        prompt_match = re.search(r'【圖像提示詞：】\s*(.+)', ai_output, re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        content = content_match.group(1).strip() if content_match else ""
        sd_prompt = prompt_match.group(1).strip() if prompt_match else ""

        # 驗證 SD 提示詞
        if not sd_prompt or len(sd_prompt) < 5:
            sd_prompt = "A professional, clean, minimalist illustration related to cryptocurrency and blockchain technology"
            print(f"[警告] SD 提示詞過短或為空，使用預設值：{sd_prompt}")
            
        return title, content, sd_prompt
    except Exception as e:
        print(f"解析錯誤: {str(e)}")
        return "", "", ""

def has_disclaimer(text: str) -> bool:
    """檢查文字中是否已包含「授權與免責聲明」段落"""
    return bool(re.search(r'\*\*授權與免責聲明\*\*', text))

def build_markdown_output(title, content, source, url):
    disclaimer = (
        "\n**授權與免責聲明**\n"
        f"> 本文章根據 {source}（CC-BY 4.0） 內容翻譯改寫，原文連結：{url}\n"
        "> 本文僅供資訊參考，不構成任何投資建議或法律意見。"
        "加密貨幣及區塊鏈相關投資具高風險，請審慎評估自身風險承受能力。\n"
    )

    # 如果 content 已經包含「授權與免責聲明」，就不用再附加
    if has_disclaimer(content):
        return f"【標題：】{title}\n\n【內文：】\n{content}"
    else:
        return f"【標題：】{title}\n\n【內文：】\n{content}{disclaimer}"

def markdown_to_html(md_content):
    """
    將 Markdown 轉換為 HTML（基本轉換）
    """
    # 轉換標題
    md_content = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'^##\s+(.+)$', r'<h2>\1</h2>', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'^###\s+(.+)$', r'<h3>\1</h3>', md_content, flags=re.MULTILINE)
    
    # 轉換粗體和斜體
    md_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', md_content)
    md_content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', md_content)
    
    # 轉換列表
    md_content = re.sub(r'^\*\s+(.+)$', r'<li>\1</li>', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', md_content, flags=re.DOTALL)
    
    # 轉換段落和換行
    md_content = re.sub(r'\n\n', r'</p><p>', md_content)
    md_content = '<p>' + md_content + '</p>'
    md_content = md_content.replace('\n', '<br>')
    
    return md_content

def lambda_handler(event, context):
    global S3_IMG_URL

    # 測試 Layer 是否正確載入
    # test_layers()
    
    # RSS 來源設定
    rss_feeds = [
        "https://cointelegraph.com/rss",
        "https://decrypt.co/feed",
        "https://cryptoslate.com/feed/"
    ]
    
    # 從環境變數獲取金鑰
    try:
        perplexity_api_key = os.environ['PERPLEXITY_API_KEY']
        ghost_admin_key = os.environ['GHOST_ADMIN_KEY']
        ghost_blog_url = os.environ['GHOST_BLOG_URL']
    except KeyError as e:
        error_msg = f"環境變數缺失: {str(e)}"
        print(error_msg)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_msg})
        }
    
    # 載入提示詞模板
    prompt_template = load_prompt_template()
    
    # 抓取 RSS 最新文章
    articles = []
    for feed_url in rss_feeds:
        try:
            feed = feedparser.parse(feed_url)
            if feed.entries:
                latest_entry = feed.entries[0]
                articles.append({
                    "title": latest_entry.title,
                    "url": latest_entry.link,
                    "source": "CoinTelegraph" if "cointelegraph" in feed_url else 
                              "Decrypt" if "decrypt" in feed_url else 
                              "CryptoSlate"
                })
        except Exception as e:
            print(f"RSS 抓取失敗 {feed_url}: {str(e)}")
            continue
    
    if not articles:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": "未找到任何文章"})
        }
    
    # 處理每篇文章
    processed_articles = []
    for article in articles:
        # 根據文章類型自動選擇模型
        title_lower = article['title'].lower()
        is_technical = any(keyword in title_lower for keyword in [
            'technical', 'analysis', 'whitepaper', 'protocol', 
            'consensus', 'zk-proof', 'zero-knowledge', 'rollup',
            'sharding', 'tokenomics', 'governance', 'audit'
        ])
        
        # 自動切換模型配置
        model = "sonar-pro" if is_technical else "sonar"
        mode = "high" if is_technical else "medium"
        
        # 動態生成提示詞
        prompt = prompt_template.format(
            source=article['source'],
            url=article['url'],
            title=article['title']
        )
        
        try:
            # 調用 Perplexity API
            headers = {
                "Authorization": f"Bearer {perplexity_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "mode": mode,
                "messages": [{"role": "user", "content": prompt}]
            }
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                json=payload,
                headers=headers,
                timeout=(30, 180)  # 連接超時30秒，讀取超時180秒
            )
            response.raise_for_status()

            # 解析 AI 回應
            ai_output = response.json()['choices'][0]['message']['content']
            
            # 強化日誌輸出
            check_Perplexity(ai_output, article['source'], article['url'])
           
            # 使用正則解析
            title, content, sd_prompt = parse_ai_response(ai_output)
            
            if not title or not content:
                raise ValueError("標題或內文解析為空")
            
            # 生成插圖
            article_filepath = process_perplexity_content(
                parsed_title=title,
                parsed_content=content,
                sd_prompt=sd_prompt
                )
            
            # 如果需要推送到 GitHub
            # if article_filepath:
                # commit_and_push_to_github(article_filepath, title)
            
            # 生成 Ghost JWT
            ghost_token = generate_ghost_token(ghost_admin_key)
            
            # 發布到 Ghost
            ghost_headers = {
                "Authorization": f"Ghost {ghost_token}",
                "Content-Type": "application/json"
            }

            # 將 Markdown 轉換為 HTML
            html_content = markdown_to_html(content)
            
            # 使用 mobiledoc 格式 (HTML 卡片)
            mobiledoc = {
                "version": "0.3.1",
                "markups": [],
                "atoms": [],
                "cards": [
                    ["html", {"html": html_content}]
                ],
                "sections": [[10, 0]]  # 引用第一個卡片
            }

            post_data = {
                "posts": [{
                    "title": title,
                    "mobiledoc": json.dumps(mobiledoc),
                    "feature_image": S3_IMG_URL,  # 這裡放 Lambda 產生的圖片網址
                    "status": "draft",
                    "tags": ["區塊鏈", "AI生成", "技術分析" if is_technical else "市場動態"]
                }]
            }
            
            # 發送請求到 Ghost
            ghost_res = requests.post(
                f"{ghost_blog_url}/ghost/api/admin/posts/",
                json=post_data,
                headers=ghost_headers
            )
            
            ghost_res.raise_for_status()
            
            success_msg = f"✅ 已建立草稿: {title[:30]}... | 來源: {article['source']}"
            print(success_msg)
            
            processed_articles.append({
                "title": title,
                "source": article['source'],
                "status": "success"
            })

        except requests.exceptions.Timeout:
            print(f"⏰ Perplexity API 超時: {article['url']}")
            continue  # 跳過這篇文章，處理下一篇
    
        except requests.exceptions.RequestException as e:
            print(f"🔗 網路連線錯誤: {str(e)}")
            continue

        except Exception as e:
            error_detail = f"❌ 處理失敗: {article['url']} | 錯誤: {type(e).__name__}-{str(e)[:100]}"
            print(error_detail)
            
            processed_articles.append({
                "title": article['title'],
                "source": article['source'],
                "status": "failed",
                "error": str(e)
            })
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "completed",
            "processed": len(articles),
            "successful": len([a for a in processed_articles if a['status'] == 'success']),
            "failed": len([a for a in processed_articles if a['status'] == 'failed']),
            "technical_count": sum(1 for a in articles if any(keyword in a['title'].lower() for keyword in ['technical', 'analysis', 'whitepaper'])),
            "articles": processed_articles
        }, ensure_ascii=False)
    }
