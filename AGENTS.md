# Agent 규칙

이 파일은 coding agent가 따라야 하는 canonical rule 파일이다. 전체 onboarding 문서가 아니므로 짧게 유지한다.

## 읽는 순서

- 먼저 `TASKS.md`를 읽고 현재 milestone과 acceptance criteria를 따른다.
- `README.md`와 `project_plan.md`는 프로젝트 방향을 확인할 때만 읽는다.
- `docs/setup.md`, `docs/data.md`, `docs/research.md`, `docs/experiments.md`는 해당 주제를 다룰 때만 읽는다.
- 모든 작업에서 모든 문서를 읽지 않는다. 필요한 최소 context만 가져온다.

## 프로젝트 방향

- 실행 순서는 MacBook tiny smoke run -> RTX 5090 medium run -> AIP/H100 large run이다.
- 모든 장비에서 pipeline은 같다: CARLA data collection -> training -> open-loop evaluation -> closed-loop evaluation.
- 먼저 MacBook smoke behavior를 구현하고, 같은 code path를 나중에 확장한다.
- MacBook과 RTX 5090 run이 AIP/H100 migration을 정당화하기 전에는 AIP/H100으로 옮기지 않는다.

## 작업 규칙

- 한 번에 하나의 milestone만 진행한다. `TASKS.md`보다 앞서가지 않는다.
- 새 파일을 만들기 전에 `TASKS.md`에 적힌 기존 stub 파일을 먼저 확인한다.
- `TASKS.md`가 요구하지 않는 한 folder structure를 바꾸지 않는다.
- 큰 rewrite보다 작고 검증 가능한 변경을 우선한다.
- 금지 규칙을 만나면 멈추지 말고 문서에 적힌 대안을 사용한다.

## 코드 규칙

- 기존 Python package layout인 `src/vla_drive/`를 사용한다.
- 공유 schema는 `src/vla_drive/data/schemas.py`에 둔다.
- CARLA integration은 `src/vla_drive/simulation/`에 둔다.
- model 코드는 `src/vla_drive/models/`에 둔다.
- training 코드는 `src/vla_drive/training/`에 둔다.
- evaluation 코드는 `src/vla_drive/evaluation/`에 둔다.
- 새 dependency를 추가하려면 `docs/setup.md`에 이유와 offline install path를 함께 기록한다.

## 규모 규칙

- MacBook: 짧은 route, 낮은 resolution, 낮은 traffic, tiny/small training, small evaluation.
- RTX 5090: 더 큰 CARLA collection, LoRA/QLoRA, 반복 evaluation.
- AIP/H100: local validation 이후 final large run과 ablation에만 사용.
- 10B급 full fine-tuning으로 시작하지 않는다. 먼저 frozen backbone, LoRA, QLoRA, 작은 image size, gradient accumulation을 사용한다.

## Offline 규칙

- internet이 없을 수 있다고 가정한다.
- internet이 필요하면 `BLOCKED: needs internet`로 표시하고 다른 offline-safe task를 진행한다.
- `TASKS.md`에서 완료된 asset은 다시 다운로드하지 않는다.
- `data/offline/`, `.conda/`, checkpoint, output, cache, model weight는 commit하지 않는다.

## 검증

- 코드 변경 후 가장 작은 관련 test를 실행한다.
- 현재 local validation 기본 명령:

```bash
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python -m pytest
```

- test를 실행할 수 없으면 실패한 명령과 정확한 이유를 기록한다.

## Agent 동작

- 이 파일을 긴 manual로 만들지 않는다. 반복 실패가 생긴 뒤에만 rule을 추가한다.
- "좋은 코드 작성" 같은 모호한 조언을 쓰지 않는다. 구체적인 제약만 쓴다.
- 긴 `@file` 또는 전체 문서 context injection을 피한다. 어떤 파일을 왜 읽는지 명시한다.
- 복잡한 명령은 긴 설명보다 `scripts/` 안의 단순 script로 만들고 그 script를 문서화한다.
- custom skill, command, subagent는 초기에 많이 만들지 않는다. workflow가 반복되고 안정된 뒤 추가한다.
