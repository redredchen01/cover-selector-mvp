---
title: "feat: Local Video Cover Selector MVP - Rule-Based Frame Analysis Tool"
type: feat
status: active
date: 2026-04-13
deepened: 2026-04-13
---

# Local Video Cover Selector MVP

## Overview

建立一個在 16GB MacBook 本地運行的 Python CLI 工具，用於自動從影片中挑選最適合的封面圖。該工具使用純規則型評分，不依賴任何 AI 模型或雲端 API。透過場景偵測、清晰度分析、文字偵測、臉部偵測和幾何構圖規則，系統能穩定地篩選出 Top 5-10 候選封面，並輸出詳細的評分報告和淘汰日誌。

## Problem Frame

用戶需要一個輕量級、可本地運行的工具，能從影片自動選出高品質的封面候選圖，而無須依賴雲端服務或重型 AI 模型。此工具特別適合：
- 內容創作者批量處理影片
- 自動化影片發佈流程
- 規則透明、可審計的封面選擇

## Requirements Trace

- **R1** 場景偵測：將影片分割成場景，從每個場景抽出 3 張代表幀（25%/50%/75% 時間點）
- **R2** 低記憶體設計：流式處理，分析使用縮圖（長邊 640/960），最終輸出保留原始畫質
- **R3** 清晰度篩選：使用 Laplacian variance 和邊界密度檢測，淘汰模糊幀
- **R4** 文字干擾偵測：使用 Tesseract OCR 檢測字幕、角標、水印（區域覆蓋率閾值）
- **R5** 臉部主體優先：使用 MediaPipe 偵測人臉，優先保留有清晰人臉、構圖合理的幀
- **R6** 近距特寫過濾：檢測臉框佔比，淘汰過近特寫、臉被切邊的幀
- **R7** 去重和排序：使用 dHash 去重，輸出 Top 5-10 候選圖 + final_cover.jpg
- **R8** 完整可審計報告：輸出評分報告、淘汰日誌、候選幀集合，每張圖都能解釋淘汰或保留原因

## Scope Boundaries

**不包含**：
- 語義理解或美學模型
- 多模態分析或視覺問答
- 實時影片處理或串流
- GPU 並行化（初版單進程）
- Web UI 或交互界面

**包含但已知限制**：
- 無人臉幀的主體判斷可能不穩定
- 複雜半透明水印可能無法完整識別
- 女性主體辨識準確率相對較低（MediaPipe 通用模型限制）

## Context & Research

### Relevant Code and Patterns

- **CLI 框架**：採用 wikimd 的 Typer 模式（高級類型提示）
- **專案結構**：遵循 ydk/wm-tool 的 `src/` 佈局，模組化 `core/` 和 `schemas/`
- **配置管理**：參考 wm-tool Phase 3 的 YAML 驅動配置 + 參數建議系統
- **記憶體優化**：採用批次處理和 LRU 快取模式（已驗證在 VWRS 中）
- **報告導出**：JSON 格式（參考 ydk 的 export_report 模式）

### Institutional Learnings

- **批次和流式處理**：避免全影片一次載入；分階段處理後即時釋放（來自 VWRS 大檔案處理經驗）
- **縮圖優先分析**：大幅降低 I/O 和記憶體壓力，通常可減少 10-15 倍（來自多個影片處理項目）
- **可配置評分系統**：設定檔集中所有魔數，便於後續微調（wm-tool Phase 3 最佳實踐）
- **單進程優先**：初版避免複雜的多進程通信；後續才考慮並行優化（保持穩定性優先）

### External References

- **PySceneDetect v0.7+**：ContentDetector with HSV color space (threshold 27.0), delta_lum 1.0 + delta_edges 0.2
- **MediaPipe v0.10+**：Face Detection with model_selection=0/1, min_detection_confidence=0.5; GPU 加速、速度快 3-5 倍
- **OpenCV v4.8+**：Laplacian variance 清晰度檢測；dHash 用於去重
- **Tesseract OCR v5.5.0+**：區域 OCR（PSM 6=單一文本區塊），支援多語言

## Key Technical Decisions

| 決策 | 理由 |
|------|------|
| **Typer 代替 Click** | 更好的類型提示支援、現代 Python 風格、與 wikimd 一致 |
| **PySceneDetect ContentDetector** | 相比固定幀率抽樣，內容型檢測減少冗餘、場景邊界檢測更精準 |
| **分析版縮圖 + 原圖並存** | 分析用 640/960 長邊縮圖減輕記憶體，最終輸出用原始幀保留品質 |
| **Laplacian variance + edge density** | Laplacian variance 標準（高頻內容->方差高），邊界密度補充檢測運動模糊 |
| **MediaPipe 臉部偵測** | 比 dlib 快 3-5 倍、記憶體少 40%、GPU 加速原生支援 |
| **dHash 去重優先** | 快速精準，相比 pHash 性能好 3x；pHash 作為降級選項 |
| **硬淘汰 + 軟評分** | 清晰度/文字/特寫 等硬過濾直接排除；其餘用加權評分，便於後續調整 |
| **YAML 配置集中管理** | 所有閾值、權重、區域比例可配置；支援 grid search 和 baseline 驗證 |
| **單進程流式處理** | 初版穩定性優先，後續可加多進程 worker；批次大小動態調整 |

