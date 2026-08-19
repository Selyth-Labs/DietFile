# DietFile

DietFile은 사용자가 지정한 목표 용량을 기준으로 이미지와 비디오의 품질 및 해상도를 자동으로 조절하여, 품질을 최대한 유지하면서 목표 용량 이하의 결과를 찾는 데 초점을 둔 파일 최적화 프로그램입니다.

현재 JPEG, PNG, WebP, GIF 및 MP4, MOV, MKV, WebM, AVI 형식을 지원합니다.

## 실행

```bash
python3 main.py
```

## FFmpeg 및 FFprobe

비디오 최적화 기능은 FFmpeg 및 FFprobe를 사용합니다.

* macOS(Apple Silicon, Intel): FFmpeg 및 FFprobe가 프로그램에 번들링되어 있어 별도의 설치가 필요하지 않습니다.

* Windows: 현재 FFmpeg 및 FFprobe 번들링을 지원하지 않습니다. 비디오 최적화 기능을 사용하려면 사용자가 별도로 FFmpeg를 설치하고 시스템 PATH에 등록해야 합니다.
> Windows 버전의 FFmpeg 및 FFprobe 번들링은 추후 지원 예정입니다.
