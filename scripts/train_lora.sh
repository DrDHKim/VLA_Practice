#!/usr/bin/env bash
set -euo pipefail

python -m vla_drive.training.train --config-name carla_rgb_waypoint

