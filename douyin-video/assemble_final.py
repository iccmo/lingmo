#!/usr/bin/env python3
"""最终版：加长场景间隔到刚好~60秒"""
import subprocess, os

BASE = "/Users/z/CodeBuddy/wechat/douyin-video"
TEMP = f"{BASE}/temp"
OUTPUT = f"{BASE}/output"
AUDIO_DIR = f"{BASE}/audio"

def get_duration(path):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",path], capture_output=True, text=True)
    return float(r.stdout.strip())

# 给每个场景片段追加静音，使每段达到目标时长
# 目标: 片头3s + 6场景(~52s) + 片尾3s = ~58s，再微调
target_scene_durs = [12, 10, 11, 9.5, 7.5, 6.5]  # 总计56.5 + 3+3 = 62.5s，略超，微调

# 实际用：每段音频时长 + 2.5秒静音
for i in range(1, 7):
    audio = f"{AUDIO_DIR}/scene{i}.mp3"
    audio_dur = get_duration(audio)
    silence_dur = 2.0  # 每段加2秒静音
    total_dur = audio_dur + silence_dur
    frames = int(total_dur * 30)
    
    # 生成静音音频
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(silence_dur), "-c:a", "aac", "-b:a", "128k",
        f"{TEMP}/silence_ext{i}.m4a"
    ], capture_output=True)
    
    # 拼接原音频+静音
    with open(f"{TEMP}/audio_ext{i}.txt", "w") as f:
        f.write(f"file '{audio}'\n")
        f.write(f"file '{TEMP}/silence_ext{i}.m4a'\n")
    
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", f"{TEMP}/audio_ext{i}.txt",
        "-c:a", "aac", "-b:a", "128k",
        f"{TEMP}/audio_ext{i}.m4a"
    ], capture_output=True)
    
    # 重新生成场景视频（使用扩展音频）
    # 读取已有的zoompan配置
    zoom_configs = [
        {"z": "min(zoom+0.0008,1.25)", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},
        {"z": "if(lte(zoom,1.0),1.25,max(1.001,zoom-0.0008))", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},
        {"z": "min(zoom+0.0006,1.2)", "x": "iw/2-(iw/zoom/2)", "y": "ih/3-(ih/zoom/2)"},
        {"z": "if(lte(zoom,1.0),1.2,max(1.001,zoom-0.0006))", "x": "iw/3-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},
        {"z": "min(zoom+0.001,1.3)", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},
        {"z": "if(lte(zoom,1.0),1.2,max(1.001,zoom-0.0008))", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},
    ]
    zc = zoom_configs[i-1]
    vf = f"scale=1920:1080,zoompan=z='{zc['z']}':d={frames}:x='{zc['x']}':y='{zc['y']}':s=1920x1080:fps=30"
    
    img = f"{BASE}/images/scene{i}.png"
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", img,
        "-i", f"{TEMP}/audio_ext{i}.m4a",
        "-vf", vf,
        "-t", str(total_dur),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        f"{TEMP}/scene{i}.mp4"
    ], capture_output=True)
    
    actual = get_duration(f"{TEMP}/scene{i}.mp4") if os.path.exists(f"{TEMP}/scene{i}.mp4") else 0
    print(f"  场景{i}: 音频{audio_dur:.1f}s + 静音{silence_dur:.1f}s = {actual:.1f}s")

# 拼接最终视频
concat_list = f"{TEMP}/concat.txt"
with open(concat_list, "w") as f:
    f.write("file 'title.mp4'\n")
    for i in range(1, 7):
        f.write(f"file 'scene{i}.mp4'\n")
    f.write("file 'end.mp4'\n")

final = f"{OUTPUT}/差一步.mp4"
r = subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
    "-c:v", "libx264", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "128k",
    final
], capture_output=True, text=True)

if r.returncode == 0:
    dur = get_duration(final)
    size = os.path.getsize(final) / (1024*1024)
    print(f"\n🎉 最终视频完成！")
    print(f"📁 {final}")
    print(f"⏱  {dur:.1f}秒 | 📦 {size:.1f}MB | 🖥  1920x1080")
else:
    print(f"❌ {r.stderr[-200:]}")
