# DietFile

DietFile은 사용자가 지정한 목표 용량을 기준으로 이미지와 비디오의 품질 및 해상도를 자동으로 조절하여, 품질을 최대한 유지하면서 목표 용량 이하의 결과를 찾는 데 초점을 둔 파일 최적화 프로그램입니다.

현재 JPEG, PNG, WebP, GIF 및 MP4, MOV, MKV, WebM, AVI 형식을 지원합니다.

## 실행

```bash
python3 main.py
```

## FFmpeg 및 FFprobe

비디오 최적화 기능은 FFmpeg 및 FFprobe를 사용합니다.

macOS(Apple Silicon, Intel) 및 Windows(x64)용 실행 바이너리가 기본으로 번들링되어 있어, 별도의 FFmpeg 설치나 환경 변수 설정 없이 바로 사용할 수 있습니다.