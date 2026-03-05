#!/usr/bin/env python3
"""
AI Music Video Pipeline
=======================
Fully automated pipeline to create AI music videos using fal.ai.

Pipeline: Suno AI (music) -> fal.ai nano-banana-pro (frames) -> fal.ai LTX 2.3 (video) -> ffmpeg (assembly)

Steps:
  1. character      - Generate character options (pick your favorite)
  2. frames         - Generate scene frames (3 per segment, then select best)
  3. select-frames  - Serve frame selector UI
  4. videos         - Generate LTX audio-to-video clips (3 per segment)
  5. select-videos  - Serve video selector UI
  6. redo 3,9,13    - Re-generate bad segments
  7. select-redo    - Serve redo selector UI
  8. assemble       - Assemble final video with effects + speed up
  9. overlay        - Add showcase overlay (pipeline info, prompts, thumbnails)

Usage:
  python pipeline.py <step>

Requirements:
  - FAL_KEY env var set with your fal.ai API key
  - ffmpeg + ffprobe installed
  - pip install fal-client pydub Pillow
"""

import json
import os
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ============================================================
# CONFIG - Edit these for your project
# ============================================================

AUDIO_FILE = "audio.mp3"                    # Your music file
CHARACTER_REF = "output/character.png"       # Selected character image (copy your pick here)

# fal.ai models
IMAGE_MODEL = "fal-ai/nano-banana-pro"
IMAGE_EDIT_MODEL = "fal-ai/nano-banana-pro/edit"
VIDEO_MODEL = "fal-ai/ltx-2/v2.3/audio-to-video"

# Pipeline settings
MAX_WORKERS = 20
VARIANTS = 3
SPEED_FACTOR = 0.75       # 0.75 = 25% faster playback
RANDOM_SEED = 42
FPS = 25
VIDEO_CRF = 18

# Style prompt appended to all image/video generations
CHARACTER_STYLE = (
    "CLAYMATION STOP MOTION STYLE, visible clay texture, fingerprint marks, "
    "Aardman Laika quality, handmade miniature world"
)

# Character prompt for step 1
CHARACTER_PROMPT = (
    "Character reference sheet, full body left, face close-up right. "
    "Mexican guy, messy textured hair, red Converse Chuck 70 high tops, "
    "black skinny jeans with chain, vintage red Members Only jacket, "
    "round sunglasses, toothpick in mouth, cool lean pose. "
    f"{CHARACTER_STYLE}. 16:9"
)

# ============================================================
# SCENES - Edit these for your video's story
# ============================================================

