#!/usr/bin/env python3
"""
组装《差一步》最终视频
- 片头标题卡
- 6个场景 + Ken Burns效果
- 交叉淡入淡出
- 旁白音频
- 片尾
"""
import subprocess
import os
import json

BASE = "/Users/z/CodeBuddy/wechat/douyin-video"
IMG_DIR = f"{BASE}/images"
AUDIO_DIR = f"{BASE}/audio"
OUTPUT = f"{BASE}/output"
TEMP = f"{BASE}/temp"
os.makedirs(OUTPUT, exist_ok=True)
os.makedirs(TEMP, exist_ok=True)

# 场景配置：图片、音频、持续时间
scenes = [
    {"img": f"{IMG_DIR}/scene1.png", "audio": f"{AUDIO_DIR}/scene1.mp3", "title": ""},
    {"img": f"{IMG_DIR}/scene2.png", "audio": f"{AUDIO_DIR}/scene2.mp3", "title": ""},
    {"img": f"{IMG_DIR}/scene3.png", "audio": f"{AUDIO_DIR}/scene3.mp3", "title": ""},
    {"img": f"{IMG_DIR}/scene4.png", "audio": f"{AUDIO_DIR}/scene4.mp3", "title": ""},
    {"img": f"{IMG_DIR}/scene5.png", "audio": f"{AUDIO_DIR}/scene5.mp3", "title": ""},
    {"img": f"{IMG_DIR}/scene6.png", "audio": f"{AUDIO_DIR}/scene6.mp3", "title": ""},
]

# 获取每段音频时长
def get_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())

# Step 1: 生成片头标题卡（用Python/Pillow）
from PIL import Image, ImageDraw, ImageFont
import os

