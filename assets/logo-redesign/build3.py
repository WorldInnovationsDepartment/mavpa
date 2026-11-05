def circ(cx,cy,r,cw=True):
    s=1 if cw else 0
    return f"M{cx-r} {cy}a{r} {r} 0 1 {s} {2*r} 0a{r} {r} 0 1 {s} {-2*r} 0Z"
def svg(body,w=256,h=256,extra=""): return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}"{extra}>{body}</svg>\n'
def save(n,s): open(n,'w').write(s)
NAVY,OR,PU,MI,CR="#14142B","#FF8A5B","#A08BF0","#7DD3B4","#FCEFD0"
bands=[(48,82),(90,124),(132,166),(174,208)]
def A(colors,uid="a"):
    defs="".join(f'<clipPath id="{uid}b{i}"><rect x="0" y="{a}" width="256" height="{b-a}"/></clipPath>' for i,(a,b) in enumerate(bands))
    defs+=(f'<mask id="{uid}m"><rect width="256" height="256" fill="#fff"/>'
      f'<circle cx="104" cy="118" r="28" fill="#000"/><circle cx="152" cy="118" r="28" fill="#000"/>'
      f'<ellipse cx="128" cy="166" rx="50" ry="34" fill="#000"/>'
      f'<circle cx="106" cy="110" r="10" fill="#fff"/><circle cx="150" cy="110" r="10" fill="#fff"/></mask>')
    shape=circ(128,128,80)+circ(44,124,30)+circ(212,124,30)
    body="".join(f'<path clip-path="url(#{uid}b{i})" fill="{c}" d="{shape}" mask="url(#{uid}m)"/>' for i,c in enumerate(colors))
    return f"<defs>{defs}</defs>{body}"
# wordmark (plain a)
SW=30; T=88; Bt=170; r=34; cy=122
p=[]; x=SW/2+4
p.append(f"M{x} {Bt}V{cy}a{r} {r} 0 0 1 {2*r} 0V{Bt}M{x+2*r} {cy}a{r} {r} 0 0 1 {2*r} 0V{Bt}"); x+=4*r+SW+14
def a_(x):
    cx=x+r; return circ(cx,cy,r)+f"M{cx+r} {T}V{Bt}", cx+r+SW/2
d,x=a_(x); p.append(d); x+=SW/2+10
p.append(f"M{x} {T}L{x+36} {Bt-12}L{x+72} {T}"); x+=72+SW+10
cx=x+r; p.append(f"M{x} {T}V{Bt+64}"+circ(cx,cy,r)); x=cx+r+SW+14
d,x=a_(x); p.append(d)
WW=int(x+SW/2+4)
word=lambda c:f'<path fill="none" stroke="{c}" stroke-width="{SW}" stroke-linecap="round" stroke-linejoin="round" d="{"".join(p)}"/>'
save("mavpa-symbol-black.svg",svg(A(["#000"]*4)))
save("mavpa-symbol.svg",svg(A([OR,PU,MI,CR])))
save("mavpa-wordmark.svg",svg(word("#000"),WW,256))
save("mavpa-icon.svg",svg(f'<rect width="256" height="256" rx="56" fill="{NAVY}"/><g transform="translate(20 20) scale(.84375)">{A([OR,PU,MI,CR])}</g>'))
s=.62
lk=lambda sym,c:f'{sym}<g transform="translate(286 {128-128*s:.1f}) scale({s})">{word(c)}</g>'
LW=int(286+WW*s+8)
save("mavpa-lockup-black.svg",svg(lk(A(["#000"]*4),"#000"),LW,256))
# banner 1280x600 dark
bs=1.25; lw=LW*bs; ox=(1280-lw)/2; oy=105
tag=(f'<text x="{ox+286*bs+4:.0f}" y="{oy+256*bs-24:.0f}" font-family="Avenir Next, Helvetica Neue, Arial, sans-serif" '
     f'font-weight="600" font-size="34" letter-spacing="1" fill="{CR}" fill-opacity=".75">monkey see · monkey do</text>')
save("mavpa-banner.svg",svg(f'<rect width="1280" height="600" fill="{NAVY}"/><g transform="translate({ox:.1f} {oy:.1f}) scale({bs})">{lk(A([OR,PU,MI,CR],"bn"),CR)}</g>'+
     f'<text x="640" y="{oy+256*bs+10:.0f}" text-anchor="middle" font-family="Avenir Next, Helvetica Neue, Arial, sans-serif" font-weight="500" font-size="36" letter-spacing="2" fill="{CR}" fill-opacity=".7">monkey see · monkey do</text>',1280,600))
