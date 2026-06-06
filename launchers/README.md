# Launchers

macOS에서 더블클릭하거나 터미널에서 직접 실행하는 launcher 파일을 모아두는 폴더다.

- `01_카를라실행.command`: macOS용 CARLA server 실행. RGB 렌더링을 위해 CrossOver 64-bit bottle + D3DMetal을 기본 backend로 쓴다. 파일 상단의 실행 파라미터를 수정해서 실행한다.
- `02_카를라연결확인.command`: 실행 중인 CARLA server에 연결해 world name을 출력한다. Mac native Python 대신 CrossOver bottle 내부 Python과 Windows CARLA PythonAPI를 사용한다.
- `03_학습.command`: CARLA JSONL로 학습을 실행한다. 기본값은 Town01 route waypoint가 backfilled된 metadata로 route waypoint 입력을 켠 `reasoning_aux` 학습이다. route-wp metadata가 없고 기존 100-scene metadata가 있으면 01 launcher로 CARLA를 자동 실행한 뒤 current Town01 map 기준 backfill을 먼저 수행한다. `STAGE`, `USE_ROUTE_WAYPOINTS`, `RESUME_FROM`, epoch, early stopping, batch size, gradient accumulation, learning rate, checkpoint/log 경로를 파일 상단에서 조정한다. `frozen_vlm`과 `lora_vlm` stage로 Qwen2.5-VL-3B full VLM backbone 연결도 실행할 수 있다.
- `05_평가.command`: open-loop, CARLA Traffic Manager closed-loop, learned-policy closed-loop 평가를 실행한다. 기본값은 Town01 learned-policy 1-route HUD 평가이며, `EVAL_MODE=open_loop|closed_loop|learned_closed_loop`로 바꿀 수 있다. route-waypoint checkpoint가 있으면 기본 checkpoint로 쓰고, 없으면 기존 command-conditioned checkpoint로 fallback한다. learned mode는 Mac torch inference server와 CrossOver CARLA client를 launcher 내부에서 함께 실행하고 HUD video까지 생성한다. learned mode 기본 출력은 `outputs/reports/learned_closed_loop/YYYYmmdd_HHMMSS/` 아래에 report, HUD video, frame artifacts, logs, run metadata를 함께 저장한다.
- `06_데이터수집.command`: CARLA Traffic Manager autopilot으로 여러 scene을 수집한다. `SCENE_COUNT`, scene별 초, FPS, 해상도, weather, output root를 파일 상단에서 조정한다. `CONTROL_MODE=autopilot`이 기본이며 다른 직접 제어 fallback은 없다. 각 scene은 `scene_000`, `scene_001` 형식으로 저장되고 전체 metadata는 output root의 `metadata.jsonl`로 합쳐진다.