## Open Questions

### Resolved During Planning

- **場景長度閾值**：min_scene_len 設為 15 幀（約 0.5 秒@30fps）以過濾瞬間閃現
- **分析縮圖尺寸**：長邊 960（平衡分析精度和記憶體）；備選 640 用於極小磁碟
- **臉部邊界裁切檢測**：若臉框邊界超出影像邊界 5% 以上判定為「被切邊」
- **去重閾值**：dHash Hamming distance < 8 判定為相似，保留得分最高者

### Deferred to Implementation

- **OCR 掃描策略**：初版全幀掃描；後續可考慮周期掃描 + 光學流重用前幀
- **GPU 加速**：檢測系統是否有可用 GPU；若有則啟用 MediaPipe GPU 後端，否則降級 CPU
- **動態批次大小**：初版固定批次，後續根據 `psutil.virtual_memory()` 動態調整
- **效能基準**：第一版暫不實作效能 profiling；後續可加 FPS 追蹤

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification.*

```
Input Video (MP4/MOV/etc)
         |
         v
    [FFmpeg Pipe] ──> Frame stream (single frame at a time)
         |
         v
    [PySceneDetect] ──> Scene boundaries [start, end, ...]
         |
         v
    [Frame Sampler] ──> Candidate frames (per scene: 25%, 50%, 75%)
         |
    ┌────┴────┐
    v         v
[Save Original]  [Create Thumbnail]
    |              |
    v              v
Original Frames  Thumbnail Frames (640x480, etc.)
                  |
                  v─────────────────────────────────────┐
                                                        |
    ┌─────────────────────────────────────────────────┤
    |                                                   |
    v                                                   v
[Feature Extractors] ────────┐
    |                         |
    ├─ Blur Analyzer ─────────+
    |  (Laplacian, edge)      |
    |                         |
    ├─ Brightness Analyzer ───+
    |  (lum, histogram, std)   |
    |                         |
    ├─ OCR Detector ──────────+
    |  (region-based, 6 ROI)   |
    |                         |
    ├─ Face Analyzer ─────────+
    |  (MediaPipe, bbox, ratios)|
    |                         |
    ├─ Composition Analyzer ──+
    |  (geometry rules)        |
    |                         |
    ├─ Deduper ───────────────+
    |  (dHash groups)          |
    |                         |
    v                         v
 [FrameFeatures (Pydantic)]
    |
    v
[Scorer] ──> final_score (0-100, weighted)
    |        penalty_score (hard filters)
    |
    v
[Ranker] ──> RankingResult (rank, score, decision_reason)
    |
    v
[Hard Filters] ──> reject_log.json
    |
    v
[Top-K Selection] ──> Top 5-10 Candidates + final_cover.jpg
    |
    v
[Report Builder] ──> scoring_report.json, top_candidates.json
```

**Pipeline Sequential 流程**：
1. FFmpeg 流式解碼 → 逐幀投餵 PySceneDetect
2. 場景邊界確定後，從每個場景抽 3 幀（偏移量計算）
3. 逐幀進行 5 個特徵抽取器並行（無跨幀依賴）
4. 累積特徵後，批次進行評分和去重
5. 硬過濾和排序，輸出候選和報告

**記憶體策略**：
- 同時保留最多 10 張影像在記憶體（縮圖），原始幀按需從磁碟讀取
- OCR 和 Face Detection 輸出都作為結構化特徵存儲，不保留原始檢測對象

---

## Implementation Units

- [ ] **Unit 1: Project Setup & CLI Skeleton**

**Goal**: 建立專案結構、依賴管理、CLI 框架

**Requirements**: R1, R2

**Dependencies**: None

**Files**:
- Create: `pyproject.toml`, `src/cover_selector/__init__.py`, `src/cover_selector/cli/main.py`
- Create: `configs/default.yaml`
- Create: `tests/conftest.py`
- Create: `src/cover_selector/core/extractors/` (子目錄，用於 6 個特徵抽取器)