SCENES = [
    "Close-up, waking up inside a giant sneaker like a bed, stretching and yawning, cozy morning light",
    "Medium close-up, stepping out of a portal made of vinyl records, looking around amazed at a new world",
    "Close-up face, riding an elevator that goes sideways through a building made of speakers, wind in face",
    "Medium shot, standing on a rooftop at night, entire city below is made of tiny glowing synthesizers",
    "Close-up, DJ-ing on turntables made of pizza, spinning slices, cheese strings flying, focused face",
    "Medium close-up, surfing on a giant paper airplane over a city of clouds, hair blowing, excited",
    "Close-up face, inside a bubble floating through a neon forest, colors reflecting on face",
    "Medium shot, having a staring contest with his own clay reflection in a giant mirror, funny intensity",
    "Close-up, opening a fridge full of tiny glowing universes, face lit by cosmic light, amazed",
    "Medium close-up, skateboarding down a rainbow that wraps around skyscrapers, cool confident face",
    "Close-up, walking upside down on the ceiling of a tiny apartment, furniture falling up, confused smile",
    "Medium close-up, arm wrestling a clay alien at a bar on the moon, intense concentration",
    "Close-up face, inside a snow globe being shaken, tiny buildings and snow swirling around",
    "Medium shot, shrunk tiny standing on a spinning vinyl record, giant DJ booth behind him",
    "Close-up, face melting like ice cream then reforming back, trippy claymation morph",
    "Medium close-up, in a room where gravity keeps changing direction, stumbling funny",
    "Close-up face, wearing headphones so big they cover his whole body, vibing hard",
    "Close-up, screaming into a microphone made of lightning, electricity sparking everywhere",
    "Medium shot, running on a giant hamster wheel that powers a neon sign of his face",
    "Close-up face, in a boxing ring with his own shadow, shadow is winning, dramatic",
    "Medium close-up, playing drums on clouds that make thunder, rain falling on beat",
    "Close-up, wearing VR goggles showing tiny galaxies in lenses, mind blown expression",
    "Medium shot, bouncing on a trampoline made of a giant phone screen showing his own music video",
    "Close-up face, head spinning 360 like a cartoon, dizzy stars orbiting, funny dazed look",
    "Medium close-up, crowd surfing on tiny clay hands at a miniature concert, spotlight on face",
    "Close-up face, inside a giant speaker, bass waves distorting his clay face comically",
    "Medium shot, dance battle with a clay robot in a neon parking garage, competitive energy",
    "Close-up, juggling tiny planets like a street performer, Saturn ring spinning on finger",
    "Medium close-up, getting a haircut from a robot barber, looking fresh, sparks flying",
    "Close-up face, blowing a bubblegum bubble so big it lifts him off the ground, city below",
    "Medium shot, teaching tiny clay aliens how to dance in a spaceship classroom",
    "Close-up, stuck in a giant block of Jello, trying to sing through it, wobble effect",
    "Medium close-up, piloting a paper airplane through a canyon made of giant books and CDs",
    "Close-up face, reflection in a puddle shows a completely different character, confused look",
    "Medium shot, playing air guitar on a rooftop and actual soundwaves are visible destroying buildings",
    "Close-up, face half clay half pixelated, reality glitching, pieces falling and reforming",
    "Medium close-up, in a museum where all paintings are silly versions of himself, proud tour guide",
    "Close-up face, surrounded by floating donuts raining sprinkles, pure joy, mouth wide open",
    "Medium shot, racing a snail on tiny go-karts through a living room, dead serious competitive face",
    "Close-up, cool walk away from explosion behind him, sunglasses sliding on perfectly",
    "Medium close-up, on a stage made of stacked boom boxes, tiny clay crowd going wild",
    "Close-up face, sweating clay drops that turn into tiny clones of himself as they fall",
    "Medium shot, doing a backflip off a giant thumbs-up hand, frozen mid-air, dramatic",
    "Close-up, face lit by a hundred tiny candles, making a wish, magical sparkle in eyes",
    "Medium close-up, riding a rollercoaster made of rainbow clay through cotton candy clouds",
    "Close-up face, catching a falling star that turns into a microphone, pure magic",
    "Medium shot, walking into a sunset, path made of piano keys that light up with each step",
    "Close-up face, gentle smile, tiny clay butterflies landing on his nose, warm golden light",
    "Medium close-up, sitting on a crescent moon, feet dangling over tiny city below, peaceful",
    "Close-up, one last wink to camera, confetti falling in slow motion, warm colors",
    "Medium shot, slowly turning into a clay statue in a gallery, visitors amazed, subtle frozen smile",
    "Close-up face, slowly closing eyes, clay world softly crumbling into colorful stardust",
]

# ============================================================
# PATHS
# ============================================================

OUTPUT = Path("output")
CHARS_DIR = OUTPUT / "characters"
SCENES_DIR = OUTPUT / "scenes"
FRAMES_DIR = SCENES_DIR / "frames"
VIDEOS_DIR = OUTPUT / "videos" / "clips"
AUDIO_SEG_DIR = OUTPUT / "videos" / "audio_segments"
FINAL_DIR = OUTPUT / "final"
NORM_DIR = FINAL_DIR / "normalized"
FX_DIR = FINAL_DIR / "fx_clips"
OVERLAY_DIR = FINAL_DIR / "overlay"

SEGMENTS_FILE = SCENES_DIR / "segments.json"
FRAME_SELECTIONS = "frame_selections.json"
VIDEO_SELECTIONS = "video_selections.json"
REDO_SELECTIONS = "redo_selections.json"

