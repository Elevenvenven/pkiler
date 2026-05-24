# pkiler

AI 幻灯片解读器。拖入 PDF，AI 帮你解读每一页。

## 快速开始

1. 双击 `pkiler.app`
2. 浏览器自动打开
3. 将 PDF 拖入窗口
4. 点击「简略/标准/详细」解读当前页

## 配置 API Key

首次使用需要配置 AI 接口密钥。在 `pkiler.app/Contents/Resources/` 下创建 `.env` 文件：

```
PKILER_API_KEY=你的Key
PKILER_API_URL=https://token-plan-cn.xiaomimimo.com/v1/chat/completions
PKILER_VISION_MODEL=mimo-v2.5
```

可参考 `.env.example` 文件格式。

## 前提条件

- macOS (arm64)
- Python 3.10+
- 依赖：`pip install flask httpx pymupdf`

## 启动方式

方式一：双击 pkiler.app（推荐）
方式二：命令行 `python3 Resources/pkiler_server.py` 后打开浏览器访问 localhost:8899

## 特色

- 三档解读粒度：简略 / 标准 / 详细
- 通俗模式：用大白话解释
- 整体解读：一键分析全部内容
- 暗色主题，护眼舒适
