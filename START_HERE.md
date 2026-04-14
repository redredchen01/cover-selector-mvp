# 🎬 快速开始指南

## ✅ 服务已启动

**🌐 访问：http://localhost:8000**

---

## 📝 测试步骤

### 1. 打开浏览器
```
http://localhost:8000
```

### 2. 选择测试模式

**方式 A：使用预设演示数据（推荐）**
- 页面自动加载示例 JSON
- 直接点击 **🚀 运行 Compose** 按钮

**方式 B：上传自己的 JSON**
- 粘贴或上传 `ranking_results.json` 文件
- 点击 **🚀 运行 Compose**

### 3. 查看结果
- **Mode** — triple 或 degraded
- **Bottom Frame** — 选中的底部图像（帧 ID + 清晰度）
- **Zoom Frames** — 选中的两个缩放图像
- **完整报告** — JSON 格式的详细信息

---

## 🧪 测试数据格式

```json
{
  "total_frames_analyzed": 300,
  "candidates": [
    {
      "frame_id": 0,
      "final_score": 82.5,
      "confidence_score": 85.0,
      "status": "normal",
      "violation_reasons": [],
      "score_breakdown": {}
    },
    {
      "frame_id": 100,
      "final_score": 88.0,
      "confidence_score": 90.0,
      "status": "normal",
      "violation_reasons": [],
      "score_breakdown": {}
    },
    {
      "frame_id": 200,
      "final_score": 85.5,
      "confidence_score": 88.0,
      "status": "normal",
      "violation_reasons": [],
      "score_breakdown": {}
    }
  ]
}
```

**必需字段：**
- `frame_id` — 帧编号 (int)
- `final_score` — 评分 (0-100)
- `confidence_score` — 置信度 (0-100)
- `status` — 状态 (normal/duplicate/rejected)

---

## 🎯 预期结果示例

### Triple Mode（三拼图）✨

```
✅ 结果

Mode: triple
Bottom Frame: 100 (Clarity: 88.0)
Zoom Frames: Frame 0, Frame 200
Total Candidates: 3
```

选择逻辑：
- 底部图：最高清晰度的候选帧（偏好横屏格式）
- 缩放图：根据清晰度、人脸存在、时间多样性加权选择

### Degraded Mode（降级模式）⚠️

```
⚠️ 当候选帧 < 3 时：

Mode: single
Bottom Frame: 100 (Clarity: 88.0)
Zoom Frames: (无)
```

---

## 🔧 高级配置

修改 `src/cover_selector/configs/default.yaml`：

```yaml
composition:
  # 底部图像选择
  bottom_image:
    min_blur_score: 60.0          # 最低清晰度要求
    min_width_aspect_ratio: 1.5   # 最小宽高比
    max_face_ratio: 0.3           # 最大人脸比例

  # 缩放图像选择
  zoom_images:
    min_blur_score: 50.0
    min_temporal_separation_absolute: 5.0  # 最小时间间隔（秒）
    weights:
      blur_weight: 0.4            # 清晰度权重
      has_face_weight: 0.3        # 人脸权重
      diversity_weight: 0.3       # 多样性权重

  # 布局
  layout:
    output_width: 1920
    output_height: 1080
    zoom_size: 360
    scaling_mode: letterbox       # 或 crop
```

---

## 💻 CLI 使用（本地测试后）

### 完整工作流

```bash
python -m cover_selector.cli.main \
  --input video.mp4 \
  --output ./results
```

### 仅 Compose 子命令

```bash
python -m cover_selector.cli.main compose ranking_results.json --output-dir ./output
```

---

## 🐛 故障排查

| 问题 | 解决方案 |
|------|---------|
| 无法连接到 localhost:8000 | 检查服务是否正在运行：`ps aux \| grep python` |
| JSON 解析错误 | 验证 JSON 格式，使用 `jsonlint` 或在线工具 |
| 候选帧不足 | 需要至少 3 个候选帧用于 triple 模式 |
| 清晰度评分过高 | 检查 `blur_score` ≤ 100 |

---

## 📊 测试场景

### 场景 1：完美情况（3 个高质量帧）
```json
"candidates": [
  {"frame_id": 0, "final_score": 85, ...},
  {"frame_id": 100, "final_score": 90, ...},
  {"frame_id": 200, "final_score": 87, ...}
]
```
**预期：** triple mode，选择 frame 100 作为底部

### 场景 2：降级情况（只有 2 个帧）
```json
"candidates": [
  {"frame_id": 50, "final_score": 80, ...},
  {"frame_id": 150, "final_score": 85, ...}
]
```
**预期：** degraded mode，single_image 输出

### 场景 3：时间间隔测试
验证两个缩放帧之间的时间分隔是否满足配置要求

---

## 📈 性能注意事项

- **Web UI：** 实时处理，< 100ms
- **CLI：** 视频长度依赖
  - 场景检测：O(video_length)
  - 帧采样 & 评分：O(candidates)
  - 三拼图选择：O(1)

---

## ✅ 完成清单

- [ ] 打开 http://localhost:8000
- [ ] 使用演示数据运行一次 compose
- [ ] 修改参数并观察结果变化
- [ ] 上传自己的 ranking JSON（如有）
- [ ] 验证 triple/degraded 两种模式
- [ ] 检查生成的报告格式

---

## 📞 API 端点

### POST /api/compose

**请求：**
```json
{
  "total_frames_analyzed": 300,
  "candidates": [...]
}
```

**响应：**
```json
{
  "status": "success",
  "report": {
    "mode": "triple",
    "bottom_image": {...},
    "zoom_images": [...],
    "summary": {...}
  }
}
```

---

**准备好了吗？** 🚀

👉 访问 **http://localhost:8000** 开始测试！
