#!/bin/sh

# Some events send additional information specific to the event in the $INFO
# variable. E.g. the front_app_switched event sends the name of the newly
# focused application in the $INFO variable:
# https://felixkratz.github.io/SketchyBar/config/events#events-and-scripting

MONITOR=$(aerospace list-monitors --focused | cut -d'|' -f1 | tr -d ' ')

if [ "$SENDER" = "front_app_switched" ]; then
    sketchybar --set "$NAME" label="[$MONITOR] → $INFO"
elif [ "$SENDER" = "aerospace_workspace_change" ] || [ "$SENDER" = "aerospace_monitor_change" ]; then
    WORKSPACE=$(aerospace list-workspaces --focused)
    FRONT_APP=$(aerospace list-windows --workspace "$WORKSPACE" --format "%{app-name}" 2>/dev/null | head -n 1)
    if [ -z "$FRONT_APP" ]; then
        sketchybar --set "$NAME" label="[$MONITOR] → No App"
    else
        sketchybar --set "$NAME" label="[$MONITOR] → $FRONT_APP"
    fi
fi
