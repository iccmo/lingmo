#!/usr/bin/env python3
"""v3: 去掉-shortest，用-t精确控制时长"""
import subprocess, os

BASE = "/Users/z/CodeBuddy/wechat/douyin-video"
TEMP = f"{BASE}/temp"
OUTPUT = f"{BASE}/output"
AUDIO_DIR = f"{BASE}/audio"

def get_duration(path):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",path], capture_output=True, text=True)
    return float(r.stdout.strip())

zoom_configs = [
    {"z": "min(zoom+0.0008,1.25)", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},
    {"z": "if(lte(zoom,1.0),1.25,max(1.001,zoom-0.0008))", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},
    {"z": "min(zoom+0.0006,1.2)", "x": "iw/2-(iw/zoom/2)", "y": "ih/3-(ih/zoom/2)"},
    {"z": "if(lte(zoom,1.0),1.2,max(1.001,zoom-0.0006))", "x": "iw/3-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},
    {"z": "min(zoom+0.001,1.3)", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},
    {"z": "if(lte(zoom,1.0),1.2,max(1.001,zoom-0.0008))", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},
]

extra_silence = 2.0  # 每段额外静音

for i in range(1, 7):
    audio = f"{AUDIO_DIR}/scene{i}.mp3"
    audio_dur = get_duration(audio)
    total_dur = audio_dur + extra_silence
    frames = int(total_dur * 30)
    
    # 生成扩展音频（原音频 + 静音）
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(extra_silence), "-c:a", "aac", "-b:a", "128k",
        f"{TEMP}/sil_ext{i}.m4a"
    ], capture_output=True)
    
    with open(f"{TEMP}/aext{i}.txt", "w") as f:
        f.write(f"file '{audio}'\nfile '{TEMP}/sil_ext{i}.m4a'\n")
    
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", f"{TEMP}/aext{i}.txt",
        "-c:a", "aac", "-b:a", "128k", f"{TEMP}/aext{i}.m4a"
    ], capture_output=True)
    
    # 生成视频片段（不用-shortest，用-t）
    zc = zoom_configs[i-1]
    vf = f"scale=1920:1080,zoompan=z='{zc['z']}':d={frames}:x='{zc['x']}':y='{zc['y']}':s=1920x1080:fps=30"
    
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", f"{BASE}/images/scene{i}.png",
        "-i", f"{TEMP}/aext{i}.m4a",
        "-vf", vf,
        "-t", str(total_dur),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        f"{TEMP}/scene{i}.mp4"
    ], capture_output=True)
    
    actual = get_duration(f"{TEMP}/scene{i}.mp4")
    print(f"  场景{i}: {actual:.1f}s (音频{audio_dur:.1f} + 静音{extra_silence})")

# 拼接
with open(f"{TEMP}/concat.txt", "w") as f:
    f.write("file 'title.mp4'\n")
    for i in range(1, 7):
        f.write(f"file 'scene{i}.mp4'\n")
    f.write("file 'end.mp4'\n")

final = f"{OUTPUT}/差一步.mp4"
r = subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", f"{TEMP}/concat.txt",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
    final
], capture_output=True, text=True)

if r.returncode == 0:
    dur = get_duration(final)
    size = os.path.getsize(final) / (1024*1024)
    print(f"\n🎉 完成！")
    print(f"📁 {final}")
    print(f"⏱  {dur:.1f}秒 | 📦 {size:.1f}MB | 🖥  1920x1080")
else:
    print(f"❌ {r.stderr[-300:]}")
