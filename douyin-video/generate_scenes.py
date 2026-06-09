#!/usr/bin/env python3
"""
生成《差一步》6个场景的艺术风格插图
使用 Pillow 创建水彩风格的场景图
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math
import random
import os

W, H = 1920, 1080
OUTPUT = "/Users/z/CodeBuddy/wechat/douyin-video/images"
os.makedirs(OUTPUT, exist_ok=True)

# 尝试加载中文字体
def get_font(size):
    fonts = [
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ]
    for f in fonts:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()

def gradient(draw, w, h, c1, c2, vertical=True):
    """绘制渐变背景"""
    for i in range(h if vertical else w):
        ratio = i / (h if vertical else w)
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        if vertical:
            draw.line([(0, i), (w, i)], fill=(r, g, b))
        else:
            draw.line([(i, 0), (i, h)], fill=(r, g, b))

def add_noise_overlay(img, intensity=15):
    """添加噪点纹理模拟水彩质感"""
    noise = Image.new("RGB", img.size)
    pixels = noise.load()
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            v = random.randint(-intensity, intensity)
            pixels[x, y] = (128 + v, 128 + v, 128 + v)
    return Image.blend(img, noise, 0.05)

def draw_building(draw, x, y, w, h, color, windows=True):
    """绘制简化的建筑"""
    draw.rectangle([x, y, x+w, y+h], fill=color)
    # 屋顶
    draw.polygon([(x-10, y), (x+w//2, y-30), (x+w+10, y)], fill=color)
    if windows:
        for row in range(3):
            for col in range(w // 60):
                wx = x + 15 + col * 60
                wy = y + 20 + row * 50
                if wx + 30 < x + w and wy + 25 < y + h:
                    draw.rectangle([wx, wy, wx+30, wy+25], fill=(255, 255, 200, 180))

def draw_tree(draw, x, y, size=1, autumn=False):
    """绘制树木"""
    trunk_color = (120, 80, 50)
    draw.rectangle([x-8*size, y, x+8*size, y+60*size], fill=trunk_color)
    colors = [(45, 120, 45), (55, 140, 55), (65, 130, 45)]
    if autumn:
        colors = [(200, 120, 40), (220, 150, 50), (180, 100, 30), (230, 80, 40)]
    for i, c in enumerate(colors):
        cx = x + random.randint(-15, 15) * size
        cy = y - 20 * size - i * 25 * size
        r = (35 + i * 10) * size
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=c)

def draw_person(draw, x, y, color, direction=1, scale=1.0):
    """绘制简约人物轮廓"""
    s = scale
    # 头
    draw.ellipse([x-12*s, y-60*s, x+12*s, y-36*s], fill=color)
    # 身体
    draw.rectangle([x-10*s, y-36*s, x+10*s, y+10*s], fill=color)
    # 腿
    draw.line([(x-5*s, y+10*s), (x-10*s, y+40*s)], fill=color, width=int(4*s))
    draw.line([(x+5*s, y+10*s), (x+10*s, y+40*s)], fill=color, width=int(4*s))
    # 手臂
    arm = 12 * direction
    draw.line([(x, y-25*s), (x+arm*s, y-10*s)], fill=color, width=int(3*s))

def draw_rain(draw, w, h, density=200):
    """绘制雨丝"""
    for _ in range(density):
        x = random.randint(0, w)
        y = random.randint(0, h)
        length = random.randint(15, 40)
        draw.line([(x, y), (x-3, y+length)], fill=(180, 200, 220, 100), width=1)

def draw_leaves(draw, w, h, count=30):
    """绘制飘落的叶子"""
    colors = [(200, 120, 40), (220, 150, 50), (180, 100, 30), (230, 80, 40), (160, 90, 25)]
    for _ in range(count):
        x = random.randint(0, w)
        y = random.randint(0, h)
        c = random.choice(colors)
        size = random.randint(4, 10)
        draw.ellipse([x, y, x+size*2, y+size], fill=c)

def draw_stars(draw, w, h, count=50):
    """绘制星星/光点"""
    for _ in range(count):
        x = random.randint(0, w)
        y = random.randint(0, h//2)
        s = random.randint(1, 3)
        brightness = random.randint(180, 255)
        draw.ellipse([x-s, y-s, x+s, y+s], fill=(brightness, brightness, brightness))

def draw_lamppost(draw, x, y):
    """绘制路灯"""
    draw.rectangle([x-4, y, x+4, y+150], fill=(60, 60, 70))
    draw.ellipse([x-20, y-15, x+20, y+15], fill=(255, 230, 150))
    # 灯光效果
    for r in range(80, 0, -5):
        alpha = max(0, 40 - r // 2)
        draw.ellipse([x-r, y-r+5, x+r, y+r+5], fill=(255, 240, 180))

def add_subtitle(img, text, position="bottom"):
    """添加字幕"""
    draw = ImageDraw.Draw(img)
    font = get_font(42)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    y = H - 120 if position == "bottom" else 60
    # 半透明背景
    padding = 20
    draw.rounded_rectangle([x-padding, y-padding, x+tw+padding, y+60], 
                          radius=10, fill=(0, 0, 0, 160))
    draw.text((x, y), text, fill=(255, 255, 255), font=font)
    return img

# ============ 场景1：清晨咖啡店 ============
def scene1():
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    # 清晨暖色调渐变
    gradient(draw, W, H, (255, 200, 140), (180, 140, 100))
    
    # 地面
    draw.rectangle([0, H*2//3, W, H], fill=(160, 130, 100))
    
    # 咖啡店建筑
    draw.rectangle([W//3, H//4, W*2//3, H*2//3], fill=(180, 140, 100))
    draw.rectangle([W//3-10, H//4, W*2//3+10, H//4+20], fill=(140, 100, 70))
    
    # 招牌
    draw.rounded_rectangle([W//2-100, H//4+30, W//2+100, H//4+80], radius=8, fill=(80, 50, 30))
    font = get_font(28)
    draw.text((W//2-60, H//4+38), "拾光咖啡", fill=(255, 230, 180), font=font)
    
    # 前门（左边）
    draw.rectangle([W//3+30, H//2, W//3+100, H*2//3], fill=(100, 70, 40))
    draw.ellipse([W//3+85, H//2+40, W//3+95, H//2+50], fill=(200, 180, 100))
    
    # 后门（右边）
    draw.rectangle([W*2//3-100, H//2, W*2//3-30, H*2//3], fill=(100, 70, 40))
    draw.ellipse([W*2//3-95, H//2+40, W*2//3-85, H//2+50], fill=(200, 180, 100))
    
    # 窗户
    for i in range(3):
        wx = W//3 + 120 + i * 100
        draw.rectangle([wx, H//3+20, wx+60, H//3+70], fill=(255, 250, 200))
    
    # 男孩（正要进前门）
    draw_person(draw, W//3+65, H*2//3-50, (60, 80, 140), direction=1, scale=1.2)
    
    # 女孩（从后门离开）
    draw_person(draw, W*2//3-65, H*2//3-50, (180, 80, 100), direction=-1, scale=1.2)
    
    # 晨光效果
    for r in range(200, 0, -10):
        alpha = max(0, 20 - r // 10)
        draw.ellipse([W-300-r, -200-r, W-300+r, -200+r], fill=(255, 240, 200))
    
    img = add_noise_overlay(img)
    img = img.filter(ImageFilter.GaussianBlur(1))
    img = add_subtitle(img, "每天早上八点十五，他们出现在同一家咖啡店")
    img.save(f"{OUTPUT}/scene1.png")
    print("✅ 场景1 完成")

# ============ 场景2：地铁站 ============
def scene2():
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    # 地铁站冷色调
    gradient(draw, W, H, (60, 70, 100), (30, 35, 60))
    
    # 站台
    draw.rectangle([0, H*2//3, W, H], fill=(80, 85, 95))
    draw.rectangle([0, H*2//3, W, H*2//3+5], fill=(200, 200, 50))  # 安全线
    
    # 轨道
    draw.rectangle([0, H*3//4, W, H*3//4+8], fill=(100, 100, 110))
    draw.rectangle([0, H*3//4+30, W, H*3//4+38], fill=(100, 100, 110))
    
    # 对面站台
    draw.rectangle([0, H*3//4+60, W, H], fill=(70, 75, 85))
    
    # 列车（中间）
    draw.rounded_rectangle([W//6, H//2+20, W*5//6, H*2//3+10], radius=15, fill=(200, 200, 210))
    for i in range(6):
        wx = W//6 + 40 + i * 180
        draw.rectangle([wx, H//2+40, wx+120, H//2+90], fill=(150, 200, 255))
    
    # 男孩（左边站台）
    draw_person(draw, W//4, H*2//3-50, (60, 80, 140), direction=1, scale=1.3)
    
    # 女孩（右边，透过车窗）
    draw_person(draw, W*3//4, H*2//3-50, (180, 80, 100), direction=-1, scale=1.3)
    
    # 车窗透过的对视光线
    draw.line([(W//4+20, H//2+50), (W*3//4-20, H//2+50)], fill=(255, 255, 200), width=2)
    
    # 灯光效果
    for i in range(8):
        x = W//6 + 60 + i * 160
        draw.ellipse([x-15, H//4, x+15, H//4+10], fill=(255, 255, 220))
    
    img = add_noise_overlay(img)
    img = img.filter(ImageFilter.GaussianBlur(1))
    img = add_subtitle(img, "他们坐同一趟地铁，却总是相反的方向")
    img.save(f"{OUTPUT}/scene2.png")
    print("✅ 场景2 完成")

# ============ 场景3：公园长椅 ============
def scene3():
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    # 秋天暖色调
    gradient(draw, W, H, (200, 170, 120), (140, 120, 80))
    
    # 草地
    draw.rectangle([0, H*3//5, W, H], fill=(120, 140, 70))
    
    # 远处的树
    for i in range(6):
        x = 100 + i * 300 + random.randint(-30, 30)
        draw_tree(draw, x, H*3//5-20, size=1.5, autumn=True)
    
    # 小路
    for y in range(H*3//5, H, 3):
        x_center = W//2 + math.sin(y * 0.01) * 50
        draw.rectangle([x_center-40, y, x_center+40, y+3], fill=(180, 160, 120))
    
    # 长椅
    bx, by = W//3, H*3//5 + 40
    draw.rectangle([bx, by, bx+200, by+10], fill=(100, 70, 40))
    draw.rectangle([bx+10, by+10, bx+30, by+50], fill=(80, 55, 30))
    draw.rectangle([bx+170, by+10, bx+190, by+50], fill=(80, 55, 30))
    draw.rectangle([bx-10, by-60, bx+10, by], fill=(100, 70, 40))
    draw.rectangle([bx+190, by-60, bx+210, by], fill=(100, 70, 40))
    draw.rectangle([bx-10, by-60, bx+210, by-50], fill=(100, 70, 40))
    
    # 男孩坐在长椅上看书
    draw_person(draw, bx+100, by-10, (60, 80, 140), direction=0, scale=1.2)
    # 书
    draw.rectangle([bx+80, by-35, bx+120, by-15], fill=(200, 180, 140))
    
    # 女孩远处走过
    draw_person(draw, W*3//4, H*3//5+20, (180, 80, 100), direction=1, scale=1.0)
    
    # 飘落的叶子
    draw_leaves(draw, W, H, count=50)
    
    # 阳光
    for r in range(150, 0, -10):
        draw.ellipse([100-r, 50-r, 100+r, 50+r], fill=(255, 240, 180))
    
    img = add_noise_overlay(img)
    img = img.filter(ImageFilter.GaussianBlur(1))
    img = add_subtitle(img, "他看的是她昨天读过的那本书")
    img.save(f"{OUTPUT}/scene3.png")
    print("✅ 场景3 完成")

# ============ 场景4：书店 ============
def scene4():
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    # 温暖的室内色调
    gradient(draw, W, H, (220, 200, 170), (180, 160, 130))
    
    # 书架
    for shelf in range(4):
        y = 100 + shelf * 200
        draw.rectangle([50, y, W-50, y+15], fill=(120, 80, 50))
        # 书
        x = 60
        while x < W - 80:
            bw = random.randint(15, 35)
            bh = random.randint(60, 120)
            c = random.choice([(180, 50, 50), (50, 80, 150), (50, 130, 70), (180, 140, 40), (140, 60, 120)])
            draw.rectangle([x, y-bh, x+bw, y], fill=c)
            x += bw + 2
    
    # 中间聚焦的书
    book_x, book_y = W//2, H//2 - 50
    draw.rectangle([book_x-20, book_y-40, book_x+20, book_y+40], fill=(180, 50, 50))
    draw.rectangle([book_x-18, book_y-38, book_x+18, book_y+38], fill=(220, 180, 140))
    
    # 男孩的手（左边伸出）
    draw.line([(W//2-150, H//2+50), (book_x-25, book_y)], fill=(220, 190, 160), width=8)
    draw.ellipse([book_x-35, book_y-10, book_x-15, book_y+10], fill=(220, 190, 160))
    
    # 女孩的手（右边伸出）
    draw.line([(W//2+150, H//2+50), (book_x+25, book_y)], fill=(230, 200, 170), width=8)
    draw.ellipse([book_x+15, book_y-10, book_x+35, book_y+10], fill=(230, 200, 170))
    
    # 电话图标（暗示打断）
    phone_x, phone_y = W//2+200, H//2+80
    draw.rounded_rectangle([phone_x-25, phone_y-15, phone_x+25, phone_y+15], radius=5, fill=(60, 60, 70))
    draw.text((phone_x-15, phone_y-10), "📞", fill=(255, 255, 255))
    
    # 暖色灯光
    for r in range(200, 0, -15):
        draw.ellipse([W//2-r, 50-r//3, W//2+r, 50+r//3], fill=(255, 240, 200))
    
    img = add_noise_overlay(img)
    img = img.filter(ImageFilter.GaussianBlur(1))
    img = add_subtitle(img, "命运安排了一次相遇，却被一个电话打断")
    img.save(f"{OUTPUT}/scene4.png")
    print("✅ 场景4 完成")

# ============ 场景5：大雨 ============
def scene5():
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    # 雨天灰蓝色调
    gradient(draw, W, H, (60, 70, 90), (40, 45, 65))
    
    # 街道
    draw.rectangle([0, H*2//3, W, H], fill=(50, 55, 65))
    
    # 建筑剪影
    for i in range(5):
        x = i * 400
        bh = random.randint(300, 500)
        draw.rectangle([x, H*2//3-bh, x+350, H*2//3], fill=(45, 50, 60))
        # 窗户灯光
        for wy in range(H*2//3-bh+30, H*2//3-30, 50):
            for wx in range(x+20, x+330, 60):
                if random.random() > 0.3:
                    draw.rectangle([wx, wy, wx+30, wy+25], fill=(255, 230, 150))
    
    # 屋檐
    awning_x = W//3
    draw.rectangle([awning_x, H//3, awning_x+300, H//3+10], fill=(80, 60, 50))
    draw.polygon([(awning_x, H//3), (awning_x-20, H//3+40), (awning_x+300, H//3+40), (awning_x+300, H//3)], fill=(100, 70, 50))
    
    # 男孩站在屋檐下
    draw_person(draw, awning_x+100, H*2//3-50, (60, 80, 140), direction=1, scale=1.3)
    # 手机
    draw.rectangle([awning_x+115, H*2//3-120, awning_x+135, H*2//3-80], fill=(200, 200, 210))
    
    # 远处跑来的身影
    draw_person(draw, W*3//4, H*2//3-30, (180, 80, 100), direction=-1, scale=1.1)
    
    # 雨丝
    draw_rain(draw, W, H, density=400)
    
    # 水洼反光
    for i in range(8):
        px = random.randint(100, W-100)
        py = random.randint(H*2//3+20, H-50)
        draw.ellipse([px-30, py-5, px+30, py+5], fill=(80, 100, 130))
    
    img = add_noise_overlay(img)
    img = img.filter(ImageFilter.GaussianBlur(1))
    img = add_subtitle(img, "直到那场大雨，把所有的差一步都淋成了一步")
    img.save(f"{OUTPUT}/scene5.png")
    print("✅ 场景5 完成")

# ============ 场景6：相遇 ============
def scene6():
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    # 雨后暖色调
    gradient(draw, W, H, (80, 90, 120), (50, 55, 80))
    
    # 地面（湿润反光）
    draw.rectangle([0, H*2//3, W, H], fill=(55, 60, 75))
    
    # 建筑
    draw.rectangle([W//4, H//5, W*3//4, H*2//3], fill=(60, 65, 80))
    
    # 屋檐
    draw.rectangle([W//4-30, H//5, W*3//4+30, H//5+15], fill=(80, 60, 50))
    
    # 路灯（暖光）
    draw_lamppost(draw, W//4 - 50, H//3)
    draw_lamppost(draw, W*3//4 + 50, H//3)
    
    # 两人站在屋檐下，面对面
    boy_x = W//2 - 60
    girl_x = W//2 + 60
    person_y = H*2//3 - 50
    
    # 男孩
    draw_person(draw, boy_x, person_y, (60, 80, 140), direction=1, scale=1.4)
    # 女孩（湿透，头发更暗）
    draw_person(draw, girl_x, person_y, (150, 60, 80), direction=-1, scale=1.4)
    
    # 微笑弧线（简笔）
    draw.arc([boy_x-8, person_y-45, boy_x+8, person_y-35], 0, 180, fill=(255, 255, 255), width=2)
    draw.arc([girl_x-8, person_y-45, girl_x+8, person_y-35], 0, 180, fill=(255, 255, 255), width=2)
    
    # 暖光效果（从路灯散射）
    for r in range(250, 0, -10):
        alpha = max(0, 30 - r // 8)
        draw.ellipse([W//4-50-r, H//3-50-r, W//4-50+r, H//3-50+r], fill=(255, 230, 150))
        draw.ellipse([W*3//4+50-r, H//3-50-r, W*3//4+50+r, H//3-50+r], fill=(255, 230, 150))
    
    # 中间的心形光晕
    for r in range(60, 0, -5):
        draw.ellipse([W//2-r, H//2-r, W//2+r, H//2+r], fill=(255, 200, 150))
    
    # 轻微的雨（快停了）
    draw_rain(draw, W, H, density=80)
    
    # 水洼
    for i in range(5):
        px = random.randint(200, W-200)
        py = random.randint(H*2//3+30, H-40)
        draw.ellipse([px-40, py-5, px+40, py+5], fill=(100, 120, 160))
    
    img = add_noise_overlay(img)
    img = img.filter(ImageFilter.GaussianBlur(1))
    img = add_subtitle(img, "原来所有的错过，都是为了这一刻的刚刚好")
    img.save(f"{OUTPUT}/scene6.png")
    print("✅ 场景6 完成")

if __name__ == "__main__":
    random.seed(42)
    scene1()
    scene2()
    scene3()
    scene4()
    scene5()
    scene6()
    print("\n🎬 所有场景图片生成完成！")
    print(f"📁 输出目录: {OUTPUT}")