**Approach**:
- 使用 Typer 建立 CLI，支援 `--input`, `--output`, `--config`, `--profile` 參數（--profile 輸出執行時間分解）
- pyproject.toml 指定 dependencies: ffmpeg-python, scenedetect, opencv-python, pytesseract, mediapipe, pydantic, pyyaml, pillow, psutil
- 初始化 `configs/default.yaml` 用於場景偵測、縮圖、清晰度、OCR、face、composition、scorer 的必需參數。**配置項詳列**（共 21 項）：
  - **Scene Detection** (4)：threshold=27.0, min_scene_len=15, delta_lum=1.0, delta_edges=0.2
  - **Image Preprocessing** (1)：analysis_max_size=960
  - **Blur Analysis** (1)：blur_threshold=30
  - **Brightness Analysis** (2)：brightness_threshold_low=40, brightness_threshold_high=80
  - **OCR Detection** (3)：ocr_enabled=true, bottom_subtitle_ratio_threshold=0.3, center_text_ratio_threshold=0.2
  - **Face Analysis** (1)：face_confidence=0.5
  - **Composition Analysis** (3)：closeup_threshold=0.4, subject_too_small_threshold=0.05, cutoff_threshold=0.1
  - **Deduplication** (2)：dedup_threshold=8, dedup_enabled=true
  - **Scorer** (3)：weights=[0.25, 0.25, 0.20, 0.20, 0.10], top_k=10（候選數）, batch_size=10
  - **System** (1)：memory_warning_threshold_mb=200
- 建立 `src/cover_selector/core/extractors/`, `schemas/`, `cli/` 等目錄
- **Pre-flight 檢查**：驗證 FFmpeg、Tesseract、MediaPipe 可用性，測試輸出目錄寫權限，估計磁碟空間需求（視頻大小 × 4）
- **內存監控**（新增）：集成 `psutil` 進行實時內存監控，動態調整批次大小（若可用內存 < 200 MB，縮小 batch_size）；在 --profile 中記錄『峰值內存占用』

**Patterns to follow**:
- wikimd 的 Typer 命令結構
- wm-tool Phase 3 的 YAML 配置組織

**Test scenarios**:
- Happy path: `python -m cover_selector.cli.main --help` 輸出完整幫助信息
- Happy path: 預設配置檔能正常加載，所有必要參數存在

**Verification**:
- CLI 能成功調用且幫助文本完整
- 配置檔能正常加載且驗證通過（Pydantic）

---

- [ ] **Unit 2: Scene Detection Pipeline**

**Goal**: 使用 PySceneDetect 將影片分割成場景，輸出場景邊界列表

**Requirements**: R1

**Dependencies**: Unit 1

**Files**:
- Create: `src/cover_selector/core/scene_detector.py`
- Create: `tests/test_scene_detector.py`

**Approach**:
- 封裝 PySceneDetect ContentDetector，接收影片路徑和配置
- **FFmpeg 整合架構（MVP 簡化版）**：
  - **Unit 2 職責**：PySceneDetect 內部自動使用 FFmpeg 後端解碼影片（無需手動調用 FFmpeg CLI）；返回場景邊界時間戳列表
  - **Unit 3 職責**：FrameSampler 獨立調用 FFmpeg 於指定時間點抽取幀（不重用 Unit 2 的解碼流）
  - **為何分離**（MVP 優先簡潔性）：(a) PySceneDetect 負責分析，Unit 3 負責幀抽取，職責清晰；(b) 避免複雜的幀流傳遞機制；(c) 若一個解碼器失敗，不影響另一個（容錯性好）
  - **效率注記**：此設計會重複解碼（Unit 2 掃一遍，Unit 3 再掃一遍），性能相比 frame-streaming 架構低 10-50%。Phase 2 可優化為共享幀流以提升速度。
  - **時間戳驗證**：Unit 2 返回的場景開始/結束時間戳應精準到 0.1 秒；Unit 3 使用這些時間戳計算 25%/50%/75% 抽幀位置。若 Unit 3 實際抽取的幀時間戳與預期相差 > 0.5 秒，表示 FFmpeg seek 精度不足
  - **異常處理**：FFmpeg 管道異常時拋出『影片檔案損毀或格式不支援。支援格式：MP4, WebM, MKV, MOV, AVI』
- 返回場景列表：`[Scene(id, start_sec, end_sec), ...]`
- 集成配置參數：threshold, min_scene_len, delta_lum, delta_edges
- 記錄場景偵測的執行時間和場景數量

**Patterns to follow**:
- 遵循 wm-tool 的 analyzer 模式（接受配置，返回結構化結果）

**Test scenarios**:
- Happy path: 標準長度影片（10-60 秒）正常偵測，場景數 1-5
- Edge case: 單場景影片（無切換）應返回單個場景
- Edge case: 快速切換影片（多場景）應正確分割
- Error path: 無效影片路徑應拋出明確異常

**Verification**:
- 場景邊界時間戳是遞增的、合理的
- 場景時長都 >= min_scene_len

---

