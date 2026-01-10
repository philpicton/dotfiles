#!/bin/sh

# Some events send additional information specific to the event in the $INFO
# variable. E.g. the front_app_switched event sends the name of the newly
# focused application in the $INFO variable:
# https://felixkratz.github.io/SketchyBar/config/events#events-and-scripting

MONITOR=$(aerospace list-monitors --focused | cut -d'|' -f1 | tr -d ' ')

if [ "$SENDER" = "front_app_switched" ]; then
    sketchybar --set "$NAME" label="[$MONITOR] → $INFO"
fi
