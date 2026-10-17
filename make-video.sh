#!/bin/zsh
# A 20 s synthetic 4K 60 fps H.264 clip with shifting colors (about 180 MB). Needs ffmpeg.
set -e
cd "${0:A:h}"
mkdir -p media
echo "Encoding media/test-4k60.mp4 (takes about a minute)..."
ffmpeg -loglevel error -y -f lavfi -i "testsrc2=size=3840x2160:rate=60:duration=20" -vf "hue=H=2*PI*t/8" \
  -pix_fmt yuv420p -c:v libx264 -preset ultrafast -crf 30 -g 60 -movflags +faststart media/test-4k60.mp4
echo "media/test-4k60.mp4: $(du -h media/test-4k60.mp4 | cut -f1)"
