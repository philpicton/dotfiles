#!/bin/bash

FOCUS=$(shortcuts run "Get Current Focus" 2>/dev/null)

if [ -z "$FOCUS" ] || [ "$FOCUS" == "null" ]; then
    ICON=""
    LABEL=""
elif [ "$FOCUS" == "Personal" ]; then
    ICON="☢︎"
    LABEL="$FOCUS"
elif [ "$FOCUS" == "Work" ]; then
    ICON="⚒︎"
    LABEL="$FOCUS"
elif [ "$FOCUS" == "Sleep" ]; then
    ICON="☾"
    LABEL="$FOCUS"
elif [ "$FOCUS" == "Do Not Disturb" ]; then
    ICON="󰀝"
    LABEL="DND"
elif [ "$FOCUS" == "Driving" ]; then
    ICON="🚗"
    LABEL="$FOCUS"
elif [ "$FOCUS" == "Fitness" ]; then
    ICON="🏃"
    LABEL="$FOCUS"
elif [ "$FOCUS" == "Reduce Interruptions" ]; then
    ICON="⏣"
    LABEL="Reduce"
elif [ "$FOCUS" == "Meeting" ]; then
    ICON=""
    LABEL=$FOCUS
else
    ICON="☣︎"
    LABEL="$FOCUS"
fi

sketchybar --set "$NAME" icon="$ICON" label="$LABEL"