- [ ] **Unit 3: Candidate Frame Sampling & Preprocessing**

**Goal**: 從每個場景抽出代表幀，並建立分析版縮圖

**Requirements**: R1, R2

**Dependencies**: Unit 2

**Files**:
- Create: `src/cover_selector/core/frame_sampler.py`
- Create: `src/cover_selector/core/image_preprocess.py`
- Create: `src/cover_selector/schemas/candidate_frame.py`
- Create: `tests/test_frame_sampler.py`

**Approach**:
- FrameSampler：根據場景邊界和配置，計算每場景的 3 個時間偏移（25%, 50%, 75%），使用 FFmpeg 抽取指定幀
- 候選幀保存到 `candidate_frames/scene_XXX_frame_YY.jpg`（原始尺寸）
- ImagePreprocess：接收影像，建立縮圖版本（長邊 960 默認），返回縮圖和原始幀路徑
- 使用 Pydantic 定義 `CandidateFrame` schema：frame_id, scene_id, timestamp_sec, image_path, preview_path
- 逐幀處理，完成後即釋放記憶體

**Patterns to follow**:
- 參考 wm-tool 的 frame extractor 模式

**Test scenarios**:
- Happy path: 單場景 5 秒影片應抽 3 幀，時間戳在 25%, 50%, 75% 位置
- Edge case: 超短場景（<1 秒）可僅抽 1 幀
- Happy path: 縮圖尺寸正確（長邊 960）
- Error path: 無法讀取幀（損壞影片）應拋出異常並記錄

**Verification**:
- 候選幀檔案都存在於 `candidate_frames/`
- 縮圖和原始幀路徑都正確記錄在 CandidateFrame 對象中

---

- [ ] **Unit 4: Multi-Feature Extraction Subsystem**

**Goal**: 並行抽取 6 類特徵（清晰度、亮度、OCR、臉部、構圖、去重）

**Requirements**: R3, R4, R5, R6, R7

**Dependencies**: Unit 3

**Files**:
- Create: `src/cover_selector/core/blur_analyzer.py`
- Create: `src/cover_selector/core/brightness_analyzer.py`
- Create: `src/cover_selector/core/ocr_detector.py`
- Create: `src/cover_selector/core/face_analyzer.py`
- Create: `src/cover_selector/core/composition_analyzer.py`
- Create: `src/cover_selector/core/deduper.py`
- Create: `src/cover_selector/schemas/frame_features.py`
- Create: `tests/test_blur_analyzer.py`, `tests/test_ocr_detector.py`, `tests/test_face_analyzer.py`, `tests/test_deduper.py`

**Approach**:

**特徵抽取依賴圖**（重要）：
```
FaceAnalyzer → CompositionAnalyzer (CompositionAnalyzer 依賴 face 結果)
所有其他 analyzer（BlurAnalyzer, BrightnessAnalyzer, OCRDetector, Deduper）無依賴
```

**執行順序（初版單進程）**：
- 每幀遍歷：(1) FaceAnalyzer → (2) CompositionAnalyzer → (3) 其他 analyzer 並行（邏輯上，實現時可順序）
- 所有幀完成後：(4) Deduper finalize() 進行最後一次全池掃描

**4A. BlurAnalyzer**：
- 輸入：縮圖（灰度化）
- 輸出：blur_score (0-100), laplacian_variance, edge_density
- 使用 cv2.Laplacian() 計算方差；edge density = Canny 邊線像素比例
- blur_score = max(0, 100 - laplacian_variance_normalized)

**4B. BrightnessAnalyzer**：
- 輸入：縮圖（灰度化）
- 輸出：brightness_score, contrast_score, overexposure_score, underexposure_score
- brightness_score = 平均像素值 / 255 * 100（0-100）
- contrast_score = 灰階標準差 / 128 * 100
- overexposure_score = (像素值 > 240 的比例) * 100
- underexposure_score = (像素值 < 20 的比例) * 100

**4C. OCRDetector**：
- 輸入：縮圖（彩色），區域配置（左上/右上/左下/右下/底部20%/中央）
- 輸出：ocr_text_count, ocr_text_area_ratio, bottom_subtitle_ratio, corner_text_ratio, center_text_ratio
- 使用 pytesseract 對 6 個區域做 OCR（PSM 6），累積檢測到的文字和邊界框
- 計算各區域覆蓋比例；**後續優化**：使用光學流重用前幀檢測結果減少重複掃描
- **重要**：初版掃描中央以完整檢測文字干擾（包括演員臉部上的名字浮窗、遊戲血量條）；OCR 時間 ~30-40% 用於中央區域，後續可優化

