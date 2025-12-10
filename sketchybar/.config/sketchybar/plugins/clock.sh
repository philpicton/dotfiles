#!/bin/sh

# The $NAME variable is passed from sketchybar and holds the name of
# the item invoking this script:
# https://felixkratz.github.io/SketchyBar/config/events#events-and-scripting

sketchybar --set "$NAME" \
    label="$(date '+%a %d %b   %H:%M')" \
    icon='' \
    label.drawing=on \
    icon.padding_left=10 \
    icon.padding_right=4 \
    label.padding_left=4 \
    label.padding_right=10
