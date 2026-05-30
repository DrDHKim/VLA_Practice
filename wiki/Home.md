# VLA Drive Wiki

이 위키는 로컬 LLM과 사람이 프로젝트를 빠르게 탐색하기 위한 문서 허브다. 실행 순서는 `TASKS.md`를 따르고, 설계 판단은 `project_plan.md`, `docs/research.md`, `docs/experiments.md`를 따른다.

## Start Here

1. `README.md`: 프로젝트 전체 개요
2. `project_plan.md`: 모델/데이터/하드웨어 전략
3. `TASKS.md`: 구현 순서와 완료 기준
4. `wiki/Handbook.md`: 구현자가 보는 압축 가이드
5. `docs/setup.md`: Anaconda, 하드웨어, 오프라인 다운로드, 120GB 예산
6. `docs/research.md`: 모델 선정과 논문 목록
7. `docs/data.md`: 데이터 우선순위와 스키마
8. `docs/experiments.md`: 실험 매트릭스

## Main Pages

- [Handbook](Handbook.md)
- [Glossary](Glossary.md)

## Machine Scale Rule

The same pipeline runs on every machine:

```text
CARLA data collection -> training -> open-loop evaluation -> closed-loop evaluation
```

- MacBook runs the tiny smoke version first.
- RTX 5090 runs the medium-scale version after the MacBook path works.
- AIP/H100 runs only after MacBook and RTX 5090 results justify irreversible migration.

## Wiki Rules

- 위키는 구현 지시서가 아니라 탐색 문서다.
- 실제 todo와 상태는 항상 `TASKS.md`에 기록한다.
- 논문 요약은 `docs/research/notes/`에 둔다.
- 실험 결과는 `outputs/reports/`에 저장하고, 중요한 결론만 위키에 요약한다.