for d in [CHARS_DIR, FRAMES_DIR, VIDEOS_DIR, AUDIO_SEG_DIR,
          FINAL_DIR, NORM_DIR, FX_DIR, OVERLAY_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ============================================================
# UTILITIES
# ============================================================

def get_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


def get_font(size):
    from PIL import ImageFont
    for fp in ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/SFNSMono.ttf",
               "/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Geneva.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
               "/usr/share/fonts/TTF/DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            pass
    return ImageFont.load_default()


def build_segments():
    random.seed(123)
    segments = []
    pos = 0
    try:
        total_dur = int(get_duration(AUDIO_FILE))
    except Exception:
        total_dur = 161
    durations = [1, 2, 2, 3, 3, 3, 4]

    for idx, scene in enumerate(SCENES):
        if pos >= total_dur:
            break
        dur = random.choice(durations)
        end = min(pos + dur, total_dur)
        if end - pos < 1:
            break
        segments.append({
            "index": idx, "start": pos, "end": end,
            "duration": end - pos, "scene": scene,
        })
        pos = end
    return segments


def load_all_selections():
    merged = {}
    for fname in [VIDEO_SELECTIONS, REDO_SELECTIONS]:
        try:
            with open(fname) as f:
                for k, v in json.load(f).items():
                    merged[int(k)] = v["path"]
        except FileNotFoundError:
            pass
    return merged


# ============================================================
# STEP 1: Generate character options
# ============================================================

def cmd_character():
    import fal_client

    print("Generating 10 character variants...\n")

    def gen(i):
        result = fal_client.subscribe(IMAGE_MODEL, arguments={
            "prompt": CHARACTER_PROMPT,
            "num_images": 1,
            "aspect_ratio": "16:9",
            "resolution": "2K",
            "output_format": "png",
        })
        path = CHARS_DIR / f"char_{i+1:02d}.png"
        subprocess.run(["curl", "-sL", "-o", str(path), result["images"][0]["url"]], check=True)
        print(f"  char_{i+1:02d} done")

    with ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(gen, range(10)))

    print(f"\nDone! Pick your favorite from {CHARS_DIR}/")
    print(f"Copy it to: {CHARACTER_REF}")


# ============================================================
# STEP 2: Generate scene frames
# ============================================================

def cmd_frames():
    import fal_client

    segments = build_segments()
    with open(SEGMENTS_FILE, "w") as f:
        json.dump(segments, f, indent=2)

    print(f"{len(segments)} segments, {VARIANTS} frames each = {len(segments)*VARIANTS} images\n")

    char_url = fal_client.upload_file(CHARACTER_REF)

    def gen_frame(seg, var_idx):
        label = f"seg{seg['index']:02d}_v{var_idx+1}"
        try:
            result = fal_client.subscribe(IMAGE_EDIT_MODEL, arguments={
                "image_urls": [char_url],
                "prompt": (
                    f"Place this exact claymation character into a fun scene. {seg['scene']}. "
                    f"{CHARACTER_STYLE}, character face clearly visible and expressive, 16:9 widescreen."
                ),
                "num_images": 1, "aspect_ratio": "16:9", "resolution": "2K", "output_format": "png",
            })
            path = FRAMES_DIR / f"{label}.png"
            subprocess.run(["curl", "-sL", "-o", str(path), result["images"][0]["url"]], check=True)
            print(f"  [{label}] done")
            return {"seg_idx": seg["index"], "var": var_idx, "path": str(path)}
        except Exception as e:
            print(f"  [{label}] ERROR: {e}")
            return None

    results = []
    with ThreadPoolExecutor(max_workers=30) as ex:
        futures = {ex.submit(gen_frame, seg, v): (seg, v)
                   for seg in segments for v in range(VARIANTS)}
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)

    with open(SCENES_DIR / "frame_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{len(results)}/{len(segments)*VARIANTS} frames generated")
    print(f"Next: python pipeline.py select-frames")


# ============================================================
# STEP 3: Generate videos
# ============================================================

