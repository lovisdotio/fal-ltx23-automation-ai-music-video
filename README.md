# AI Music Video Pipeline

Fully automated pipeline to create AI-generated music videos using **fal.ai** models. Zero manual editing.

**Pipeline:** Suno AI (music) → fal.ai nano-banana-pro (scene frames) → fal.ai LTX 2.3 (audio-to-video) → ffmpeg (effects + assembly)

https://github.com/user-attachments/assets/placeholder

## How it works

1. **Music** — Generate a track on [Suno AI](https://suno.com) (or use any audio file)
2. **Character** — Generate claymation character options with `nano-banana-pro`
3. **Frames** — Generate 3 scene frame variants per audio segment using character reference
4. **Select frames** — Pick the best frame per segment via browser UI
5. **Videos** — Generate 3 LTX 2.3 audio-to-video clips per segment
6. **Select videos** — Pick the best video per segment via browser UI
7. **Redo** — Re-generate any bad segments with new frames + videos
8. **Assemble** — Concatenate with music video effects (zooms, flashes, shakes, color burns)
9. **Overlay** — Add showcase overlay showing pipeline, prompts, and input frames

## Quick start

```bash
# Clone
git clone https://github.com/lovisdotio/fal-ltx23-automation-ai-music-video.git
cd fal-ltx23-automation-ai-music-video

# Install
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set your fal.ai API key
export FAL_KEY="your-api-key"

# Place your audio file
cp /path/to/your/song.mp3 audio.mp3
```

## Step by step

### 1. Generate character options
```bash
python pipeline.py character
# → Pick your favorite from output/characters/
# → Copy it to output/character.png
```

### 2. Generate scene frames
```bash
python pipeline.py frames
```

### 3. Select best frames
```bash
python pipeline.py select-frames
# → Opens browser UI at http://localhost:8888/frame_selector.html
# → Click best frame per segment, export selections
```

### 4. Generate videos
```bash
python pipeline.py videos
```

### 5. Select best videos
```bash
python pipeline.py select-videos
# → Opens browser UI at http://localhost:8888/video_selector.html
# → Pick best video per segment, export selections
```

### 6. Re-do bad segments (optional)
```bash
python pipeline.py redo 3,9,13
python pipeline.py select-redo
```

### 7. Assemble final video
```bash
python pipeline.py assemble
# → output/final/final_video.mp4
```

### 8. Add showcase overlay (optional)
```bash
python pipeline.py overlay
# → output/final/showcase.mp4
```

## Customization

Edit `pipeline.py` to customize:

- **`SCENES`** — List of scene descriptions (one per segment)
- **`CHARACTER_PROMPT`** — Character design prompt
- **`CHARACTER_STYLE`** — Visual style applied to all generations
- **`SPEED_FACTOR`** — Playback speed (0.75 = 25% faster)
- **`RANDOM_SEED`** — Seed for reproducible effects
- **`MAX_WORKERS`** — Concurrent fal.ai API calls

## Requirements

- Python 3.10+
- ffmpeg + ffprobe
- [fal.ai](https://fal.ai) API key

## Models used

| Step | Model | What it does |
|------|-------|-------------|
| Character & Frames | [`fal-ai/nano-banana-pro`](https://fal.ai/models/fal-ai/nano-banana-pro) | Text/image-to-image generation |
| Video | [`fal-ai/ltx-2/v2.3/audio-to-video`](https://fal.ai/models/fal-ai/ltx-2/v2.3/audio-to-video) | Audio-reactive video generation |

## Music

See [`suno_instructions.md`](suno_instructions.md) for the Suno AI prompt used to generate the reggaeton track.

## License

MIT
