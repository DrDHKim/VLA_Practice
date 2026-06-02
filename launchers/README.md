# Launchers

macOS에서 더블클릭하거나 터미널에서 직접 실행하는 launcher 파일을 모아두는 폴더다.

- `01_카를라실행.command`: macOS용 CARLA server 실행. RGB 렌더링을 위해 CrossOver 64-bit bottle + D3DMetal을 기본 backend로 쓴다. 파일 상단의 실행 파라미터를 수정해서 실행한다.
- `02_카를라연결확인.command`: 실행 중인 CARLA server에 연결해 world name을 출력한다. Mac native Python 대신 CrossOver bottle 내부 Python과 Windows CARLA PythonAPI를 사용한다.
- `03_학습.command`: CARLA JSONL로 학습을 실행한다. `STAGE`, `RESUME_FROM`, epoch, early stopping, batch size, gradient accumulation, learning rate, checkpoint/log 경로를 파일 상단에서 조정한다. `frozen_vlm`과 `lora_vlm` stage로 Qwen2.5-VL-3B full VLM backbone 연결도 실행할 수 있다.
- `05_평가.command`: CARLA Traffic Manager autopilot closed-loop 평가를 실행한다. route 수, spawn 시작 index, target speed, Traffic Manager 옵션, report 경로를 파일 상단에서 조정한다. CARLA RPC port는 `WAIT_FOR_CARLA_SECONDS`만큼 기다린다.
- `06_데이터수집.command`: CARLA Traffic Manager autopilot으로 여러 scene을 수집한다. `SCENE_COUNT`, scene별 초, FPS, 해상도, weather, output root를 파일 상단에서 조정한다. `CONTROL_MODE=autopilot`이 기본이며 다른 직접 제어 fallback은 없다. 각 scene은 `scene_000`, `scene_001` 형식으로 저장되고 전체 metadata는 output root의 `metadata.jsonl`로 합쳐진다.