def cmd_videos():
    import fal_client
    from pydub import AudioSegment

    with open(FRAME_SELECTIONS) as f:
        selections = json.load(f)
    with open(SEGMENTS_FILE) as f:
        segments = json.load(f)

    audio = AudioSegment.from_file(AUDIO_FILE)
    print(f"{len(segments)} segments, generating {VARIANTS} videos each\n")

    jobs = []
    for seg in segments:
        idx = str(seg["index"])
        if idx not in selections:
            continue

        start_ms, end_ms = seg["start"] * 1000, seg["end"] * 1000
        seg_audio = audio[start_ms:min(end_ms, len(audio))]
        if len(seg_audio) < 2000:
            seg_audio = audio[start_ms:min(start_ms + 2000, len(audio))]

        audio_path = AUDIO_SEG_DIR / f"seg{seg['index']:02d}.mp3"
        seg_audio.export(str(audio_path), format="mp3")
        audio_url = fal_client.upload_file(str(audio_path))
        frame_url = fal_client.upload_file(selections[idx]["path"])

        for v in range(VARIANTS):
            jobs.append({"seg": seg, "var": v, "frame_url": frame_url, "audio_url": audio_url})
        print(f"  seg{seg['index']:02d} ready ({seg['duration']}s)")

    print(f"\n{len(jobs)} video jobs\n")

    def gen_video(job):
        seg, v = job["seg"], job["var"]
        label = f"seg{seg['index']:02d}_v{v+1}"
        try:
            result = fal_client.subscribe(VIDEO_MODEL, arguments={
                "audio_url": job["audio_url"],
                "image_url": job["frame_url"],
                "prompt": (
                    f"Claymation stop motion music video. The clay character is singing, "
                    f"mouth open and moving with the music, head bobbing to the beat. "
                    f"{seg['scene']}. {CHARACTER_STYLE}. Face clearly visible."
                ),
                "resolution": "1080p", "fps": FPS, "guidance_scale": 7,
            }, with_logs=False)
            path = VIDEOS_DIR / f"{label}.mp4"
            subprocess.run(["curl", "-sL", "-o", str(path), result["video"]["url"]], check=True)
            print(f"  [{label}] done")
            return {"seg_idx": seg["index"], "var": v, "path": str(path)}
        except Exception as e:
            print(f"  [{label}] ERROR: {e}")
            return None

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(gen_video, j): j for j in jobs}
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)

    results.sort(key=lambda r: (r["seg_idx"], r["var"]))
    with open(OUTPUT / "videos" / "video_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{len(results)}/{len(jobs)} videos generated")
    print(f"Next: python pipeline.py select-videos")


# ============================================================
# STEP 4: Redo bad segments
# ============================================================

def cmd_redo(segment_indices):
    import fal_client
    from pydub import AudioSegment

    indices = [int(x.strip()) for x in segment_indices.split(",")]
    with open(SEGMENTS_FILE) as f:
        all_segments = json.load(f)

    segments = [s for s in all_segments if s["index"] in indices]
    print(f"Redoing {len(segments)} segments: {indices}\n")

    audio = AudioSegment.from_file(AUDIO_FILE)
    char_url = fal_client.upload_file(CHARACTER_REF)

    print("[FRAMES] Generating new close-up frames...\n")

    def gen_frame(seg):
        label = f"seg{seg['index']:02d}_redo"
        try:
            result = fal_client.subscribe(IMAGE_EDIT_MODEL, arguments={
                "image_urls": [char_url],
                "prompt": (
                    f"CLOSE-UP of this claymation character's face, singing with mouth open. "
                    f"Scene: {seg['scene']}. Face fills most of the frame, expressive. "
                    f"{CHARACTER_STYLE}, 16:9."
                ),
                "num_images": 1, "aspect_ratio": "16:9", "resolution": "2K", "output_format": "png",
            })
            path = FRAMES_DIR / f"{label}.png"
            subprocess.run(["curl", "-sL", "-o", str(path), result["images"][0]["url"]], check=True)
            print(f"  [FRAME {label}] done")
            return {"seg_idx": seg["index"], "path": str(path)}
        except Exception as e:
            print(f"  [FRAME {label}] ERROR: {e}")
            return None

    frame_results = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(gen_frame, s): s for s in segments}
        for f in as_completed(futures):
            r = f.result()
            if r:
                frame_results[r["seg_idx"]] = r

    print(f"\n[VIDEOS] Generating {len(frame_results)*3} videos...\n")

    jobs = []
    for seg in segments:
        if seg["index"] not in frame_results:
            continue
        start_ms, end_ms = seg["start"] * 1000, seg["end"] * 1000
        seg_audio = audio[start_ms:min(end_ms, len(audio))]
        if len(seg_audio) < 2000:
            seg_audio = audio[start_ms:min(start_ms + 2000, len(audio))]
        audio_path = AUDIO_SEG_DIR / f"seg{seg['index']:02d}_redo.mp3"
        seg_audio.export(str(audio_path), format="mp3")
        audio_url = fal_client.upload_file(str(audio_path))
        frame_url = fal_client.upload_file(frame_results[seg["index"]]["path"])
        for v in range(VARIANTS):
            jobs.append({"seg": seg, "var": v, "frame_url": frame_url, "audio_url": audio_url})

    def gen_video(job):
        seg, v = job["seg"], job["var"]
        label = f"seg{seg['index']:02d}_redo_v{v+1}"
        try:
            result = fal_client.subscribe(VIDEO_MODEL, arguments={
                "audio_url": job["audio_url"],
                "image_url": job["frame_url"],
                "prompt": (
                    f"Claymation stop motion music video. CLOSE-UP of clay character singing, "
                    f"mouth open moving with music, expressive face. {seg['scene']}. "
                    f"{CHARACTER_STYLE}. Face fills frame."
                ),
                "resolution": "1080p", "fps": FPS, "guidance_scale": 7,
            }, with_logs=False)
            path = VIDEOS_DIR / f"{label}.mp4"
            subprocess.run(["curl", "-sL", "-o", str(path), result["video"]["url"]], check=True)
            print(f"  [{label}] done")
            return {"seg_idx": seg["index"], "var": v, "path": str(path)}
        except Exception as e:
            print(f"  [{label}] ERROR: {e}")
            return None

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(gen_video, j): j for j in jobs}
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)

    print(f"\n{len(results)}/{len(jobs)} redo videos generated")
    print(f"Next: python pipeline.py select-redo")


