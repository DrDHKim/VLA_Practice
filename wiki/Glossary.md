# Glossary

## VLA

Vision-Language-Action model. A model that maps visual input and language/context into actions.

## VLM

Vision-Language Model. Used as the perception/reasoning backbone.

## Waypoint

A future position in ego-vehicle coordinates. The baseline predicts a sequence of waypoints instead of direct controls.

## Ego State

Vehicle state such as speed, acceleration, yaw rate, and pose.

## Route Command

High-level instruction such as `go straight`, `turn left`, `turn right`, or `follow lane`.

## Open-Loop Evaluation

Evaluating predicted trajectories against logged ground truth without applying actions to the simulator.

## Closed-Loop Evaluation

Running the policy inside CARLA and measuring actual driving behavior.

## LoRA / QLoRA

Parameter-efficient fine-tuning methods. Use frozen-backbone or very small LoRA tests on MacBook, LoRA/QLoRA as the default for RTX 5090, and larger LoRA/ablation runs only after moving to AIP/H100.

## Smoke Run

The smallest complete data collection, training, and evaluation run. In this project, the first smoke run belongs on the MacBook.

## Scale Ladder

The project execution order: MacBook tiny smoke run, RTX 5090 medium run, then AIP/H100 large run if needed.
