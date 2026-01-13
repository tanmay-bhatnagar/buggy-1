#!/bin/bash
# Launch Label Studio using buggy conda environment
# All data stays local in ~/Library/Application Support/label-studio/

source /opt/anaconda3/bin/activate buggy
label-studio start --port 8080

# After signing up locally, your data is stored at:
# ~/Library/Application Support/label-studio/