# ============================================================
# STEP 5: Assemble final video
# ============================================================

def cmd_assemble():
    random.seed(RANDOM_SEED)

    with open(SEGMENTS_FILE) as f:
        segments = json.load(f)
    selections = load_all_selections()
    print(f"Segments: {len(segments)}, Selected: {len(selections)}\n")

    clips = []
    for seg in segments:
        if seg["index"] in selections:
            path = selections[seg["index"]]
            if Path(path).exists():
                clips.append({"seg": seg, "path": path})
    print(f"{len(clips)} clips to assemble")

    # Normalize to 1920x1080 25fps
    print("\n[NORMALIZE]...")
    for i, clip in enumerate(clips):
        out = NORM_DIR / f"clip_{i:03d}.mp4"
        dur = clip["seg"]["duration"]
        actual_dur = get_duration(clip["path"])
        trim_dur = min(dur, actual_dur)
        subprocess.run([
            "ffmpeg", "-y", "-i", clip["path"], "-t", str(trim_dur),
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
                   "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-c:v", "libx264", "-preset", "fast", "-crf", str(VIDEO_CRF),
            "-r", str(FPS), "-pix_fmt", "yuv420p", "-an", str(out),
        ], capture_output=True)
        clip["norm"] = str(out)
        clip["dur"] = trim_dur
    print(f"  {len(clips)} clips normalized")

    # Apply effects
    print("\n[EFFECTS]...")
    total_dur = sum(c["dur"] for c in clips)
    fallbacks = 0

    for i, clip in enumerate(clips):
        dur = clip["dur"]
        position = clip["seg"]["start"] / max(total_dur, 1)
        out = FX_DIR / f"fx_{i:03d}.mp4"
        vf = _build_fx(dur, i, position)
        try:
            r = subprocess.run([
                "ffmpeg", "-y", "-i", clip["norm"], "-t", str(dur), "-vf", vf,
                "-c:v", "libx264", "-preset", "fast", "-crf", str(VIDEO_CRF),
                "-r", str(FPS), "-pix_fmt", "yuv420p", "-an", str(out),
            ], capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                raise Exception("ffmpeg error")
        except Exception:
            subprocess.run(["cp", clip["norm"], str(out)], capture_output=True)
            fallbacks += 1
        clip["fx"] = str(out)
        print(f"  {i:03d} done")

    if fallbacks:
        print(f"  {fallbacks} fallbacks")

    # Concat
    concat_f = FINAL_DIR / "concat.txt"
    with open(concat_f, "w") as f:
        for c in clips:
            f.write(f"file '{Path(c['fx']).resolve()}'\n")

    raw = FINAL_DIR / "raw.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                     "-i", str(concat_f), "-c", "copy", str(raw)], capture_output=True)

    with_audio = FINAL_DIR / "with_audio.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", str(raw), "-i", AUDIO_FILE,
                     "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                     "-map", "0:v:0", "-map", "1:a:0", "-shortest",
                     str(with_audio)], capture_output=True)

    final = FINAL_DIR / "final_video.mp4"
    tempo = 1 / SPEED_FACTOR
    subprocess.run(["ffmpeg", "-y", "-i", str(with_audio),
                     "-filter_complex",
                     f"[0:v]setpts={SPEED_FACTOR}*PTS[v];[0:a]atempo={tempo}[a]",
                     "-map", "[v]", "-map", "[a]",
                     "-c:v", "libx264", "-preset", "fast", "-crf", str(VIDEO_CRF),
                     "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
                     str(final)], capture_output=True)

    for p in [concat_f, raw, with_audio]:
        p.unlink(missing_ok=True)

    dur = get_duration(str(final))
    print(f"\n{'='*50}")
    print(f"DONE: {final} ({dur:.1f}s)")
    print(f"{'='*50}")