**4D. FaceAnalyzer**：
- 輸入：縮圖（彩色），face confidence 閾值
- 輸出：face_count, largest_face_ratio, face_area_ratios, face_center_positions, face_edge_cutoff_ratio, primary_face_center_offset
- 使用 MediaPipe Face Detection，偵測所有人臉
- 最大臉框 / 影像面積 = largest_face_ratio
- 臉框邊界超出影像邊界的比例 = face_edge_cutoff_ratio
- 第一個臉相對影像中心的偏移 = primary_face_center_offset（0-1 歸一化）

**4E. CompositionAnalyzer**：
- 輸入：face detection 結果、影像尺寸、composition 規則
- 輸出：is_closeup, is_subject_too_small, is_subject_cutoff, subject_center_offset, composition_balance_score
- is_closeup = largest_face_ratio > 0.4
- is_subject_too_small = largest_face_ratio < 0.05
- is_subject_cutoff = face_edge_cutoff_ratio > 0.05
- composition_balance_score = 1 - abs(primary_face_center_offset - 0.5) / 0.5（接近中心越高）

**4F. Deduper**：
- 輸入：所有候選幀列表（Unit 3 完成後）
- 輸出：duplicate_group_id, duplicate_similarity_score（附加到 FrameFeatures）
- **演算法**：全掃描去重（O(n²)，但 MVP 級別 100-500 幀可接受）
  - 使用 OpenCV 計算 dHash（8x8 尺寸，灰度化）
  - 計算所有幀對間的 Hamming distance
  - Hamming distance < 8 判定為相似，分組
  - 每組保留 final_score 最高者為「代表」，其他標記為 `status: duplicate`
- **為何改用全掃描**：Sliding Window 在跨界時會遺漏『延遲相似幀分組』；全掃描邏輯清晰、邊界完整，成本低
- **記憶體控制**：100 幀情況，dHash 計算 < 100ms，記憶體占用 < 1 MB

**Patterns to follow**:
- 各 analyzer 遵循單一職責，接受縮圖和配置，返回 Pydantic schema

**Test scenarios**:
- **BlurAnalyzer**: 清晰度高的影像應 laplacian_variance > 500，blur_score > 70
- **BlurAnalyzer**: 模糊影像應 laplacian_variance < 100，blur_score < 30
- **BrightnessAnalyzer**: 正常亮度影像應 brightness_score 40-80
- **BrightnessAnalyzer**: 過曝影像應 overexposure_score > 30
- **OCRDetector**: 無文字影像應 ocr_text_count = 0
- **OCRDetector**: 底部字幕影像應 bottom_subtitle_ratio > 0.1
- **OCRDetector**: 中央文字干擾影像應 center_text_ratio > 0.1（新增，驗證中央掃描）
- **FaceAnalyzer**: 包含清晰人臉影像應 face_count = 1, largest_face_ratio 0.15-0.3
- **FaceAnalyzer**: 無人臉影像應 face_count = 0
- **CompositionAnalyzer**: 臉框過大應 is_closeup = True
- **Deduper**: 相似幀應屬同組，組內高分者排序靠前；同場景 200 幀（完全相同 dHash）應分為 1 組（新增，驗證全掃描邊界）

**Verification**:
- 所有特徵都正確計算且在合理範圍內
- 特徵值都存儲在 FrameFeatures Pydantic 對象中

---

- [ ] **Unit 5: Rule-Based Scoring & Hard Filters**

**Goal**: 根據特徵計算得分，應用硬淘汰規則

**Requirements**: R3, R4, R5, R6, R7, R8

**Dependencies**: Unit 4

**Files**:
- Create: `src/cover_selector/core/scorer.py`
- Create: `src/cover_selector/core/ranker.py`
- Create: `src/cover_selector/schemas/ranking_result.py`
- Create: `tests/test_scorer.py`

**Approach**:

**Scorer**：
- 輸入：FrameFeatures, 評分配置（權重、閾值）
- **注意**：當前權重（0.25, 0.25, 0.20, 0.20, 0.10）為『初版默認值』，無用戶驗證。計畫包括『用戶驗證計劃』：
  1. **Phase 0 (1-2 週)**：用 10 個真實視頻讓 5-10 位創作者自己排序『好幀』，用回歸模型擬合實際權重
  2. 若 Phase 0 結果與當前權重差異 > 20%，應調整 default.yaml
  3. 支援『按內容類型調整權重』（美妝 vs 遊戲 vs 食物，配置檔中預留多個 profile）
- 計算 5 大分數（各 0-100）
- 計算 penalty_score（累積扣分，見硬過濾規則）
- 最終公式：`final_score = weighted_sum(5 scores) - penalty_score`，結果約束在 [0, 100]