def create_title_card():
    img = Image.new("RGB", (1920, 1080), (20, 20, 35))
    draw = ImageDraw.Draw(img)
    
    # 渐变背景
    for y in range(1080):
        ratio = y / 1080
        r = int(20 + 30 * ratio)
        g = int(20 + 25 * ratio)
        b = int(35 + 40 * ratio)
        draw.line([(0, y), (1920, y)], fill=(r, g, b))
    
    # 标题
    fonts = [
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    font_big = None
    font_small = None
    for f in fonts:
        if os.path.exists(f):
            font_big = ImageFont.truetype(f, 80)
            font_small = ImageFont.truetype(f, 36)
            break
    
    title = "差一步"
    subtitle = "——所有的错过，都是为了刚刚好"
    
    if font_big:
        bbox = draw.textbbox((0, 0), title, font=font_big)
        tw = bbox[2] - bbox[0]
        draw.text(((1920-tw)//2, 400), title, fill=(255, 230, 180), font=font_big)
    
    if font_small:
        bbox2 = draw.textbbox((0, 0), subtitle, font=font_small)
        tw2 = bbox2[2] - bbox2[0]
        draw.text(((1920-tw2)//2, 520), subtitle, fill=(180, 180, 200), font=font_small)
    
    # 装饰线条
    draw.line([(600, 500), (1320, 500)], fill=(255, 230, 180), width=1)
    
    img.save(f"{TEMP}/title.png")
    return f"{TEMP}/title.png"

def create_end_card():
    img = Image.new("RGB", (1920, 1080), (20, 20, 35))
    draw = ImageDraw.Draw(img)
    
    for y in range(1080):
        ratio = y / 1080
        r = int(20 + 30 * ratio)
        g = int(20 + 25 * ratio)
        b = int(35 + 40 * ratio)
        draw.line([(0, y), (1920, y)], fill=(r, g, b))
    
    fonts = ["/System/Library/Fonts/STHeiti Light.ttc", "/System/Library/Fonts/PingFang.ttc"]
    for f in fonts:
        if os.path.exists(f):
            font = ImageFont.truetype(f, 48)
            font_small = ImageFont.truetype(f, 28)
            break
    
    text = "完"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((1920-tw)//2, 450), text, fill=(255, 230, 180), font=font)
    
    credit = "AI创作 · 拾光故事馆"
    bbox2 = draw.textbbox((0, 0), credit, font=font_small)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((1920-tw2)//2, 550), credit, fill=(150, 150, 170), font=font_small)
    
    img.save(f"{TEMP}/end.png")
    return f"{TEMP}/end.png"

# 生成片头片尾
title_img = create_title_card()
end_img = create_end_card()

# 获取每段音频时长
durations = []
for s in scenes:
    d = get_duration(s["audio"])
    durations.append(d + 1.0)  # 额外1秒留白
    print(f"  场景{scenes.index(s)+1}: {d:.1f}s audio -> {d+1.0:.1f}s clip")

# 片头3秒，片尾3秒
title_dur = 3.0
end_dur = 3.0

# Step 2: 为每个场景生成带Ken Burns效果的视频片段
# 交替使用zoom-in和zoom-out + 不同的pan方向
zoom_effects = [
    "zoompan=z='min(zoom+0.001,1.3)':d={dur}:x='iw/2-(iw/zoom/2)+10*t':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30",
    "zoompan=z='if(lte(zoom,1.0),1.3,max(1.00,zoom-0.001))':d={dur}:x='iw/2-(iw/zoom/2)-5*t':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30",
    "zoompan=z='min(zoom+0.0008,1.2)':d={dur}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)+8*t':s=1920x1080:fps=30",
    "zoompan=z='if(lte(zoom,1.0),1.25,max(1.00,zoom-0.001))':d={dur}:x='iw/2-(iw/zoom/2)+5*t':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30",
    "zoompan=z='min(zoom+0.001,1.3)':d={dur}:x='iw/2-(iw/zoom/2)-8*t':y='ih/2-(ih/zoom/2)+5*t':s=1920x1080:fps=30",
    "zoompan=z='if(lte(zoom,1.0),1.2,max(1.00,zoom-0.0008))':d={dur}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)-5*t':s=1920x1080:fps=30",
]

# 生成片头视频
print("\n🎬 生成片头...")
subprocess.run([
    "ffmpeg", "-y", "-loop", "1", "-i", title_img,
    "-vf", f"zoompan=z='min(zoom+0.0005,1.1)':d={int(title_dur*30)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30",
    "-t", str(title_dur), "-c:v", "libx264", "-pix_fmt", "yuv420p",
    f"{TEMP}/title.mp4"
], capture_output=True)

# 生成每个场景片段
for i, scene in enumerate(scenes):
    print(f"🎬 生成场景{i+1}视频片段...")
    dur_frames = int(durations[i] * 30)
    vf = zoom_effects[i].format(dur=dur_frames)
    
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", scene["img"],
        "-i", scene["audio"],
        "-vf", vf,
        "-t", str(durations[i]),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        f"{TEMP}/scene{i+1}.mp4"
    ], capture_output=True)
    print(f"  ✅ 场景{i+1} 完成")

# 生成片尾视频
print("🎬 生成片尾...")
subprocess.run([
    "ffmpeg", "-y", "-loop", "1", "-i", end_img,
    "-vf", f"zoompan=z='min(zoom+0.0005,1.1)':d={int(end_dur*30)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30",
    "-t", str(end_dur), "-c:v", "libx264", "-pix_fmt", "yuv420p",
    f"{TEMP}/end.mp4"
], capture_output=True)

# Step 3: 创建concat列表
print("\n🔗 拼接视频...")
concat_list = f"{TEMP}/concat.txt"
with open(concat_list, "w") as f:
    f.write(f"file 'title.mp4'\n")
    for i in range(6):
        f.write(f"file 'scene{i+1}.mp4'\n")
    f.write(f"file 'end.mp4'\n")

# 先拼接无音频版本
subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
    "-c:v", "libx264", "-pix_fmt", "yuv420p",
    f"{TEMP}/video_only.mp4"
], capture_output=True)

# Step 4: 添加整体音频（混合所有旁白，加上静音填充）
print("🎵 合成音频轨道...")

# 创建音频concat列表（带静音间隔）
audio_concat = f"{TEMP}/audio_concat.txt"
with open(audio_concat, "w") as f:
    # 片头静音3秒
    f.write(f"file '{TEMP}/silence_title.mp3'\n")
    for i in range(6):
        f.write(f"file '{AUDIO_DIR}/scene{i+1}.mp3'\n")
        f.write(f"file '{TEMP}/silence{i+1}.mp3'\n")
    # 片尾静音3秒
    f.write(f"file '{TEMP}/silence_end.mp3'\n")

# 生成静音片段
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", 
                "-t", "3", "-c:a", "libmp3lame", f"{TEMP}/silence_title.mp3"], capture_output=True)
for i in range(6):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", "1", "-c:a", "libmp3lame", f"{TEMP}/silence{i+1}.mp3"], capture_output=True)
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", "3", "-c:a", "libmp3lame", f"{TEMP}/silence_end.mp3"], capture_output=True)

# 拼接音频
subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", audio_concat,
    "-c:a", "aac", "-b:a", "128k",
    f"{TEMP}/full_audio.m4a"
], capture_output=True)

# Step 5: 合并视频和音频
print("🎬 合并最终视频...")
final_output = f"{OUTPUT}/差一步.mp4"
result = subprocess.run([
    "ffmpeg", "-y",
    "-i", f"{TEMP}/video_only.mp4",
    "-i", f"{TEMP}/full_audio.m4a",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
    "-shortest",
    final_output
], capture_output=True, text=True)

if result.returncode == 0:
    # 获取最终时长
    dur = get_duration(final_output)
    size = os.path.getsize(final_output) / (1024*1024)
    print(f"\n🎉 视频制作完成！")
    print(f"📁 文件: {final_output}")
    print(f"⏱  时长: {dur:.1f}秒")
    print(f"📦 大小: {size:.1f}MB")
else:
    print(f"❌ 错误: {result.stderr}")
