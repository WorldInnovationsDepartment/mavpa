exec(open("build.py").read().split("# ---- A")[0])
# A v2: striped head, monkey face mask as negative space, eyes solid
bands=[(48,82),(90,124),(132,166),(174,208)]
def A(colors,bg="#fff"):
    defs="".join(f'<clipPath id="b{i}"><rect x="0" y="{a}" width="256" height="{b-a}"/></clipPath>' for i,(a,b) in enumerate(bands))
    defs+=f'<mask id="m"><rect width="256" height="256" fill="#fff"/><circle cx="106" cy="122" r="28" fill="#000"/><circle cx="150" cy="122" r="28" fill="#000"/><ellipse cx="128" cy="164" rx="46" ry="34" fill="#000"/><circle cx="108" cy="124" r="10" fill="#fff"/><circle cx="148" cy="124" r="10" fill="#fff"/></mask>'
    shape=circ(128,128,80)+circ(42,118,28)+circ(214,118,28)
    body="".join(f'<path clip-path="url(#b{i})" fill="{c}" d="{shape}" mask="url(#m)"/>' for i,c in enumerate(colors))
    return f"<defs>{defs}</defs>{body}"
save("a-symbol.svg",svg(A(["#000"]*4)))
save("a-symbol-color.svg",svg('<rect width="256" height="256" rx="56" fill="#14142B"/>'+A(["#FF8A5B","#A08BF0","#7DD3B4","#FCEFD0"])))
# C v2
SW=30; T=88; Bt=170; r=34; cy=122
p=[]; x=SW/2+4
p.append(f"M{x} {Bt}V{cy}a{r} {r} 0 0 1 {2*r} 0V{Bt}M{x+2*r} {cy}a{r} {r} 0 0 1 {2*r} 0V{Bt}"); x+=4*r+SW+14
cx=x+r; p.append(circ(cx,cy,r)+f"M{cx+r} {T}V{Bt}"); x=cx+r+SW+10
p.append(f"M{x} {T}L{x+36} {Bt-12}L{x+72} {T}"); x+=72+SW+10
cx=x+r; p.append(f"M{x} {T}V{Bt+64}"+circ(cx,cy,r)); x=cx+r+SW+14
cx=x+r
tail=f"M{cx+r} {T}V{Bt-14}c0 44 76 44 76 -6V58a22 22 0 0 1 44 0v8"
last=circ(cx,cy,r)+tail
W=int(cx+r+120+SW/2+6)
g=lambda d,c="#000":f'<path fill="none" stroke="{c}" stroke-width="{SW}" stroke-linecap="round" stroke-linejoin="round" d="{d}"/>'
save("c-wordmark.svg",svg(g("".join(p)+last),W,256))
ox=cx-r-SW/2-(256-(2*r+120+SW))/2
save("c-symbol.svg",svg(f'<g transform="translate({-ox:.0f} 0)">{g(last)}</g>'))
# lockups: symbol at height 256 + wordmark scaled
def lockup(symfile,name):
    sym=open(symfile).read().split('height="256">',1)[1].rsplit('</svg>',1)[0]
    s=0.62
    wd=g("".join(p)+last)
    return svg(f'{sym}<g transform="translate(276 {128-128*s:.0f}) scale({s})">{wd}</g>',int(276+W*s+10),256)
save("a-lockup.svg",lockup("a-symbol.svg","a")); save("b-lockup.svg",lockup("b-symbol.svg","b"))
save("c-lockup.svg",svg(g("".join(p)+last),W,256))
