# Launchers

macOS에서 더블클릭하거나 터미널에서 직접 실행하는 launcher 파일을 모아두는 폴더다.

- `01_카를라실행.command`: macOS용 CARLA server 실행. RGB 렌더링을 위해 CrossOver 64-bit bottle + D3DMetal을 기본 backend로 쓴다. 파일 상단의 실행 파라미터를 수정해서 실행한다.
- `02_카를라연결확인.command`: 실행 중인 CARLA server에 연결해 world name을 출력한다. Mac native Python 대신 CrossOver bottle 내부 Python과 Windows CARLA PythonAPI를 사용한다.
- `03_학습.command`: CARLA JSONL로 회귀 waypoint 정책 학습을 실행한다. `STAGE`, `USE_ROUTE_WAYPOINTS`, `RESUME_FROM`, epoch, early stopping, batch size, gradient accumulation, learning rate, checkpoint/log 경로를 파일 상단에서 조정한다. `frozen_vlm`과 `lora_vlm` stage로 Qwen2.5-VL-3B 특징 연결도 실행할 수 있다.
- `05_평가.command`: 기본값은 `07`에서 학습한 AutoVLA LoRA를 쓰는 Town01 learned-policy 1-route HUD 평가다. CARLA가 꺼져 있으면 `01`을 자동 실행하고, 3개 모델 카메라와 글로벌 경로에서 계산한 high-level command를 입력해 synchronous closed-loop 평가한다. HUD에는 reasoning, action token, predicted waypoint, route waypoint, steer/throttle/brake를 표시한다. 결과는 `outputs/reports/learned_closed_loop/YYYYmmdd_HHMMSS/` 아래에 report, HUD video, frame artifacts, logs, run metadata로 저장한다. 회귀 checkpoint는 `POLICY_TYPE=regression`과 해당 `.pt` 경로를 지정해 평가하며, AutoVLA open-loop 평가는 아직 연결되지 않았다.
- `06_데이터수집.command`: CARLA Traffic Manager autopilot으로 여러 scene을 수집한다. `SCENE_COUNT`, scene별 초, FPS, 해상도, weather, output root를 파일 상단에서 조정한다. `CONTROL_MODE=autopilot`이 기본이며 다른 직접 제어 fallback은 없다. 각 scene은 `scene_000`, `scene_001` 형식으로 저장되고 전체 metadata는 output root의 `metadata.jsonl`로 합쳐진다.
- `07_AutoVLA학습.command`: 3카메라 RGB + ego speed + high-level command에서 reasoning 문장과 action token trajectory를 생성하는 Qwen2.5-VL LoRA를 학습한다. dataset 생성, 주기적 checkpoint, milestone 보존, 중단 후 자동 resume를 한 launcher에서 처리한다.
