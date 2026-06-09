#!/usr/bin/env python3
"""
组装《差一步》最终视频 v2
修复zoompan表达式，使用on(帧号)替代t
"""
import subprocess
import os
from PIL import Image, ImageDraw, ImageFont

BASE = "/Users/z/CodeBuddy/wechat/douyin-video"
IMG_DIR = f"{BASE}/images"
AUDIO_DIR = f"{BASE}/audio"
OUTPUT = f"{BASE}/output"
TEMP = f"{BASE}/temp"
os.makedirs(OUTPUT, exist_ok=True)
os.makedirs(TEMP, exist_ok=True)

FPS = 30

def get_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())

def run_cmd(cmd, desc=""):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️  {desc} 有问题: {result.stderr[-200:]}")
    return result.returncode == 0

# ============ 片头片尾 ============
def create_card(text, subtitle="", filename="card"):
    img = Image.new("RGB", (1920, 1080))
    draw = ImageDraw.Draw(img)
    for y in range(1080):
        r = int(20 + 30 * y / 1080)
        g = int(20 + 25 * y / 1080)
        b = int(35 + 40 * y / 1080)
        draw.line([(0, y), (1920, y)], fill=(r, g, b))
    
    fonts = ["/System/Library/Fonts/STHeiti Light.ttc", "/System/Library/Fonts/PingFang.ttc"]
    for f in fonts:
        if os.path.exists(f):
            font_big = ImageFont.truetype(f, 80)
            font_small = ImageFont.truetype(f, 36)
            break
    
    bbox = draw.textbbox((0, 0), text, font=font_big)
    draw.text(((1920-(bbox[2]-bbox[0]))//2, 400), text, fill=(255, 230, 180), font=font_big)
    draw.line([(600, 500), (1320, 500)], fill=(255, 230, 180), width=1)
    
    if subtitle:
        bbox2 = draw.textbbox((0, 0), subtitle, font=font_small)
        draw.text(((1920-(bbox2[2]-bbox2[0]))//2, 520), subtitle, fill=(180, 180, 200), font=font_small)
    
    path = f"{TEMP}/{filename}.png"
    img.save(path)
    return path

title_img = create_card("差一步", "——所有的错过，都是为了刚刚好", "title")
end_img = create_card("完", "AI创作 · 拾光故事馆", "end")

# ============ 场景配置 ============
scenes = [
    {"img": f"{IMG_DIR}/scene1.png", "audio": f"{AUDIO_DIR}/scene1.mp3"},
    {"img": f"{IMG_DIR}/scene2.png", "audio": f"{AUDIO_DIR}/scene2.mp3"},
    {"img": f"{IMG_DIR}/scene3.png", "audio": f"{AUDIO_DIR}/scene3.mp3"},
    {"img": f"{IMG_DIR}/scene4.png", "audio": f"{AUDIO_DIR}/scene4.mp4"},
    {"img": f"{IMG_DIR}/scene5.png", "audio": f"{AUDIO_DIR}/scene5.mp3"},
    {"img": f"{IMG_DIR}/scene6.png", "audio": f"{AUDIO_DIR}/scene6.mp3"},
]
# fix scene4 audio path
scenes[3]["audio"] = f"{AUDIO_DIR}/scene4.mp3"

# 获取音频时长
for s in scenes:
    s["dur"] = get_duration(s["audio"])
    s["clip_dur"] = s["dur"] + 1.0  # 额外1秒留白
    s["frames"] = int(s["clip_dur"] * FPS)

print("📊 场景时长:")
for i, s in enumerate(scenes):
    print(f"  场景{i+1}: 音频{s['dur']:.1f}s -> 片段{s['clip_dur']:.1f}s ({s['frames']}帧)")

title_dur = 3.0
end_dur = 3.0

# ============ 生成视频片段 ============
# Ken Burns效果：缓慢zoom + 微移
zoom_configs = [
    {"z": "min(zoom+0.0008,1.25)", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},  # 缓慢zoom in居中
    {"z": "if(lte(zoom,1.0),1.25,max(1.001,zoom-0.0008))", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},  # 缓慢zoom out
    {"z": "min(zoom+0.0006,1.2)", "x": "iw/2-(iw/zoom/2)", "y": "ih/3-(ih/zoom/2)"},  # zoom in偏上
    {"z": "if(lte(zoom,1.0),1.2,max(1.001,zoom-0.0006))", "x": "iw/3-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},  # zoom out偏左
    {"z": "min(zoom+0.001,1.3)", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},  # 较快zoom in
    {"z": "if(lte(zoom,1.0),1.2,max(1.001,zoom-0.0008))", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"},  # zoom out居中
]

# 片头
print("\n🎬 生成片头...")
run_cmd([
    "ffmpeg", "-y", "-loop", "1", "-i", title_img,
    "-vf", f"zoompan=z='min(zoom+0.0005,1.1)':d={int(title_dur*FPS)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps={FPS}",
    "-t", str(title_dur), "-c:v", "libx264", "-pix_fmt", "yuv420p",
    f"{TEMP}/title.mp4"
], "片头")

# 各场景
for i, scene in enumerate(scenes):
    print(f"🎬 生成场景{i+1}...")
    zc = zoom_configs[i]
    vf = f"scale=1920:1080,zoompan=z='{zc['z']}':d={scene['frames']}:x='{zc['x']}':y='{zc['y']}':s=1920x1080:fps={FPS}"
    ok = run_cmd([
        "ffmpeg", "-y", "-loop", "1", "-i", scene["img"],
        "-i", scene["audio"],
        "-vf", vf,
        "-t", str(scene["clip_dur"]),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-shortest",
        f"{TEMP}/scene{i+1}.mp4"
    ], f"场景{i+1}")
    
    # 验证
    actual_dur = get_duration(f"{TEMP}/scene{i+1}.mp4") if os.path.exists(f"{TEMP}/scene{i+1}.mp4") else 0
    print(f"  {'✅' if actual_dur > 0 else '❌'} 场景{i+1}: {actual_dur:.1f}s")

# 片尾
print("🎬 生成片尾...")
run_cmd([
    "ffmpeg", "-y", "-loop", "1", "-i", end_img,
    "-vf", f"zoompan=z='min(zoom+0.0005,1.1)':d={int(end_dur*FPS)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps={FPS}",
    "-t", str(end_dur), "-c:v", "libx264", "-pix_fmt", "yuv420p",
    f"{TEMP}/end.mp4"
], "片尾")

# ============ 拼接 ============
print("\n🔗 拼接视频...")
concat_list = f"{TEMP}/concat.txt"
with open(concat_list, "w") as f:
    f.write("file 'title.mp4'\n")
    for i in range(6):
        f.write(f"file 'scene{i+1}.mp4'\n")
    f.write("file 'end.mp4'\n")

# 拼接（所有片段已有音频）
final_output = f"{OUTPUT}/差一步.mp4"
result = subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
    "-c:v", "libx264", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "128k",
    final_output
], capture_output=True, text=True)

if result.returncode == 0:
    dur = get_duration(final_output)
    size = os.path.getsize(final_output) / (1024*1024)
    print(f"\n🎉 视频制作完成！")
    print(f"📁 文件: {final_output}")
    print(f"⏱  时长: {dur:.1f}秒")
    print(f"📦 大小: {size:.1f}MB")
    print(f"🖥  分辨率: 1920x1080")
else:
    print(f"❌ 拼接失败: {result.stderr[-300:]}")
