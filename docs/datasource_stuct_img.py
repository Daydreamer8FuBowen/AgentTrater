from PIL import Image, ImageDraw, ImageFont
import os


# Fallback: search for a font that supports Chinese (also checks a project fonts/ dir)
from pathlib import Path


def find_font():
    candidates = [
        "msyh.ttc",
        "msyh.ttf",
        "simhei.ttf",
        "simsun.ttc",
        "NotoSansSC-Regular.otf",
        "NotoSansCJK-Regular.otf",
    ]
    font_dirs = [
        r"C:\Windows\Fonts",
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        str(Path.home() / ".local" / "share" / "fonts"),
        str(Path.cwd() / "docs" / "fonts"),  # project-local fonts directory
    ]
    for d in font_dirs:
        pdir = Path(d)
        if not pdir.exists():
            continue
        for name in candidates:
            p = pdir / name
            if p.exists():
                return str(p)
    return None


font_path = find_font()

if font_path:
    title = ImageFont.truetype(font_path, 40)
    sub = ImageFont.truetype(font_path, 26)
    body = ImageFont.truetype(font_path, 24)
else:
    # Fallback to Pillow's default font (may not render Chinese correctly)
    title = ImageFont.load_default()
    sub = ImageFont.load_default()
    body = ImageFont.load_default()

def box(d,xy,text,color):
    d.rounded_rectangle(xy,20,fill=color,outline="#333",width=3)
    x1,y1,x2,y2=xy
    d.text((x1+20,y1+20),text,font=body,fill="black")

def arrow(d,a,b):
    d.line([a,b],fill="#333",width=4)

# 图1
img=Image.new("RGB",(1600,900),"white")
d=ImageDraw.Draw(img)
d.text((40,30),"Data Source Routing — Overview",font=title,fill="black")

box(d,(80,250,260,350),"Client","#E3F2FD")
box(d,(350,220,650,380),"Gateway","#E8F5E9")
box(d,(720,220,1020,380),"Selector","#FFF3E0")
box(d,(1100,220,1450,380),"Providers","#FCE4EC")

box(d,(720,500,1020,650),"Priority Storage","#F3E5F5")
box(d,(1100,500,1450,650),"Provider Registry","#F3E5F5")

arrow(d,(260,300),(350,300))
arrow(d,(650,300),(720,300))
arrow(d,(1020,300),(1100,300))
arrow(d,(870,380),(870,500))
arrow(d,(1250,380),(1250,500))

out_dir = Path(__file__).parent
out_dir.mkdir(parents=True, exist_ok=True)

p1 = out_dir / "ppt_overall.png"
img.save(p1)

# 图2
img=Image.new("RGB",(1600,900),"white")
d=ImageDraw.Draw(img)
d.text((40,30),"Request Execution Flow",font=title,fill="black")

box(d,(100,200,300,300),"Client","#E3F2FD")
box(d,(400,200,650,300),"Gateway","#E8F5E9")
box(d,(750,200,1000,300),"Selector","#FFF3E0")
box(d,(1100,200,1400,300),"Provider","#FCE4EC")

arrow(d,(300,250),(400,250))
arrow(d,(650,250),(750,250))
arrow(d,(1000,250),(1100,250))

d.text((300,500),"Success: return immediately\nFailure: try next provider",font=sub,fill="black")

p2 = out_dir / "ppt_sequence.png"
img.save(p2)

# 图3
img=Image.new("RGB",(1600,900),"white")
d=ImageDraw.Draw(img)
d.text((40,30),"Core Data Model (Overview)",font=title,fill="black")

box(d,(150,250,450,500),"RouteKey","#E3F2FD")
box(d,(600,200,1000,550),"PriorityConfig","#E8F5E9")
box(d,(1100,250,1450,500),"FetchResult","#FFF3E0")

arrow(d,(450,350),(600,350))
arrow(d,(1000,350),(1100,350))

p3 = out_dir / "ppt_model.png"
img.save(p3)

print(p1, p2, p3)