# ============================================================
# STEP 6: Overlay
# ============================================================

def cmd_overlay():
    from PIL import Image, ImageDraw

    final_video = FINAL_DIR / "final_video.mp4"
    if not final_video.exists():
        print(f"ERROR: {final_video} not found. Run 'assemble' first.")
        sys.exit(1)

    with open(SEGMENTS_FILE) as f:
        segments = json.load(f)

    # Load frame selections with redo overrides
    frame_sel = {}
    try:
        with open(FRAME_SELECTIONS) as f:
            for k, v in json.load(f).items():
                frame_sel[int(k)] = v["path"]
    except Exception:
        pass
    # Override with redo frames if they exist
    for seg in segments:
        for suffix in ["_redo3", "_redo2", "_redo"]:
            path = FRAMES_DIR / f"seg{seg['index']:02d}{suffix}.png"
            if path.exists():
                frame_sel[seg["index"]] = str(path)
                break

    selections = load_all_selections()
    clips = [seg for seg in segments if seg["index"] in selections]
    total_segs = len(clips)

    timeline = []
    t = 0.0
    for seg in clips:
        dur = seg["duration"] * SPEED_FACTOR
        timeline.append({"seg": seg, "start": t, "dur": dur})
        t += dur

    src_dur = get_duration(str(final_video))
    total_frames = int(src_dur * FPS)
    W, H = 1920, 1080
    THUMB_W, THUMB_H = 300, 169
    CHROMA = (255, 0, 255)

    fb, fp, fs = get_font(22), get_font(20), get_font(17)

    print(f"Creating overlay for {total_segs} segments...")
    overlay_cache = {}
    for i, item in enumerate(timeline):
        seg = item["seg"]
        idx = seg["index"]
        img = Image.new("RGB", (W, H), CHROMA)
        draw = ImageDraw.Draw(img)

        # Top-right badge
        bt = "AI Generated  |  fal.ai + LTX 2.3"
        bb = draw.textbbox((0, 0), bt, font=fb)
        bw = bb[2] - bb[0] + 28
        bx = W - bw - 15
        draw.rounded_rectangle([(bx, 15), (bx + bw, 54)], radius=8, fill=(0, 0, 0))
        draw.text((bx + 14, 19), bt, fill=(255, 255, 255), font=fb)

        # Top-left thumbnail
        tx, ty = 15, 15
        draw.rounded_rectangle([(tx-3, ty-3), (tx+THUMB_W+3, ty+THUMB_H+3)],
                                radius=8, fill=(255, 255, 255))
        try:
            thumb = Image.open(frame_sel.get(idx, "")).convert("RGB")
            thumb = thumb.resize((THUMB_W, THUMB_H), Image.LANCZOS)
            img.paste(thumb, (tx, ty))
        except Exception:
            draw.rectangle([(tx, ty), (tx+THUMB_W, ty+THUMB_H)], fill=(40, 40, 40))

        draw.rounded_rectangle([(tx, ty+THUMB_H+5), (tx+THUMB_W, ty+THUMB_H+30)],
                                radius=5, fill=(0, 0, 0))
        lt = "INPUT FRAME"
        lb = draw.textbbox((0, 0), lt, font=fs)
        draw.text((tx+(THUMB_W-(lb[2]-lb[0]))//2, ty+THUMB_H+7), lt,
                   fill=(100, 220, 255), font=fs)

        draw.rounded_rectangle([(tx, ty+THUMB_H+34), (tx+THUMB_W, ty+THUMB_H+59)],
                                radius=5, fill=(0, 0, 0))
        sl = f"Segment {i+1}/{total_segs}"
        sb = draw.textbbox((0, 0), sl, font=fs)
        draw.text((tx+(THUMB_W-(sb[2]-sb[0]))//2, ty+THUMB_H+36), sl,
                   fill=(255, 180, 100), font=fs)

        # Bottom bar
        bar_h, bar_y = 95, H - 105
        draw.rounded_rectangle([(10, bar_y), (W-10, bar_y+bar_h)], radius=10, fill=(0, 0, 0))
        draw.text((22, bar_y+8),
                   "Suno AI  ->  fal.ai nano-banana-pro  ->  fal.ai LTX 2.3  ->  ffmpeg",
                   fill=(100, 200, 255), font=fs)
        sc = seg["scene"][:105] + "..." if len(seg["scene"]) > 105 else seg["scene"]
        draw.text((22, bar_y+32), f'prompt: "{sc}"', fill=(200, 255, 200), font=fp)
        draw.text((22, bar_y+62), "Zero manual editing  -  Fully automated AI pipeline",
                   fill=(255, 180, 100), font=fs)

        overlay_cache[i] = img

    frame_dir = OVERLAY_DIR / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    print(f"Generating {total_frames} overlay frames...")

    for frame_num in range(total_frames):
        frame_time = frame_num / FPS
        seg_i = len(timeline) - 1
        for i, item in enumerate(timeline):
            if item["start"] <= frame_time < item["start"] + item["dur"]:
                seg_i = i
                break
        out_path = frame_dir / f"frame_{frame_num:05d}.png"
        if not out_path.exists():
            overlay_cache[seg_i].save(str(out_path))
        if frame_num % 200 == 0:
            print(f"  {frame_num}/{total_frames}")

    overlay_vid = OVERLAY_DIR / "overlay.mp4"
    print("Encoding overlay video...")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS),
        "-i", str(frame_dir / "frame_%05d.png"),
        "-c:v", "libx264", "-preset", "fast", "-crf", str(VIDEO_CRF),
        "-pix_fmt", "yuv420p", "-r", str(FPS), str(overlay_vid),
    ], capture_output=True)

    showcase = FINAL_DIR / "showcase.mp4"
    print("Compositing...")
    subprocess.run([
        "ffmpeg", "-y", "-i", str(final_video), "-i", str(overlay_vid),
        "-filter_complex",
        "[1:v]colorkey=0xFF00FF:0.3:0.2[ov];[0:v][ov]overlay=0:0:shortest=1[v]",
        "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", str(VIDEO_CRF),
        "-c:a", "copy", str(showcase),
    ], capture_output=True)

    dur = get_duration(str(showcase))
    print(f"\n{'='*50}")
    print(f"DONE: {showcase} ({dur:.1f}s)")
    print(f"{'='*50}")


