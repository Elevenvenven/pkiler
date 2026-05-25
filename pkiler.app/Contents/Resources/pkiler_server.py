#!/usr/bin/env python3
"""pkiler - AI-powered PDF slide reader backend."""

import json, os, shutil, base64, tempfile, traceback
from flask import Flask, request, Response, send_from_directory, send_file
import httpx
import pymupdf

app = Flask(__name__)
PKILER_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(tempfile.gettempdir(), "pkiler_images")

# --- Config loading ---
def load_config():
    api_key = os.environ.get("PKILER_API_KEY", "")
    api_url = os.environ.get("PKILER_API_URL", "https://token-plan-cn.xiaomimimo.com/v1/chat/completions")
    model = os.environ.get("PKILER_VISION_MODEL", "mimo-v2.5")

    if not api_key:
        for env_path in [
            os.path.join(PKILER_DIR, ".env"),
            os.path.expanduser("~/.hermes/.env"),
        ]:
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if "=" not in line or line.startswith("#"):
                            continue
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip()
                        if k == "PKILER_API_KEY" and not api_key:
                            api_key = v
                        elif k == "PKILER_API_URL":
                            api_url = v
                        elif k == "PKILER_VISION_MODEL":
                            model = v
                        elif k == "XIAOMI_API_KEY" and not api_key:
                            api_key = v
            except FileNotFoundError:
                continue
    return api_key, api_url, model

API_KEY, API_URL, VISION_MODEL = load_config()
print(f"[Init] API key set: {bool(API_KEY)}, model: {VISION_MODEL}", flush=True)

# --- Prompts ---
PROMPTS = {
    "brief": "用1-2句话简单说说这页在讲什么，不用任何格式符号。",
    "standard": "用人话解释这页PPT在讲什么，说清楚概念含义和意义。不要用任何格式符号，就像跟朋友聊天一样自然地说出来。",
    "detailed": "非常详细地解读这页PPT。说清楚概念含义、技术原理、数据意义、和相关页的关联。不要用任何格式符号，就像跟朋友聊天一样自然地说出来。",
}

OVERVIEW_PROMPTS = {
    "normal": "这是一个学术演讲PPT的目录。请做一个整体解读，包括：1）核心主题 2）主要部分 3）关键技术贡献 4）最终愿景。就像跟朋友聊天一样自然地说出来。",
    "plain": "这是一个学术演讲PPT的目录。请用最简单的大白话做一个整体解读，就像给完全不懂这个领域的人讲故事一样。说清楚这个演讲在讲什么、核心思想是什么、为什么重要。用生活中的例子来类比。",
}

# --- Helpers ---
def cleanup_images():
    if os.path.exists(IMG_DIR):
        shutil.rmtree(IMG_DIR, ignore_errors=True)
    os.makedirs(IMG_DIR, exist_ok=True)

def pdf_to_images(pdf_path):
    cleanup_images()
    doc = pymupdf.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=100)
        img_path = os.path.join(IMG_DIR, f"page_{i+1}.png")
        pix.save(img_path)
        pages.append({"id": i + 1, "title": page.get_text("text").strip()[:200]})
    doc.close()
    return pages

def get_page_image_base64(page_num):
    img_path = os.path.join(IMG_DIR, f"page_{page_num}.png")
    if not os.path.exists(img_path):
        return None
    doc = pymupdf.open(img_path)
    pix = doc[0].get_pixmap(dpi=100)
    jpeg_data = pix.tobytes("jpeg", jpg_quality=70)
    doc.close()
    return base64.b64encode(jpeg_data).decode()

def stream_sse(payload):
    """Generic SSE streaming generator for the vision API."""
    if not API_KEY:
        yield f"data: {json.dumps({'text': '请先配置 API Key：在 app 所在目录创建 .env 文件，写入 PKILER_API_KEY=你的key'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                API_URL, json=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
            )
            if resp.status_code != 200:
                err = resp.read().decode()[:300]
                yield f"data: {json.dumps({'text': f'API error: {err}'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            for line in resp.iter_lines():
                if not line:
                    continue
                chunk_str = line if isinstance(line, str) else line.decode("utf-8")
                if chunk_str.startswith("data: "):
                    chunk_str = chunk_str[6:]
                if chunk_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(chunk_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield f"data: {json.dumps({'text': content}, ensure_ascii=False)}\n\n"
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass

            yield "data: [DONE]\n\n"

    except Exception as e:
        traceback.print_exc()
        yield f"data: {json.dumps({'text': f'错误: {str(e)}'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

# --- Routes ---
@app.route("/")
def index():
    return send_from_directory(PKILER_DIR, "index.html")

@app.route("/images/<int:page_num>")
def serve_image(page_num):
    img_path = os.path.join(IMG_DIR, f"page_{page_num}.png")
    if os.path.exists(img_path):
        return send_file(img_path, mimetype="image/png")
    return "Not found", 404

@app.route("/api/config")
def config():
    return json.dumps({"has_key": bool(API_KEY), "model": VISION_MODEL})

@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return json.dumps({"error": "No file uploaded"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".pdf"):
        return json.dumps({"error": "Only PDF files are accepted"}), 400

    tmp_path = os.path.join(tempfile.gettempdir(), "pkiler_upload.pdf")
    f.save(tmp_path)
    try:
        pages = pdf_to_images(tmp_path)
        return json.dumps({"pages": pages}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}), 500
    finally:
        os.remove(tmp_path)

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.json
    page_num = data.get("page", 0)
    page_text = data.get("text", "")
    level = data.get("level", "standard")
    plain = data.get("plain", False)
    extra = data.get("prompt", "")

    user_content = []
    img_b64 = get_page_image_base64(page_num)
    if img_b64:
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}})

    instruction = PROMPTS.get(level, PROMPTS["standard"])
    if plain:
        instruction = "用最简单的大白话解释，就像给一个完全不懂这个领域的小白讲故事一样。可以打比方、举生活中的例子，不要用任何专业术语。如果必须用术语，要立刻解释是什么意思。回答控制在一段话以内。"

    text = f"请解读这页PPT的内容。{instruction}"
    if page_text:
        text += f"\n页面标题是：{page_text}"
    if extra:
        text += f"\n\n用户问题：{extra}"
    user_content.append({"type": "text", "text": text})

    # Brief mode uses fewer tokens for faster response
    max_tokens = 512 if level == "brief" else 2048 if level == "standard" else 4096

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {"role": "system", "content": "你是一位学术论文解读助手，擅长用通俗易懂的语言解释复杂的学术概念。"},
            {"role": "user", "content": user_content},
        ],
        "max_completion_tokens": max_tokens,
        "stream": True,
    }
    return Response(stream_sse(payload), mimetype="text/event-stream")

@app.route("/api/overview", methods=["POST"])
def overview():
    data = request.json
    titles = data.get("titles", "")
    plain = data.get("plain", False)

    prompt = OVERVIEW_PROMPTS["plain" if plain else "normal"]
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {"role": "system", "content": "你是一位学术论文解读助手，擅长用通俗易懂的语言解释复杂的学术概念。"},
            {"role": "user", "content": f"{prompt}\n\n目录如下：\n{titles}"},
        ],
        "max_completion_tokens": 4096,
        "stream": True,
    }
    return Response(stream_sse(payload), mimetype="text/event-stream")

if __name__ == "__main__":
    print(f"pkiler backend on http://127.0.0.1:8899", flush=True)
    app.run(host="127.0.0.1", port=8899, debug=False)
