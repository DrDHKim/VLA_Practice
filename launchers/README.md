# Launchers

macOS에서 더블클릭하거나 터미널에서 직접 실행하는 launcher 파일을 모아두는 폴더다.

- `01_카를라실행.command`: macOS용 CARLA server 실행. RGB 렌더링을 위해 CrossOver 64-bit bottle + D3DMetal을 기본 backend로 쓴다. 파일 상단의 실행 파라미터를 수정해서 실행한다.
- `02_카를라연결확인.command`: 실행 중인 CARLA server에 연결해 world name을 출력한다. Mac native Python 대신 CrossOver bottle 내부 Python과 Windows CARLA PythonAPI를 사용한다.
- `03_학습.command`: tiny CARLA JSONL로 학습을 실행한다. `STAGE`, `RESUME_FROM`, epoch, batch size, checkpoint/log 경로를 파일 상단에서 조정한다.
- `04_PID튜닝.command`: waypoint-to-control PID grid search를 실행한다. target speed, steer gain, speed/brake gain 후보를 파일 상단 배열에서 조정한다. CARLA RPC port는 `WAIT_FOR_CARLA_SECONDS`만큼 기다린다.
- `05_평가.command`: closed-loop CARLA 평가를 실행한다. route 수, spawn 시작 index, PID gain, report 경로를 파일 상단에서 조정한다. CARLA RPC port는 `WAIT_FOR_CARLA_SECONDS`만큼 기다린다.