# ============================================================
# Effects builder
# ============================================================

def _build_fx(dur, clip_idx, position):
    filters = []

    # Zoom/movement
    move = random.choice(["zoom_in", "zoom_out", "zoom_in_fast", "center_zoom_in",
                           "center_zoom_out", "center_zoom_punch", "shake"])
    f = random.choice([1.15, 1.2, 1.25])
    w, h = int(1920 * f), int(1080 * f)
    ew, eh = w - 1920, h - 1080

    if move == "zoom_in":
        filters.append(f"scale={w}:{h},crop=1920:1080:'{ew//2}*t/{dur}':'{eh//2}*t/{dur}'")
    elif move == "zoom_out":
        filters.append(f"scale={w}:{h},crop=1920:1080:'{ew}-{ew//2}*t/{dur}':'{eh}-{eh//2}*t/{dur}'")
    elif move == "zoom_in_fast":
        filters.append(f"scale={w}:{h},crop=1920:1080:'{ew//2}*min(t*3/{dur},1)':'{eh//2}*min(t*3/{dur},1)'")
    elif move == "center_zoom_in":
        extra = int(400 * (f - 1) / 0.25)
        extra_h = int(225 * (f - 1) / 0.25)
        filters.append(
            f"scale={w}:{h},"
            f"crop='min(1920+{extra}*(1-t/{dur})\\,iw)':'min(1080+{extra_h}*(1-t/{dur})\\,ih)':"
            f"'(iw-ow)/2':'(ih-oh)/2',scale=1920:1080"
        )
    elif move == "center_zoom_out":
        extra = int(400 * (f - 1) / 0.25)
        extra_h = int(225 * (f - 1) / 0.25)
        filters.append(
            f"scale={w}:{h},"
            f"crop='min(1920+{extra}*t/{dur}\\,iw)':'min(1080+{extra_h}*t/{dur}\\,ih)':"
            f"'(iw-ow)/2':'(ih-oh)/2',scale=1920:1080"
        )
    elif move == "center_zoom_punch":
        filters.append(
            f"scale={int(1920*1.3)}:{int(1080*1.3)},"
            f"crop='min(1920+480*max(1-t*6/{dur}\\,0)\\,iw)':'min(1080+270*max(1-t*6/{dur}\\,0)\\,ih)':"
            f"'(iw-ow)/2':'(ih-oh)/2',scale=1920:1080"
        )
    elif move == "shake":
        filters.append(
            "crop=w=in_w-30:h=in_h-30:"
            "x='15+8*sin(n*0.7)':y='15+8*cos(n*0.9)',scale=1920:1080"
        )

    # Flashes (moderate)
    if position < 0.1:
        filters.append("eq=brightness=0.5:enable='lt(t,0.06)'")
    elif 0.7 < position < 0.9:
        filters.append("eq=brightness=0.5:enable='lt(t,0.06)'")
        filters.append(f"eq=brightness=0.5:enable='gt(t,{max(dur-0.06,0)})'")
    elif position > 0.9:
        filters.append(f"eq=brightness=0.5:enable='gt(t,{max(dur-0.06,0)})'")
    else:
        fl = random.choice(["both", "single", "single", "none"])
        if fl == "both":
            filters.append("eq=brightness=0.5:enable='lt(t,0.06)'")
            filters.append(f"eq=brightness=0.5:enable='gt(t,{max(dur-0.06,0)})'")
        elif fl == "single":
            filters.append("eq=brightness=0.5:enable='lt(t,0.06)'")

    # B&W snap every 4th
    if clip_idx % 4 == 0:
        snap = random.uniform(0, max(dur - 0.08, 0.01))
        filters.append(f"hue=s=0:enable='between(t,{snap},{snap+0.06})'")

    # Negate every 5th
    if clip_idx % 5 == 0:
        snap = random.uniform(0, max(dur - 0.12, 0.01))
        filters.append(f"negate=enable='between(t,{snap},{snap+0.1})'")

    # Color effects (20%)
    if random.random() < 0.2:
        filters.append("colorbalance=rs=0.3:gs=-0.1:bs=-0.2")

    # Contrast pop (30%)
    if random.random() < 0.3:
        filters.append("eq=contrast=1.2:saturation=1.3")

    return ",".join(filters)


# ============================================================
# Selector helpers
# ============================================================

def cmd_select(html_file):
    import http.server
    import socketserver
    port = 8888
    print(f"Open http://localhost:{port}/{html_file}")
    print("Press Ctrl+C when done\n")
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nDone.")


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "character":
        cmd_character()
    elif cmd == "frames":
        cmd_frames()
    elif cmd == "select-frames":
        cmd_select("frame_selector.html")
    elif cmd == "videos":
        cmd_videos()
    elif cmd == "select-videos":
        cmd_select("video_selector.html")
    elif cmd == "redo":
        if len(sys.argv) < 3:
            print("Usage: python pipeline.py redo 3,9,13")
            sys.exit(1)
        cmd_redo(sys.argv[2])
    elif cmd == "select-redo":
        cmd_select("video_selector.html")
    elif cmd == "assemble":
        cmd_assemble()
    elif cmd == "overlay":
        cmd_overlay()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