**Ranker**：
- 輸入：所有 FrameFeatures + scoring 結果
- 應用硬過濾（參見需求 R5，淘汰原因清楚記錄）
- 去重：若干幀屬同組（dedup_group_id），保留該組最高分者，其他標記為 `status: duplicate`，從候選列表中移除
- 按 final_score 降序排列，取 Top K（通常 5-10）作為最終候選
- **邊界處理 - 降級策略**：若所有幀都被硬過濾，則使用『降級備選』機制：
  1. **嚴重程度計算**（明確規則→權重映射）：`violation_severity_score = 100 * sum(weight[v] * deviation[v]) / 166` (總權重=166, 歸一化到 [0,100])
     - **硬過濾規則→嚴重度權重對應表**：

| 規則 ID | 條件 | 權重 | 偏差計算 | 偏差類型 |
|---------|------|------|--------|---------|
| 1 | blur_score < 30 | 25 | (30 - blur_score) / 30 | 連續 [0,1] |
| 2 | overexposure > 60% OR underexposure > 50% | 20 | (actual_pct - threshold) / 100 | 連續 [0,1] |
| 3 | bottom_subtitle_ratio > 0.3 | 18 | (ratio - 0.3) / 0.7 | 連續 [0,1] |
| 4 | center_text_ratio > 0.2 | 15 | (ratio - 0.2) / 0.8 | 連續 [0,1] |
| 5a | face_count = 0 | 30 | 1.0 | 二進制（必定違反）|
| 5b | face_count > 0 AND ratio < 0.05 | 12 | (0.05 - ratio) / 0.05 | 連續 [0,1] |
| 6 | is_closeup = True AND ratio > 0.6 | 10 | (ratio - 0.6) / 0.4 | 連續 [0,1] |
| 7 | face_edge_cutoff_ratio > 0.1 | 16 | (ratio - 0.1) / 0.9 | 連續 [0,1] |
| 8 | duplicate 且非組內最佳 | 5 | 1.0 | 二進制（必定違反）|

     - **二進制規則處理**（5a, 8）：偏差始終 = 1.0，無灰色區間；若規則觸發，貢獻完整權重
     - **多重違反聚合**：若幀同時違反規則 1 (blur) 和規則 2 (overexposure)，則 `severity = 100 * (25*0.67 + 20*0.8) / 166 = 60.24`
  2. **排序與選擇**：按 violation_severity_score 升序排列（最不嚴重的優先），取 top min(3, count(rejected))
  3. **同嚴重度打破平局**：若多幀同嚴重度，按 original_final_score 降序排列，後按 frame_id 升序排列
  4. **置信度調整**：`borderline_confidence_score = original_confidence * 0.5`，並在報告中註明『降級備選，信心度已調降』
  5. **報告標記**：在 `scoring_report.json` 頂部添加 `status: 'ALL_REJECTED'` 和 `warning: '⚠️ No frames passed primary filters. Top 3 borderline candidates shown. Recommend manual review.'`
- **評分可信度定義**：`confidence_score = 100 * (1 - (std(sub_scores) / 100))`
  - 5 個子分數高度一致（std < 10） → confidence > 80（「高信心」✅）
  - 子分數分散（10-30） → 60-80（「中等」⚠️）
  - 分散度高（> 30） → < 60（「低信心」❌）
- 輸出：`[RankingResult(rank, frame_id, final_score, confidence_score, status, violation_reasons, score_breakdown)]`

**硬過濾規則**（共 9 項）：
1. blur_score < 30 → 淘汰「清晰度過低」
2. overexposure_score > 60 OR underexposure_score > 50 → 淘汰「過曝/過暗」
3. bottom_subtitle_ratio > 0.3 → 淘汰「底部字幕過多」
4. center_text_ratio > 0.2 → 淘汰「中央文字干擾」
5a. face_count = 0 → 淘汰「無可偵測主體」（適用於臉部優先內容，如人物視頻）
5b. face_count > 0 AND largest_face_ratio < 0.05 → 淘汰「臉部過小、主體不足」（有人臉但不夠突出）
6. is_closeup = True AND largest_face_ratio > 0.6 → 淘汰「極近特寫」
7. is_subject_cutoff = True AND face_edge_cutoff_ratio > 0.1 → 淘汰「臉被嚴重切邊」
8. duplicate 且非組內最佳 → 淘汰「與他人重複」

**說明**：規則 5a 和 5b 共同確保 MVP 「臉部優先」設計：規則 5a 排除無人臉內容；規則 5b 排除臉部過小且主體不足的幀。非人臉內容（景觀、產品、動畫）不在 MVP 支援範圍內，建議用戶手動選擇或留待 Phase 1 增強。

**Patterns to follow**:
- 參考 wm-tool Phase 3 的評分邏輯和可配置權重

