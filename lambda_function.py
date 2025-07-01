import os
import sys
import json
import re

# 添加依賴層路徑
sys.path.append('/opt/python')

# 現在可以導入 Layer 中的套件
import requests
import feedparser
import jwt
import time

# 提示詞層路徑
PROMPTS_DIR = '/opt/assets/prompts'

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
        with open(os.path.join(PROMPTS_DIR, 'ghost_prompt_tw.txt'), 'r', encoding='utf-8') as f:
            return f.read().strip()
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
            
            prompt = load_prompt_template()
            print(f"✅ 提示詞載入成功，長度: {len(prompt)} 字元")
            print(f"✅ 提示詞開頭: {prompt[:50]}...")
        else:
            print("❌ 提示詞目錄不存在")
    except Exception as e:
        print("❌ 提示詞層測試失敗:", str(e))
    
    print("=== Layer 測試結束 ===")

def parse_ai_response(ai_output):
    """使用正則表達式解析 AI 回應"""
    try:
        title_match = re.search(r'【標題：】\s*(.+?)(?:\n|【內文：】|$)', ai_output, re.DOTALL)
        content_match = re.search(r'【內文：】\s*(.+?)(?:\*\*授權與免責聲明\*\*|$)', ai_output, re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        content = content_match.group(1).strip() if content_match else ""
        return title, content
    except Exception as e:
        print(f"解析錯誤: {str(e)}")
        return "", ""

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
                timeout=30
            )
            response.raise_for_status()
            
            # 解析 AI 回應
            ai_output = response.json()['choices'][0]['message']['content']
            
             # 強化日誌輸出
            print(f"=== Perplexity API 回應內容 ===")
            print(f"回應長度: {len(ai_output)} 字元")
            
            # 使用正則解析
            title, content = parse_ai_response(ai_output)
            
            if not title or not content:
                raise ValueError("標題或內文解析為空")
            
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
