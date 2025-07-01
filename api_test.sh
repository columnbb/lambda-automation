#!/bin/bash
API_KEY="sk-p4LBjEoBlPCQGNDH0mRHBbrya2kbqRyDVkfVKnPXKTJjxxYY"
PROMPT="futuristic spaceship"

curl -X POST "https://api.stability.ai/v2beta/stable-image/generate/sd3" \
  -H "Authorization: Bearer $API_KEY" \
  -F "prompt=$PROMPT" \
  -F "output_format=png" \
  -o generated_image.png

echo "Image saved as generated_image.png"

