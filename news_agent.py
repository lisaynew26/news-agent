#!/usr/bin/env python3
"""
新闻 Agent：抓取热榜 → 六大分类 → DeepSeek 摘要 → 输出 HTML
"""
import os, json, feedparser, requests
from datetime import datetime
from collections import defaultdict

RSSHUB_BASE = "https://rsshub.app"
HOT_ROUTES = [
    "/weibo/search/hot", "/toutiao/trending", "/baidu/top",
    "/zhihu/hotlist", "/36kr/hot", "/wallstreetcn/hot"
]

CATEGORY_KEYWORDS = {
    "AI": ["ai", "人工智能", "大模型", "gpt", "chatgpt", "sora", "深度学习",
           "openai", "gemini", "claude", "aigc", "llm", "stable diffusion",
           "算法", "机器学习", "推理", "多模态", "智能体", "deepseek",
           "文心一言", "通义千问", "盘古", "悟道", "神经网络"],
    "科技": ["芯片", "半导体", "光刻", "鸿蒙", "华为", "小米", "苹果", "特斯拉",
             "spacex", "火箭", "卫星", "量子", "核聚变", "新能源", "电池",
             "自动驾驶", "机器人", "5g", "6g", "元宇宙", "vr", "ar",
             "脑机", "基因编辑", "航天", "nasa", "c919"],
    "互联网巨头": ["阿里", "阿里巴巴", "淘宝", "天猫", "菜鸟", "蚂蚁集团",
                   "腾讯", "微信", "qq", "腾讯云", "腾讯游戏",
                   "字节", "字节跳动", "抖音", "tiktok", "今日头条", "火山引擎",
                   "京东", "拼多多", "美团", "快手", "小红书", "b站", "哔哩哔哩"],
    "中国政策": ["国务院", "工信部", "发改委", "财政部", "央行", "证监会", "银保监",
                 "政策", "法规", "条例", "新规", "十四五", "双碳", "数据安全",
                 "个人信息保护", "反垄断", "共同富裕", "注册制", "房地产税"],
    "中国经济": ["经济", "gdp", "增长", "通胀", "cpi", "ppi", "pmi",
                 "出口", "进口", "贸易", "投资", "消费", "内需",
                 "a股", "上证", "深证", "创业板", "科创板", "港股", "恒生",
                 "楼市", "房价", "房贷", "利率", "lpr", "存款", "贷款",
                 "地方债", "城投债", "化债", "特别国债"],
    "美国要闻": ["美国", "白宫", "美联储", "拜登", "特朗普", "国会", "参议院",
                 "众议院", "美股", "道琼斯", "纳斯达克", "硅谷银行", "加息",
                 "降息", "cpi", "非农", "贸易战", "芯片法案", "实体清单",
                 "tiktok", "微软", "谷歌", "meta", "amazon"]
}

MAX_PER_SOURCE = 10
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

def fetch_hot_news():
    all_entries = []
    for route in HOT_ROUTES:
        url = f"{RSSHUB_BASE}{route}"
        try:
            feed = feedparser.parse(url)
            src = feed.feed.get("title", route)
            for entry in feed.entries[:MAX_PER_SOURCE]:
                all_entries.append({
                    "title": entry.get("title", "").strip(),
                    "link": entry.get("link", ""),
                    "source": src
                })
        except Exception as e:
            print(f"Error {url}: {e}")
    seen = set()
    dedup = []
    for item in all_entries:
        if item["link"] and item["link"] not in seen:
            seen.add(item["link"])
            dedup.append(item)
    return dedup

def classify(articles):
    classified = defaultdict(list)
    for art in articles:
        text = art["title"].lower()
        for cat, kws in CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in kws):
                classified[cat].append(art)
    return classified

def build_prompt(classified):
    parts = []
    for cat in ["AI", "科技", "互联网巨头", "中国政策", "中国经济", "美国要闻"]:
        arts = classified.get(cat, [])
        if not arts: continue
        lines = [f"【{cat}】"]
        for i, a in enumerate(arts, 1):
            lines.append(f"{i}. {a['title']} （来源：{a['source']}）")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)

def deepseek_summary(prompt):
    if not DEEPSEEK_API_KEY:
        return "未配置 API Key"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}",
               "Content-Type": "application/json"}
    system = ("你是资深时政科技编辑。根据下面各类新闻标题，用简洁中文分六段总结今日要闻，每段不超过60字，"
              "顺序为：🤖 AI进展、🚀 科技产业、🏢 互联网巨头、🇨🇳 中国政策、💰 中国经济、🇺🇸 美国要闻。"
              "只输出内容，不用Markdown，某类无新闻则写“今日无重要动态”。")
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 700
    }
    try:
        r = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=40)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"摘要生成失败: {e}"

def generate_html(classified, summary):
    today = datetime.now().strftime("%Y-%m-%d")
    title = f"📰 {today} AI 每日精选"
    summary_lines = summary.split("\n")
    summary_html = "".join(f"<p>{line.strip()}</p>" for line in summary_lines if line.strip())

    categories_html = ""
    for cat in ["AI", "科技", "互联网巨头", "中国政策", "中国经济", "美国要闻"]:
        arts = classified.get(cat, [])
        if not arts: continue
        cats = f'<div class="category"><h2>{cat}</h2><ol>'
        for a in arts:
            cats += f'<li><a href="{a["link"]}" target="_blank">{a["title"]}</a> <span class="source">({a["source"]})</span></li>'
        cats += '</ol></div>'
        categories_html += cats

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f9f9f9; color: #333; }}
h1 {{ text-align: center; color: #1a1a1a; }}
.summary {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-bottom: 30px; }}
.summary p {{ margin: 8px 0; font-size: 16px; line-height: 1.6; }}
.category {{ background: white; padding: 15px 20px; margin: 15px 0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
.category h2 {{ margin-top: 0; border-bottom: 2px solid #eee; padding-bottom: 8px; }}
a {{ color: #0066cc; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.source {{ color: #888; font-size: 0.9em; }}
.footer {{ text-align: center; margin-top: 40px; color: #aaa; font-size: 14px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="summary">{summary_html}</div>
{categories_html}
<div class="footer">由新闻AI Agent自动生成 · 每日08:00更新 · 数据基于公开热榜</div>
</body>
</html>"""
    return html

def main():
    print("抓取热榜...")
    articles = fetch_hot_news()
    print(f"去重后共 {len(articles)} 条")
    classified = classify(articles)
    prompt = build_prompt(classified)
    print("请求 DeepSeek 摘要...")
    summary = deepseek_summary(prompt)
    html = generate_html(classified, summary)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html 生成完成")

if __name__ == "__main__":
    main()
