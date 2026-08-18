# DietFile

DietFile은 사용자가 지정한 목표 용량을 기준으로 이미지와 비디오의 품질 및 해상도를 자동으로 조절하여, 품질을 최대한 유지하면서 목표 용량 이하의 결과를 찾는 데 초점을 둔 파일 최적화 프로그램입니다.

현재 JPEG, PNG, WebP, GIF 및 MP4, MOV, MKV, WebM, AVI 형식을 지원합니다.

## 실행

```bash
python3 main.py
````

## FFmpeg 설치

비디오 파일을 최적화하려면 FFmpeg가 필요합니다.

현재 DietFile은 시스템에 설치된 FFmpeg의 `ffmpeg`와 `ffprobe`를 사용합니다.

### macOS

Homebrew를 사용하는 경우 다음 명령어로 FFmpeg를 설치할 수 있습니다.

```bash
brew install ffmpeg
```

설치 후 다음 명령어로 정상적으로 설치되었는지 확인할 수 있습니다.

```bash
ffmpeg -version
ffprobe -version
```

### Windows

Windows에서는 FFmpeg를 설치한 후 `ffmpeg.exe`와 `ffprobe.exe`를 PATH에 등록해야 합니다.

설치가 완료된 후 명령 프롬프트 또는 PowerShell에서 다음 명령어를 실행하여 확인할 수 있습니다.

```bash
ffmpeg -version
ffprobe -version
```

FFmpeg가 정상적으로 인식되면 DietFile에서 비디오 파일을 사용할 수 있습니다.

> 현재 버전에서는 FFmpeg를 사용자가 직접 설치해야 합니다. 추후 배포 편의성을 위해 FFmpeg를 DietFile에 번들링하여 별도의 FFmpeg 설치 없이 사용할 수 있도록 개선할 예정입니다.