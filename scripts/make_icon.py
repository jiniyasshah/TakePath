"""Generate a bold, high-contrast app icon legible at Windows taskbar sizes."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import math
root=Path(__file__).resolve().parents[1]
size=1024
im=Image.new('RGBA',(size,size),(0,0,0,0))
d=ImageDraw.Draw(im)
# Use the whole icon square: previous art had excessive transparent padding.
d.rounded_rectangle((28,28,996,996),radius=210,fill='#111727',outline='#384D7A',width=15)
# Deep, simple indigo surface.
d.rounded_rectangle((51,51,973,973),radius=187,outline='#233354',width=14)
# Thick single arc at prominent size; minimal forms remain visible at 24 px.
box=(180,170,844,834)
d.arc(box, start=207,end=502,fill='#5888FF',width=88)
# Cyan start cap
for x,y,r in [(222,570,53)]: d.ellipse((x-r,y-r,x+r,y+r),fill='#2CE5E8')
# Arrow head at bottom/right, aligned with loop end
d.polygon([(755,686),(921,675),(827,829)],fill='#6484FF')
# Central white cursor with dark outline and sharply recognizable silhouette
shape=[(380,298),(380,768),(486,665),(575,840),(660,798),(571,620),(737,610)]
d.line(shape+[shape[0]],fill='#0A1330',width=42,joint='curve')
d.polygon(shape,fill='#F6FAFF')
d.line(shape+[shape[0]],fill='#D8E8FF',width=11,joint='curve')
assets=root/'assets';assets.mkdir(exist_ok=True)
im.save(assets/'takepath-icon.png')
# ICO embeds various true resolutions, not a single blown-down 256px BMP.
im.save(assets/'takepath.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
# macOS application icon
im.save(assets/'takepath.icns', format='ICNS')
print('Icon formats:', [f.name for f in assets.glob('takepath*')])
