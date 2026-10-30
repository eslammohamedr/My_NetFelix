"""Generate original, local SVG scene artwork for the NetFelix TV themes."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'tv_ui'
SPORTS = {'ahly':'ASC','zamalek':'ZSC','ismaily':'ISC','barcelona':'FCB','madrid':'RM','ac-milan-legends':'ACM','inter-miami':'MIAMI','nassr':'NASSR','hilal':'HILAL','ittihad':'ITTIHAD','ahli-saudi':'AHLI','egypt':'EGYPT','argentina':'ARG','portugal':'POR','montreal':'MTL','toronto':'TOR','basketball':'HOOPS','baseball':'BASEBALL'}

def scene(theme):
    name, accent, deep = theme['id'], theme['primary'], theme['secondary']
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080"><defs>
    <linearGradient id="sky" x2=".8" y2="1"><stop stop-color="#030815"/><stop offset="1" stop-color="{deep}"/></linearGradient>
    <radialGradient id="light"><stop stop-color="{accent}" stop-opacity=".5"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>
    <linearGradient id="metal" x2=".8" y2="1"><stop stop-color="#fff"/><stop offset=".25" stop-color="{accent}"/><stop offset=".6" stop-color="{deep}"/><stop offset="1" stop-color="{accent}"/></linearGradient>
    <linearGradient id="fade"><stop stop-color="#030712" stop-opacity=".9"/><stop offset=".5" stop-color="#030712" stop-opacity=".25"/><stop offset="1" stop-color="#030712" stop-opacity="0"/></linearGradient>
    <linearGradient id="horizon" x2="0" y2="1"><stop stop-color="{accent}" stop-opacity=".5"/><stop offset="1" stop-color="#030712"/></linearGradient>
    <filter id="blur"><feGaussianBlur stdDeviation="28"/></filter></defs>
    <rect width="1920" height="1080" fill="url(#sky)"/><ellipse cx="1510" cy="440" rx="760" ry="650" fill="url(#light)"/>''']
    if name in SPORTS:
        parts += ['<path d="M700 770Q1300 420 1970 710L1980 1080H600Z" fill="#060e19"/>', f'<path d="M650 795Q1320 400 1990 745" fill="none" stroke="{accent}" stroke-width="9" opacity=".8"/>']
        for row in range(9):
            y=690+row*23
            parts.append(f'<path d="M780 {y}Q1370 {y-200} 1950 {y-24}" fill="none" stroke="{accent}" stroke-opacity="{.06+row*.012}" stroke-width="5"/>')
        for x in [1000,1760]:
            parts.append(f'<path d="M{x} 440v300" stroke="#35455a" stroke-width="7"/><path d="M{x-95} 442h190" stroke="#d4ebff" stroke-width="15"/><path d="M{x-90} 455L{x-260} 950H{x+320}L{x+90} 455" fill="{accent}" opacity=".035"/>')
        parts.append(f'<path d="M930 1080L1170 790H1650L1910 1080" fill="{accent}" opacity=".08"/><ellipse cx="1420" cy="985" rx="100" ry="47" fill="none" stroke="#d7eaff" opacity=".3"/>')
        if name in ['montreal','toronto']:
            parts.append('<path d="M970 955Q1400 815 1850 940" fill="none" stroke="#dceeff" stroke-width="80" opacity=".18"/>')
        elif name=='basketball':
            parts.append(f'<circle cx="1700" cy="820" r="85" fill="{accent}"/><path d="M1615 820h170M1700 735v170M1640 760q120 60 0 120M1760 760q-120 60 0 120" fill="none" stroke="#140d18" stroke-width="6"/>')
        elif name=='baseball':
            parts.append('<path d="M1260 990l150-145 150 145-150 145z" fill="none" stroke="#d4dbc5" stroke-width="4" opacity=".6"/>')
        # Original team-monogram shield; no downloaded club logo or player image.
        parts += [f'<g transform="translate(1400 475)"><path d="M-170-160Q0-225 170-160V30Q155 155 0 225Q-155 155-170 30Z" fill="{deep}" stroke="url(#metal)" stroke-width="8"/>',
                  f'<path d="M-145-137Q0-193 145-137V30Q130 133 0 194Q-130 133-145 30Z" fill="none" stroke="{accent}" stroke-width="2" opacity=".6"/>',
                  f'<path d="M-115-100H115M-95 110H95" stroke="{accent}" stroke-width="2"/>',
                  f'<text x="0" y="24" text-anchor="middle" fill="#f7f4e8" font-family="sans-serif" font-size="{48 if len(SPORTS[name])>4 else 80}" font-weight="900" letter-spacing="5">{SPORTS[name]}</text>',
                  f'<path d="M-45-65l8-18 8 18 19 2-14 13 4 19-17-9-17 9 4-19-14-13zM20-65l8-18 8 18 19 2-14 13 4 19-17-9-17 9 4-19-14-13z" fill="{accent}"/>', '</g>']
    elif name.startswith('islamic-'):
        parts += [f'<circle cx="1440" cy="230" r="90" fill="{accent}" opacity=".12"/>', f'<path d="M760 850Q1320 740 1920 840V1080H700Z" fill="#061019"/>']
        for x,h in [(1090,470),(1680,450),(1835,560)]:
            parts.append(f'<path d="M{x} 800V{h}h28v330m-38-{800-h}h48m-35-16h22l-11-40z" fill="#1d343e" stroke="{accent}" stroke-opacity=".45" stroke-width="3"/>')
        if name=='islamic-makkah':
            parts += ['<path d="M1220 570l230-40 175 85v230l-190 48-215-92z" fill="#101319" stroke="#bb9f66" stroke-width="3"/>', '<path d="M1220 615l215 20 190-45v35l-190 45-215-20z" fill="#bd9a54"/><path d="M1435 635v258" stroke="#383535" stroke-width="3"/><path d="M1480 710l50-10v105l-50 12z" fill="#b5985c"/>']
        else:
            color='#4baf91' if name=='islamic-madinah' else '#ecc46a'
            parts += [f'<path d="M1210 660Q1210 560 1420 465Q1630 560 1630 660Z" fill="{color}" opacity=".85"/><path d="M1210 660H1630V840H1210Z" fill="#243943" stroke="{color}" stroke-width="3"/>',f'<path d="M1420 465v-35" stroke="{color}" stroke-width="5"/><path d="M1427 405a12 12 0 1 0 6 20a13 13 0 0 1-6-20Z" fill="{color}"/>']
            for x in range(1250,1610,60):
                parts.append(f'<path d="M{x} 815v-70q20-35 40 0v70" fill="#091621" stroke="{color}" stroke-opacity=".45"/>')
        for i in range(7):
            parts.append(f'<path d="M900 {895+i*22}Q1430 {850+i*20} 1920 {895+i*22}" fill="none" stroke="{accent}" opacity=".09"/>')
    elif name=='gta6':
        parts += ['<circle cx="1480" cy="440" r="190" fill="#ff8ca4" opacity=".7"/>']
        for i in range(11):
            x=900+i*94;h=100+(i*47)%220
            parts.append(f'<rect x="{x}" y="{780-h}" width="75" height="{h}" fill="#160f30" stroke="#ff8fcb" stroke-opacity=".22"/>')
        parts.append('<path d="M850 850H1920V1080H650Z" fill="#0b0b22"/><path d="M1400 790L1080 1080M1480 790L1800 1080" stroke="#ff78bb" stroke-width="4" opacity=".7"/>')
        for x,y,size in [(1780,780,1.4),(1110,770,.9)]:
            parts.append(f'<g transform="translate({x} {y}) scale({size})" stroke="#050a17" fill="#050a17"><path d="M0 90Q-40-80 0-220" fill="none" stroke-width="17"/><path d="M0-220Q-80-280-165-220Q-80-242 0-220M0-220Q90-290 175-220Q80-245 0-220M0-220Q-130-230-155-130Q-60-200 0-220M0-220Q110-220 130-120Q50-200 0-220" stroke-width="9"/></g>')
    elif name=='blue-cinema':
        parts += [f'<path d="M1050 480L1920 170V950L1050 590Z" fill="{accent}" opacity=".09"/>', '<g transform="translate(1430 500) rotate(-15)"><rect x="-180" y="-80" width="380" height="230" rx="24" fill="#101e37" stroke="#65cfff" stroke-width="4"/><circle cx="-75" cy="-130" r="93" fill="#182b47" stroke="#8cbbd5" stroke-width="5"/><circle cx="100" cy="-130" r="93" fill="#182b47" stroke="#8cbbd5" stroke-width="5"/>']
        for cx in [-75,100]:
            for i in range(5):
                x=cx+math.cos(i*math.tau/5)*50;y=-130+math.sin(i*math.tau/5)*50
                parts.append(f'<circle cx="{x}" cy="{y}" r="19" fill="#071222"/>')
        parts += ['<path d="M200-20l110-55v175L200 45Z" fill="#254868"/><path d="M-70 150l-90 250M70 150l90 250" stroke="#35516d" stroke-width="12"/></g>']
    elif name in ['saudi-national','egypt-national','king-salman','crown-prince']:
        saudi=name!='egypt-national'
        parts += [f'<path d="M1010 1080V320" stroke="url(#metal)" stroke-width="11"/>']
        if saudi:
            parts.append('<path d="M1016 325Q1240 205 1510 330T1920 330V620Q1700 745 1500 620T1016 620Z" fill="#0d714b" stroke="#7ac997" stroke-opacity=".4"/><path d="M1240 480h310M1290 510h230" stroke="#e9ebca" stroke-width="7" opacity=".7"/>')
            parts.append('<path d="M1200 990V830L1280 760V990M1400 990V650L1480 570V990M1570 990V800L1660 700V990M1750 990V740H1840V990" fill="#0b2926" stroke="#2c7a60" stroke-width="3"/>')
        else:
            for i,col in enumerate(['#c62b43','#edebe0','#131821']):
                parts.append(f'<path d="M1016 {325+i*90}Q1240 {205+i*90} 1510 {330+i*90}T1920 {330+i*90}V{420+i*90}Q1700 {540+i*90} 1500 {420+i*90}T1016 {420+i*90}Z" fill="{col}"/>')
            parts.append('<path d="M1100 1000l270-340 270 340z" fill="#756046"/><path d="M1370 660l270 340h-150z" fill="#4a4037"/><path d="M1500 1030l210-270 210 270z" fill="#5f503d"/>')
    elif name=='night':
        parts.append('<circle cx="1730" cy="810" r="420" fill="#15233d" stroke="#97b8e9" stroke-width="3"/><path d="M1310 810Q1370 390 1730 390" fill="none" stroke="#b6d9ff" stroke-width="9" opacity=".5"/>')
        for i in range(95):
            x=(i*139+831)%1920;y=(i*73+31)%850
            parts.append(f'<circle cx="{x}" cy="{y}" r="{1+i%3*.6}" fill="#e2edff" opacity="{.15+(i%5)*.1}"/>')
        parts.append('<ellipse cx="1670" cy="810" rx="700" ry="65" transform="rotate(-24 1670 810)" fill="none" stroke="#89aee5" stroke-opacity=".26" stroke-width="16"/>')
    else:
        # Distinct landscapes for the base palettes.
        for i in range(5):
            y=450+i*110
            if name in ['amber','emerald']:
                path=f'M600 {y+260}Q1000 {y-150} 1320 {y+65}T2100 {y+35}V1080H600Z'
            else:
                path=f'M700 {y+200}Q1150 {y-140} 1510 {y+70}T2100 {y-20}V1080H700Z'
            parts.append(f'<path d="{path}" fill="{accent}" opacity="{.04+i*.035}"/>')
        if name=='violet':
            for i in range(6):
                parts.append(f'<path d="M800 100Q1200 {450+i*30} 1450 100T2100 220" stroke="{accent}" stroke-width="{15+i*8}" fill="none" opacity=".08"/>')
        parts.append(f'<circle cx="1570" cy="320" r="95" fill="{accent}" opacity=".16"/>')
    parts += ['<rect width="1920" height="1080" fill="url(#fade)"/></svg>']
    return '\n'.join(parts)

if __name__=='__main__':
    folder=ROOT/'scenes';folder.mkdir(exist_ok=True)
    themes=json.loads((ROOT/'themes.json').read_text())
    for theme in themes:
        theme['artwork']='/tv-ui/scenes/'+theme['id']+'.svg'
        theme['iconStyle']='solid' if theme['id'] in SPORTS else 'outline' if theme['id'].startswith('islamic-') else 'glass'
        (folder/(theme['id']+'.svg')).write_text(scene(theme))
    (ROOT/'themes.json').write_text(json.dumps(themes,ensure_ascii=False,indent=2)+'\n')
    print('Generated',len(themes),'original scene illustrations')
