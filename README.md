# 行测刷题

本地 / GitHub Pages 刷题工具：按模块练习、即时解析、错题本、技巧库，以及北森冲刺包。

## 本地使用

```bash
export PATH="$HOME/.local/node/bin:$PATH"
cd "/Users/gesu/行测"
npm install
npm run import   # 从桌面资料重新导入题库（可选）
npm run dev
```

打开终端提示的地址（通常 http://localhost:5173 ）。

## 发布到 GitHub Pages

仓库名建议：`xingce-practice`  
上线后地址形如：

`https://<你的GitHub用户名>.github.io/xingce-practice/`

推送到 `main` 后，GitHub Actions 会自动构建并发布。  
首次需要在仓库 **Settings → Pages → Source** 选 **GitHub Actions**。

## 题库来源

资料目录：`/Users/gesu/Desktop/26秋招/行测题目`

- 普通练习：北森解析版 + 30 天计划 + Word 精选
- 冲刺抱佛脚：仅北森解析版

导入结果在 `public/data/`，配图在 `public/images/`。
