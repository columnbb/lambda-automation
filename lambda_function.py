# 決定採用 AWS＋Perplexity＋StableDiffusion＋Hugo＋Netligy 架構
# 018 提示詞改放S3、免責聲明強制附加
import os
import sys
import json
import re
import boto3
from io import BytesIO

# 從 S3 讀取提示詞載入程式碼
def load_file_from_s3(bucket, key):
    """從 S3 讀取文字檔案並回傳字串"""
    s3 = boto3.client('s3')
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj['Body'].read().decode('utf-8')

# 添加依賴層路徑
sys.path.append('/opt/python')

# 現在可以導入 Layer 中的套件
import requests
import feedparser
import jwt
import time

# 提示詞層路徑
PROMPTS_DIR = '/opt/assets/prompts'

def load_sd_prompt_config():
    try:
        bucket = os.environ['S3_BUCKET_NAME']
        key = 'prompts/sd_prompt_config.json'
        content = load_file_from_s3(bucket, key)
        return json.loads(content)
    except Exception as e:
        print(f"SD提示詞配置加載失敗: {str(e)}")
        return {
            "default_style": "realistic",
            "negative_prompt": "",
            "resolution_ratio": 1.77
        }

def generate_sd_prompt(title, style_override=None):
    config = load_sd_prompt_config()
    style = style_override or config.get('default_style', 'realistic')
    bucket = os.environ['S3_BUCKET_NAME']
    key = 'prompts/sd_prompt_template.txt'
    template = load_file_from_s3(bucket, key).strip()
    return template.format(title=title, style=style)


def generate_and_upload_image(title, bucket_name):
    try:
        prompt = generate_sd_prompt(title)
        config = load_sd_prompt_config()
        # 解析resolution
        resolution = config.get('resolution', '1024x576')
        if 'x' in resolution:
            width, height = [int(x) for x in resolution.split('x')]
        else:
            width, height = 1024, 576

        response = requests.post(
            "https://api.stability.ai/v2beta/stable-image/generate/sd3",
            headers={
                "Authorization": f"Bearer {os.environ['STABILITY_API_KEY']}",
                "Accept": "image/*"
            },
            files={"none": ''},
            data={
                "prompt": prompt,
                "output_format": "png",
                "negative_prompt": config.get('negative_prompt', ''),
                "width": width,
                "height": height
            }
        )
        if response.status_code != 200:
            raise Exception(f"API錯誤: {response.text}")

        s3 = boto3.client('s3')
        image_key = f"images/{int(time.time())}.png"
        s3.upload_fileobj(BytesIO(response.content), bucket_name, image_key)
        return s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': image_key},
            ExpiresIn=604800
        )
    except Exception as e:
        print(f"圖片生成失敗: {str(e)}")
        return "https://example.com/default-image.png"

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
            
            # ===== 新增 SD 提示詞測試 =====
            try:
                # 測試 SD 配置
                sd_config = load_sd_prompt_config()
                print(f"✅ SD提示詞配置載入成功: {json.dumps(sd_config, ensure_ascii=False)}")
                
                # 測試 SD 模板
                sd_template_path = os.path.join(PROMPTS_DIR, 'sd_prompt_template.txt')
                with open(sd_template_path, 'r', encoding='utf-8') as f:
                    sd_template = f.read().strip()
                print(f"✅ SD 提示詞模板載入成功，長度: {len(sd_template)} 字元")
                print(f"✅ SD 提示詞模板開頭: {sd_template[:50]}...")
                
                # 測試動態提示詞生成
                test_title = "區塊鏈技術革命"
                generated_prompt = generate_sd_prompt(test_title)
                print(f"✅ 動態提示詞生成測試: {generated_prompt}")
            except Exception as sd_e:
                print(f"❌ SD提示詞測試失敗: {str(sd_e)}")
        else:
            print("❌ 提示詞目錄不存在")
    except Exception as e:
        print("❌ 提示詞層測試失敗:", str(e))
    
    print("=== Layer 測試結束 ===")

def parse_ai_response(ai_output):
    """使用正則表達式解析 AI 回應"""
    try:
        title_match = re.search(r'【標題：】\s*(.+?)(?:\n|【內文：】|$)', ai_output, re.DOTALL)
        # 修改：包含完整內容，包括免責聲明
        content_match = re.search(r'【內文：】\s*(.+)', ai_output, re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        content = content_match.group(1).strip() if content_match else ""
        return title, content
    except Exception as e:
        print(f"解析錯誤: {str(e)}")
        return "", ""

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
    # 測試 Layer 是否正確載入
    test_layers()
    
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
            print(f"=== Perplexity API 回應內容 ===")
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

            # 使用正則解析
            title, content = parse_ai_response(ai_output)
            
            if not title or not content:
                raise ValueError("標題或內文解析為空")
            
            # 解析後的內容檢查
            parsed_title, parsed_content = parse_ai_response(ai_output)
            print(f"📋 解析後標題長度: {len(parsed_title)} 字元")
            print(f"📋 解析後內文長度: {len(parsed_content)} 字元")
            print(f"📋 解析後內容包含免責聲明: {'✅' if has_disclaimer(parsed_content) else '❌'}")

            # 最終組裝檢查
            final_markdown = build_markdown_output(parsed_title, parsed_content, article['source'], article['url'])
            print(f"📋 最終Markdown長度: {len(final_markdown)} 字元")
            print(f"📋 最終內容包含免責聲明: {'✅' if has_disclaimer(final_markdown) else '❌'}")
            print(f"📋 最終內容後100字元: {final_markdown[-100:]}")
            
            # 生成插圖
            image_url = generate_and_upload_image(
                title=title,
                bucket_name=os.environ['S3_BUCKET_NAME']
                )
            md_content = f"![生成插圖]({image_url})\n\n{content}"
            
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
