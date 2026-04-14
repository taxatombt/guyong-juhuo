#!/usr/bin/env python3
# Generates logo.svg
svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<defs>
<radialGradient id="bg" cx="50%" cy="50%" r="70%"><stop offset="0%" stop-color="#1a1040"/><stop offset="100%" stop-color="#0a0818"/></radialGradient>
<linearGradient id="fl" x1="0" y1="1" x2="0" y2="0"><stop offset="0%" stop-color="#ff6b35"/><stop offset="35%" stop-color="#f72585"/><stop offset="65%" stop-color="#7b2ff7"/><stop offset="100%" stop-color="#4361ee"/></linearGradient>
<radialGradient id="ir" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#c084fc"/><stop offset="55%" stop-color="#7b2ff7"/><stop offset="100%" stop-color="#1e3a8a"/></radialGradient>
<filter id="g" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="eg" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="512" height="512" fill="url(#bg)" rx="80"/>
<g stroke="#7b2ff7" opacity="0.18">
<line x1="256" y1="42" x2="256" y2="58"/><line x1="362" y1="72" x2="356" y2="87"/>
<line x1="445" y1="150" x2="430" y2="157"/><line x1="470" y1="256" x2="454" y2="256"/>
<line x1="445" y1="362" x2="430" y2="355"/><line x1="362" y1="440" x2="356" y2="425"/>
<line x1="256" y1="470" x2="256" y2="454"/><line x1="150" y1="440" x2="156" y2="425"/>
<line x1="67" y1="362" x2="82" y2="355"/><line x1="42" y1="256" x2="58" y2="256"/>
<line x1="67" y1="150" x2="82" y2="157"/><line x1="150" y1="72" x2="156" y2="87"/>
</g>
<path d="M256,62C228,130 190,172 180,225C170,278 192,318 218,350C234,368 248,382 256,390C264,382 278,368 294,350C320,318 342,278 332,225C322,172 284,130 256,62Z" fill="url(#fl)" opacity="0.28" filter="url(#g)"/>
<path d="M256,92C236,148 212,182 204,224C196,266 212,300 234,330C247,348 253,360 256,368C259,360 265,348 278,330C300,300 316,266 308,224C300,182 276,148 256,92Z" fill="url(#fl)" opacity="0.52" filter="url(#g)"/>
<path d="M256,138C243,180 227,212 220,248C213,284 224,312 242,338C252,354 254,362 256,368C258,362 260,354 270,338C288,312 299,284 292,248C285,212 269,180 256,138Z" fill="url(#fl)" opacity="0.85" filter="url(#g)"/>
<ellipse cx="256" cy="258" rx="50" ry="34" fill="#1a1040"/>
<ellipse cx="256" cy="256" rx="46" ry="32" fill="#f0eeff"/>
<ellipse cx="256" cy="256" rx="30" ry="30" fill="url(#ir)" filter="url(#eg)"/>
<ellipse cx="256" cy="256" rx="13" ry="13" fill="#0a0818"/>
<ellipse cx="248" cy="248" rx="5" ry="4" fill="white" opacity="0.9"/>
<ellipse cx="262" cy="262" rx="2.5" ry="2" fill="white" opacity="0.4"/>
<ellipse cx="256" cy="256" rx="46" ry="32" fill="none" stroke="#7b2ff7" stroke-width="1.5" opacity="0.5"/>
<circle cx="192" cy="162" r="3" fill="#f72585" opacity="0.7" filter="url(#g)"/>
<circle cx="322" cy="145" r="2" fill="#ff6b35" opacity="0.6" filter="url(#g)"/>
<circle cx="358" cy="308" r="2.5" fill="#7b2ff7" opacity="0.5" filter="url(#g)"/>
<circle cx="165" cy="308" r="2" fill="#4361ee" opacity="0.6" filter="url(#g)"/>
<circle cx="343" cy="192" r="1.5" fill="#c084fc" opacity="0.5"/>
<circle cx="172" cy="222" r="1.5" fill="#f72585" opacity="0.4"/>
<circle cx="308" cy="363" r="2" fill="#ff6b35" opacity="0.45"/>
<circle cx="197" cy="363" r="1.5" fill="#4361ee" opacity="0.4"/>
</svg>'''

with open('logo.svg', 'w', encoding='utf-8') as f:
    f.write(svg)
print('Done: logo.svg')
