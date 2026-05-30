# Glossary

## VLA

Vision-Language-Action model. visual input과 language/context를 action으로 매핑하는 model.

## VLM

Vision-Language Model. perception/reasoning backbone으로 사용한다.

## Waypoint

ego-vehicle coordinate의 future position. baseline은 direct control 대신 waypoint sequence를 예측한다.

## Ego State

speed, acceleration, yaw rate, pose 같은 vehicle state.

## Route Command

`go straight`, `turn left`, `turn right`, `follow lane` 같은 high-level instruction.

## Open-Loop Evaluation

action을 simulator에 적용하지 않고, 예측 trajectory를 logged ground truth와 비교하는 evaluation.

## Closed-Loop Evaluation

policy를 CARLA 안에서 실제로 실행하고 driving behavior를 측정하는 evaluation.

## LoRA / QLoRA

Parameter-efficient fine-tuning 방법. MacBook에서는 frozen-backbone 또는 매우 작은 LoRA test를 사용하고, RTX 5090에서는 LoRA/QLoRA를 기본으로 사용한다. AIP/H100에서는 migration 이후 larger LoRA/ablation run에 사용한다.

## Smoke Run

data collection, training, evaluation이 모두 포함된 가장 작은 complete run. 이 project의 첫 smoke run은 MacBook에서 실행한다.

## Scale Ladder

project 실행 순서: MacBook tiny smoke run, RTX 5090 medium run, 필요할 때 AIP/H100 large run.
