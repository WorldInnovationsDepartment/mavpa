import math
def circ(cx,cy,r,cw=True):
    s=1 if cw else 0
    return f"M{cx-r} {cy}a{r} {r} 0 1 {s} {2*r} 0a{r} {r} 0 1 {s} {-2*r} 0Z"
def svg(body,w=256,h=256): return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{body}</svg>\n'
def save(n,s): open(n,'w').write(s)

# ---- A: Stem Head — monkey head sliced into 4 stem bands
bands=[(54,87),(95,128),(136,169),(177,210)]
cols=["#FF8A5B","#A08BF0","#7DD3B4","#FCEFD0"]
head=circ(128,132,78)+circ(46,138,30)+circ(210,138,30)+circ(102,112,11,False)+circ(154,112,11,False)
def A(colors):
    defs="".join(f'<clipPath id="b{i}"><rect x="0" y="{a}" width="256" height="{b-a}"/></clipPath>' for i,(a,b) in enumerate(bands))
    body="".join(f'<path clip-path="url(#b{i})" fill="{c}" d="{head}"/>' for i,c in enumerate(colors))
    return f"<defs>{defs}</defs>{body}"
save("a-symbol.svg",svg(A(["#000"]*4)))
save("a-symbol-color.svg",svg(A(cols)))

# ---- B: Headphone ears — the ears are the headphone cups
mask=circ(106,128,28,False)+circ(150,128,28,False)
def B(fg,face,eye):
    band='<path fill="none" stroke="%s" stroke-width="16" stroke-linecap="round" d="M44 128A84 84 0 0 1 212 128"/>'%fg
    h=f'<circle cx="128" cy="144" r="74" fill="{fg}"/>'
    cups=f'<rect x="28" y="110" width="34" height="66" rx="17" fill="{fg}"/><rect x="194" y="110" width="34" height="66" rx="17" fill="{fg}"/>'
    f=f'<path fill="{face}" d="{circ(108,134,30)}{circ(148,134,30)}"/><ellipse cx="128" cy="172" rx="48" ry="32" fill="{face}"/>'
    e=f'<circle cx="110" cy="134" r="10" fill="{eye}"/><circle cx="148" cy="134" r="10" fill="{eye}"/>'
    m=f'<path fill="none" stroke="{eye}" stroke-width="9" stroke-linecap="round" d="M110 178Q130 192 152 172"/>'
    br=f'<path fill="none" stroke="{eye}" stroke-width="8" stroke-linecap="round" d="M136 112L160 106"/>'
    return band+h+cups+f+e+m+br
save("b-symbol.svg",svg(B("#000","#fff","#000")))
save("b-symbol-color.svg",svg(B("#A08BF0","#FCEFD0","#14142B")))

# ---- C: wordmark mavpa, last 'a' grows a monkey tail
SW=30; T=88; Bt=170; r=34; cy=122
def wm(color, only_tail=False):
    p=[]; x=SW/2+4
    # m
    p.append(f"M{x} {Bt}V{cy}a{r} {r} 0 0 1 {2*r} 0V{Bt}M{x+2*r} {cy}a{r} {r} 0 0 1 {2*r} 0V{Bt}"); x+=4*r+SW+18
    # a
    cx=x+r; p.append(circ(cx,cy+0.0,r)+f"M{cx+r} {T}V{Bt}"); x=cx+r+SW+14
    # v
    p.append(f"M{x} {T}L{x+38} {Bt-14}L{x+76} {T}"); x+=76+SW+14
    # p
    cx=x+r; p.append(f"M{x} {T}V{Bt+64}"+circ(cx,cy,r)); x=cx+r+SW+18
    # a + tail
    cx=x+r; tail=f"M{cx+r} {T}V{Bt-8}a26 26 0 0 0 52 0V{cy+6}a13 13 0 0 0 -26 0"
    last=circ(cx,cy,r)+tail
    W=cx+r+52+SW/2+6
    d=last if only_tail else "".join(p)+last
    return d,W
d,W=wm("#000")
g=lambda d,c:f'<path fill="none" stroke="{c}" stroke-width="{SW}" stroke-linecap="round" stroke-linejoin="round" d="{d}"/>'
save("c-wordmark.svg",svg(g(d,"#000"),int(W),256))
dt,_=wm("#000",True)
# symbol: tailed a centred
save("c-symbol.svg",svg(f'<g transform="translate({-(W-256)+0} 0)">{g(dt,"#000")}</g>'.replace(f"translate({-(W-256)} 0)","translate(-%d 0)"%(int(W)-200))))
# lockups
def lock(sym, word_scale=0.62):
    return sym
