#!/bin/bash

FOCUS=$(shortcuts run "Get Current Focus" 2>/dev/null)

if [ -z "$FOCUS" ] || [ "$FOCUS" == "null" ]; then
  ICON=""
  LABEL=""
else
  ICON="󰀝"
  LABEL="$FOCUS"
fi

sketchybar --set "$NAME" icon="$ICON" label="$LABEL"
