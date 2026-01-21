#!/bin/bash

# Source theme colours
source "$CONFIG_DIR/theme/colours.sh"

# Get next calendar event from Apple Shortcut
result=$(shortcuts run "Get Next Calendar Event" 2>/dev/null)

if [ -z "$result" ]; then
    sketchybar --set "$NAME" label="" icon.drawing=off
    exit 0
fi

# Parse JSON response
title=$(echo "$result" | grep -o '"title":"[^"]*"' | cut -d'"' -f4)
start=$(echo "$result" | grep -o '"start":"[^"]*"' | cut -d'"' -f4)
end=$(echo "$result" | grep -o '"end":"[^"]*"' | cut -d'"' -f4)
link=$(echo "$result" | grep -o '"link":"[^"]*"' | cut -d'"' -f4 | sed 's/\\//g')

# Format display text
if [ -n "$title" ]; then
    # Check if times are valid (not "none")
    if [ -n "$start" ] && [ "$start" != "none" ] && [ -n "$end" ] && [ "$end" != "none" ]; then
        display_text="${start}-${end} ${title}"

        # Get current time in minutes since midnight
        current_mins=$((10#$(date +%H) * 60 + 10#$(date +%M)))

        # Parse start time (format: HH:MM)
        start_hour=$(echo "$start" | cut -d: -f1)
        start_min=$(echo "$start" | cut -d: -f2)
        start_mins=$((10#$start_hour * 60 + 10#$start_min))

        # Calculate time difference
        time_diff=$((start_mins - current_mins))

        # Determine text color (yellow if within 5 minutes, white otherwise)
        if [ $time_diff -le 5 ] && [ $time_diff -ge 0 ]; then
            text_color=$CALENDAR_EVENT_COLOUR
            icon_color=$CALENDAR_ICON_COLOUR
            icon=
        else
            text_color=$TEXT_COLOUR
            icon_color=$TEXT_COLOUR
            icon=
        fi
    else
        # Times are "none", just show title with default color
        display_text="$title"
        text_color=$TEXT_COLOUR
        icon_color=$TEXT_COLOUR
        icon=
    fi

    # Set up click script if link exists and is not "none"
    if [ -n "$link" ] && [ "$link" != "none" ]; then
        sketchybar --set "$NAME" \
            label="$display_text" \
            icon="$icon" \
            icon.color="$icon_color" \
            icon.font="MonoLisa Nerd Font Mono:Regular:15.0" \
            label.font="MonoLisa Nerd Font Mono:Regular:13.0" \
            label.color="$text_color" \
            icon.padding_left=10 \
            icon.padding_right=4 \
            label.padding_left=4 \
            label.padding_right=10 \
            click_script="open \"${link}\""
    else
        sketchybar --set "$NAME" \
            label="$display_text" \
            icon="$icon" \
            icon.color="$icon_color" \
            icon.font="MonoLisa Nerd Font Mono:Regular:15.0" \
            label.font="MonoLisa Nerd Font Mono:Regular:13.0" \
            label.color="$text_color" \
            icon.padding_left=10 \
            icon.padding_right=4 \
            label.padding_left=4 \
            label.padding_right=10
    fi
else
    sketchybar --set "$NAME" label="" icon.drawing=off
fi