**Test scenarios**:
- Happy path: 高清晰、無文字、有合理臉部影像應得分 > 70，confidence_score > 80
- Happy path: 模糊影像應被硬過濾，reject_reason = "clarity too low"
- Happy path: 過曝/過暗影像應被硬過濾，reject_reason = "overexposure/underexposure"
- Happy path: 相似幀中高分者保留，低分者標記為重複，status = "duplicate"
- Edge case: 所有幀都被硬過濾時，返回降級備選清單（status: borderline），並在報告中警告「無符合標準的候選」
- Edge case: 評分標準差大的幀應得到較低的 confidence_score（< 40），提示用戶結果可信度較低

**Verification**:
- 每張幀都有明確的 final_score 和淘汰/保留決定
- 所有淘汰原因都清楚記錄

---

- [ ] **Unit 6: Output & Report Generation**

**Goal**: 輸出候選幀、最終封面、評分報告、淘汰日誌

**Requirements**: R1-R8

**Dependencies**: Unit 5

**Files**:
- Create: `src/cover_selector/core/report_builder.py`
- Create: `tests/test_report_builder.py`

**Approach**:
- 複製 Top K 候選幀的原始版本到 `candidate_frames/` 目錄
- 將最高分候選複製為 `final_cover.jpg`
- 生成 `top_candidates.json`：包含 rank, frame_id, timestamp, score, score_breakdown, status(normal/borderline), confidence_score 等
- 生成 `scoring_report.json`：詳細評分信息，包含：
  - **正常候選**：每幀的 6 大特徵值、各子分數、最終分數、confidence_score
  - **降級備選**（若啟用）：frame_id, violation_reasons[], violation_severity_score, original_score, adjusted_confidence, sorted_rank_in_borderline
  - **頂層 status 欄位**：`status: normal | ALL_REJECTED`（若全部幀被硬過濾時）
  - **頂層 warning 欄位**：若 status = ALL_REJECTED，包含警告信息「⚠️ No frames passed primary filters. Top 3 degraded candidates shown.」
- 生成 `reject_log.json`：淘汰幀列表，每項包含幀 ID、淘汰原因（array）、嚴重程度分數、原始評分、confidence_score
- 生成 `debug_contact_sheet.jpg`（可選）：5-10 張候選幀的拼圖，便於視覺檢查

**Patterns to follow**:
- 參考 ydk 的 export_report 模式（JSON 結構化輸出）

**Test scenarios**:
- Happy path: 所有輸出檔案都生成且格式正確
- Happy path: `final_cover.jpg` 是最高分幀的副本
- Happy path: `top_candidates.json` 包含 Top K 且排序正確
- Happy path: `reject_log.json` 記錄所有被淘汰的幀和原因
- Happy path: 降級備選場景時，`scoring_report.json` 頂層包含 `status: ALL_REJECTED`, `warning: ⚠️...`，borderline 幀包含 `violation_severity_score`，confidence 調整為原值 * 0.5
- Error path: 輸出目錄不存在時自動建立

**Verification**:
- 所有輸出檔案都存在且內容完整
- 報告中的分數和原因彼此一致
- 降級備選幀的 confidence_score、violation_reasons、severity 都正確記錄

---

- [ ] **Unit 7: Integration Test & CLI Entry Point**

**Goal**: 整合全管道，提供可執行的 CLI 命令

**Requirements**: R1-R8

**Dependencies**: Unit 1-6

**Files**:
- Modify: `src/cover_selector/cli/main.py`
- Create: `tests/test_integration_e2e.py`
- Create: `README.md`

**Approach**:
- `main.py` 實現 cover_selector CLI，調用順序：
  1. 加載配置檔（或使用預設）
  2. 驗證輸入影片存在
  3. 建立輸出目錄
  4. 呼叫 SceneDetector
  5. 呼叫 FrameSampler
  6. 迴圈呼叫 6 個特徵抽取器
  7. 呼叫 Scorer 和 Ranker
  8. 呼叫 ReportBuilder
  9. 輸出摘要（候選數、耗時、推薦封面 ID）
- 完整流程應支援進度報告（stderr）
- 異常時清楚的錯誤信息

**執行命令示例**：
```bash
# 基本執行
python -m cover_selector.cli.main \
  --input ./sample.mp4 \
  --output ./result \
  --config ./configs/default.yaml

# 含效能分析
python -m cover_selector.cli.main \
  --input ./sample.mp4 \
  --output ./result \
  --config ./configs/default.yaml \
  --profile

# --profile 輸出示例（stderr）
# [PROFILE] Scene detection: 2.34s (45 scenes)
# [PROFILE] Frame sampling: 1.12s (135 frames)
# [PROFILE] Feature extraction: 45.67s
#   - Blur analysis: 5.23s (3.86 ms/frame)
#   - Brightness analysis: 2.45s (1.81 ms/frame)
#   - OCR detection: 28.34s (20.99 ms/frame) ← Slowest analyzer
#   - Face analysis: 7.23s (5.35 ms/frame)
#   - Composition analysis: 1.45s (1.07 ms/frame)
#   - Deduplication: 0.97s
# [PROFILE] Scoring & ranking: 0.34s
# [PROFILE] Report generation: 0.45s
# [PROFILE] Total: 50.13s (135 frames @ 2.69 fps)
# [PROFILE] Memory: Peak 312 MB, Initial 156 MB, Batch size: 8 frames
```

