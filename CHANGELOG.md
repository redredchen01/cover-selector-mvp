# Changelog

All notable changes to Cover Selector project will be documented in this file.

## [0.2.0] - 2026-04-15 (Current Release)

### 🎉 Major Features

#### Unit 1: Enhanced Face Detection
- **MediaPipe Integration**: Real-time face detection with 468-point landmark extraction
- **Graceful Fallback**: Heuristic-based face detection using OpenCV when MediaPipe unavailable
- **Improved Schema**: New fields for face detection:
  - `face_confidence` (0-1): Detection confidence score
  - `face_center_x/y` (0-1): Normalized face center coordinates
  - `face_size_ratio` (0-1): Face size as proportion of image
  - `face_landmarks_json`: 468-point landmark coordinates in JSON format

#### Unit 2: Parallel Feature Extraction & Frame-Level Caching
- **Frame-Level Caching**: MD5-based content hashing for intelligent cache invalidation
- **Config-Hash Based Invalidation**: Automatic cache invalidation on configuration changes
- **Parallel Feature Extraction**: ThreadPoolExecutor-based parallel processing for all feature analyzers
- **FrameCache Implementation**: Persistent JSON-based cache with corruption detection
- **Cache Statistics**: Hit rate tracking and performance monitoring

#### Unit 3: Web UI Enhancement
- **Session Management**: UUID-based session tracking with persistent history
- **Real-time Progress Tracking**: WebSocket-like polling via `/api/progress/{session_id}`
- **Background Processing**: Non-blocking HTTP responses with background thread execution
- **Session History**: `/api/history` endpoint for past upload tracking
- **File-based History**: Persistent JSON history storage in `~/.cover_selector_history/`

#### Unit 4: Test Coverage Expansion
- **Comprehensive Integration Tests**: 9 new end-to-end tests covering:
  - Frame sampling pipeline validation
  - Cache hit tracking and statistics
  - Feature extraction robustness with multiple scenarios
  - Schema validation and type enforcement
  - Parallel pipeline initialization
  - Cache invalidation on config changes
  - Concurrent session management
  - Error handling with graceful degradation
- **Video Generation**: ffmpeg-based test video creation with fallback to OpenCV

#### Unit 5: Docker & Multi-Cloud Deployment
- **Multi-stage Dockerfile**: Optimized for size and security
  - Builder stage: Compile dependencies via wheels
  - Runtime stage: Minimal runtime with system libraries
  - Non-root user execution (UID 1000)
  - Health check integration
- **Docker Compose**: Local development environment with volume mapping
- **Cloud Deployment Guides**:
  - AWS ECS/ECR with CloudWatch monitoring
  - Google Cloud Run with Artifact Registry
  - Azure Container Instances with Container Registry
- **Makefile**: Developer-friendly Docker commands
- **.dockerignore**: Optimized build context

### 🐛 Bug Fixes

- Fixed MediaPipe import compatibility issues with v0.10.33+
- Fixed frame cache creation and persistence
- Fixed session manager module initialization
- Fixed integration test video generation (ffmpeg fallback)
- Fixed duplicate field definitions in FrameFeatures schema

### 🔧 Technical Improvements

#### Performance
- **Parallel Processing**: ThreadPoolExecutor with configurable workers (default: 4)
- **Frame Caching**: 77%+ code coverage with intelligent invalidation
- **Memory Optimization**: Explicit garbage collection between pipeline stages
- **Session-aware Processing**: Background threads with progress tracking

#### Code Quality
- **Code Formatting**: 33 files reformatted with black (line-length: 100)
- **Import Sorting**: isort applied across entire codebase
- **Type Coverage**: 80%+ test coverage on core modules
- **Error Handling**: Graceful degradation with proper exception logging

### 📦 Dependencies

#### Added
- `ffmpeg` (system dependency) - Video processing
- `tesseract-ocr` (system dependency) - OCR functionality

### 🚀 Deployment

#### Docker Support
- Multi-stage build optimized for production
- Non-root user security
- Automatic health checks
- Kubernetes-ready specification

### 📊 Testing

#### Test Results
- **Total Tests**: 29 passing (core modules)
- **Coverage**: 32% overall (core modules 70-100%)

### 📝 Documentation

#### New Guides
- **DOCKER_DEPLOYMENT.md**: Comprehensive cloud deployment guide
- **Makefile**: Developer command reference

### 🔐 Security

- Non-root Docker user execution
- Image scanning support
- Secrets management guidance
- TLS/SSL support for production

---

## [0.1.0] - Previous Release

### Features
- Scene detection using PySceneDetect
- Frame sampling with multiple strategies
- Feature analysis (blur, brightness, OCR, composition)
- Rule-based frame ranking and selection
- Triple-collage composition
- Web UI for video upload
- CLI for batch processing

---

**Last Updated**: 2026-04-15  
**Version**: 0.2.0