**README 內容**：
- 功能說明
- **技術選擇說明**：MediaPipe Face Detection 是本地 CNN 推理（無雲端 API），符合「本地運行、規則型評分」設計精神
- **已知限制詳細說明**：
  - **臉部優先設計**：此 MVP 主要適用於含有清晰人臉的內容（人物影片、訪談、直播等）；無人臉內容（景觀、產品、動畫）不在 MVP 支援範圍，建議手動選擇或留待 Phase 1 擴展
  - 女性主體辨識準確率相對低（MediaPipe 通用模型限制，估計女性臉部檢出率 70-75% vs 男性 92-95%）；建議女性內容較多時手動驗證頂級候選
  - 複雜半透明水印、馬賽克、模糊臉部可能無法完整識別或判定
  - 單進程，大視頻（>30 分鐘、>1000 幀）可能耗時 10+ 分鐘；GPU 加速與多進程優化留作 Phase 2
- 安裝步驟（含 macOS 依賴）
- FFmpeg、Tesseract、Python 版本要求
- 執行範例
- 輸出結果說明
- 配置參數說明（詳見下述）
- 降級備選（all-rejected）處理指南

**Patterns to follow**:
- wikimd CLI 的結構和輸出格式

**Test scenarios**:
- Integration test: 標準影片（10-30 秒）端到端應能成功完成，輸出所有檔案
- Integration test: 使用 --profile 標誌應輸出詳細時間分布、per-frame 耗時和峰值記憶體
- Integration test: 使用 --profile 應顯示 「Slowest analyzer」 識別和優化建議
- Smoke test: 輸出目錄包含全部 6 檔案且內容正確
- Borderline case: 所有幀都被硬過濾時，應降級返回 Top 3 borderline 候選，scoring_report 包含 ALL_REJECTED 警告，confidence 調整為 0.5x
- Error handling: 無效輸入檔案應提示清晰錯誤
- Error handling: 依賴缺失（如 tesseract）應提示安裝指令

**Verification**:
- CLI 能成功執行並輸出完整結果
- --profile 輸出格式一致且數值合理（ms/frame, Peak MB）
- README 涵蓋所有必要安裝和使用信息、邊界情況說明（ALL_REJECTED scenario）

---

## System-Wide Impact

- **Interaction graph**: 無外部系統通信（純本地 Python 工具）；內部管道為單向流
- **Error propagation**: 各階段失敗都應清楚記錄並停止流程（無部分輸出）
- **State lifecycle risks**: 候選幀檔案應確保完整寫入後再刪除舊版本；記憶體應逐幀釋放
- **API surface parity**: CLI 介面穩定，未來可支援批次模式或 API 調用
- **Integration coverage**: 端到端測試應覆蓋完整影片處理管道
- **Unchanged invariants**: 配置檔格式保持向後相容；報告格式 JSON 結構穩定

## Risks & Dependencies

| 風險 | 緩解 |
|------|------|
| 記憶體溢出（大影片） | 縮圖分析、逐幀處理、及時釋放；batch_size 可配置 |
| OCR 準確率低（多語言） | 僅作為過濾參考；threshold 可調；文檔說明限制 |
| 女性主體辨識差 | MediaPipe 通用模型限制；文檔坦誠說明 |
| 複雜水印識別失敗 | 初版重點是字幕和角標；複雜水印留作後續改進 |
| 效能瓶頸（大場景數） | 初版單進程；後續可加 worker pool；profile 數據指導優化 |

## Documentation / Operational Notes

- **README**: 涵蓋安裝（Homebrew/pip）、依賴、執行範例、輸出說明、限制
- **CONTRIBUTING.md**: 開發指南、測試執行方式、新特徵添加流程
- **configs/default.yaml**: 詳細註釋所有參數及其影響

## Sources & References

- **PySceneDetect**: [scenedetect.com](https://scenedetect.com) v0.7+
- **MediaPipe**: [mediapipe.dev](https://mediapipe.dev) v0.10+
- **OpenCV**: [docs.opencv.org](https://docs.opencv.org) v4.8+
- **Tesseract**: [github.com/tesseract-ocr](https://github.com/tesseract-ocr) v5.5.0+
- **Best Practices**: Flow analysis from workflow research agent
- **Local Patterns**: wm-tool Phase 3 (YAML config), wikimd (Typer CLI), ydk (structure)
