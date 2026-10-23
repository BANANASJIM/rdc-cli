var e=[[{cmd:`rdc open hello_triangle.rdc`,output:`opened: hello_triangle.rdc`},{cmd:`rdc info`,output:`Capture:        hello_triangle.rdc
API:            Vulkan
Events:         6
Draw Calls:     1 (0 indexed, 1 non-indexed, 0 dispatches)
Clears:         0
Copies:         0`},{cmd:`rdc draws`,output:`EID	TYPE	TRIANGLES	INSTANCES	PASS	MARKER
11	Draw	12	1	Colour Pass #1 (1 Target + Depth)	-`},{cmd:`rdc pipeline 11`,output:`EID	API	TOPOLOGY	GFX_PIPE	COMP_PIPE
11	Vulkan	TriangleList	114	0`},{cmd:`rdc search "main"`,output:`shader:111[vs]:12:EntryPoint(Vertex, main, "main", {
shader:111[vs]:43:void main() {
shader:112[ps]:12:EntryPoint(Fragment, main, "main", {
shader:112[ps]:18:ExecutionMode(main, OriginUpperLeft);
shader:112[ps]:32:void main() {`},{cmd:`rdc close`,output:`session closed`}],[{cmd:`rdc open hello_triangle.rdc`,output:`opened: hello_triangle.rdc`},{cmd:`rdc tree / --depth 1`,output:`//
|-- capabilities
|-- info
|-- stats
|-- log
|-- events/
|-- draws/
|-- passes/
|-- resources/
|-- textures/
|-- buffers/
|-- shaders/
|-- counters/
\\-- current@`},{cmd:`rdc ls /draws/11`,output:`pipeline
shader
bindings
targets
postvs
cbuffer
vbuffer
ibuffer
descriptors
pixel`},{cmd:`rdc cat /draws/11/pipeline/topology`,output:`eid:      11
topology: TriangleList`},{cmd:`rdc resources -q | wc -l`,output:`46`},{cmd:`rdc draws --json | jq ".[0].triangles"`,output:`12`},{cmd:`rdc close`,output:`session closed`}],[{cmd:`rdc open hello_triangle.rdc`,output:`opened: hello_triangle.rdc`},{cmd:`rdc pick-pixel 300 300 11`,output:`r=0.3373  g=0.3373  b=0.3373  a=0.5216`},{cmd:`rdc pixel 300 300 11`,output:`EID	FRAG	DEPTH	PASSED	FLAGS
6	0	-	yes	-
11	0	0.9581	yes	-`},{cmd:`rdc debug pixel 11 300 300`,output:`stage:   ps
eid:     11
steps:   80
inputs:  _99 = [-107374176.0 -107374176.0 -107374176.0 -107374176.0]
outputs:  = [0.0]`},{cmd:`rdc debug pixel 11 300 300 --trace`,output:`STEP	INSTR	FILE	LINE	VAR	TYPE	VALUE
0	78	-	0	_99	float	-107374176.0 -107374176.0 -107374176.0 -107374176.0
1	79	-	0	_79	float	-0.015102430246770382 -0.3927634656429291 4.36358118057251
2	80	-	0	_80	float	0.01510667521506548 -8.669495582580566e-05 0.0010061264038085938
3	81	-	0		float	0.0
3	81	-	0	_76	float	0.01510667521506548 -8.669495582580566e-05 0.0010061264038085938
4	82	-	0		float	0.0
4	82	-	0	_82	float	-0.015102430246770382 -0.3927634656429291 4.36358118057251
... (138 more)`},{cmd:`rdc close`,output:`session closed`}],[{cmd:`rdc open hello_triangle.rdc`,output:`opened: hello_triangle.rdc`},{cmd:`rdc draws --json`,output:`[
  {
    "eid": 11,
    "type": "Draw",
    "triangles": 12,
    "instances": 1,
    "pass": "Colour Pass #1 (1 Target + Depth)",
    "marker": "-"
  }
]`},{cmd:`rdc assert-count draws --expect 1 --op eq`,output:`pass: draws = 1 (expected eq 1)`},{cmd:`rdc assert-count events --expect 5 --op ge`,output:`pass: events = 6 (expected ge 5)`},{cmd:`rdc close`,output:`session closed`}],[{cmd:`rdc diff before.rdc after.rdc --draws`,output:`STATUS	EID_A	EID_B	MARKER	TYPE	TRI_A	TRI_B	INST_A	INST_B	CONFIDENCE
=	11	11	-	Draw	12	12	1	1	medium`},{cmd:`rdc diff before.rdc after.rdc --stats`,output:`STATUS	PASS	DRAWS_A	DRAWS_B	DRAWS_DELTA	TRI_A	TRI_B	TRI_DELTA	DISP_A	DISP_B	DISP_DELTA
=	vkCmdBeginRenderPass(C=Clear, D=Clear)	1	1	0	12	12	0	0	0	0`}]],t=document.getElementById(`replay-lines`),n=document.getElementById(`replay-terminal`),r=20,i=30,a=1400,o=2e3,s=0;function c(e){return new Promise(t=>setTimeout(t,e))}function l(){n.scrollTop=n.scrollHeight}function u(){let e=document.createElement(`div`);e.className=`flex items-start`,e.innerHTML=`<span class="text-gpu-green mr-2 select-none font-bold shrink-0">$</span>`;let n=document.createElement(`span`);n.className=`text-gray-200`,e.appendChild(n);let r=document.createElement(`span`);return r.className=`replay-cursor`,r.textContent=`█`,e.appendChild(r),t.appendChild(e),{el:e,span:n}}async function d(e){let{el:t,span:n}=u();l();for(let t of e)n.textContent+=t,l(),await c(r);t.querySelector(`.replay-cursor`)?.remove()}function f(e){let t=document.createElement(`div`);if(t.className=`text-gray-400 pl-0 whitespace-pre`,/^\t*[A-Z_]+(\t[A-Z_]+)+$/.test(e))return t.className=`text-gray-500 pl-0 whitespace-pre`,t.textContent=e.replace(/\t/g,`  `),t;let n=e.match(/^(\w[\w\s]*?)\s{2,}(.+)$/);if(n){let e=document.createElement(`span`);e.className=`text-gray-500`,e.textContent=n[1],t.appendChild(e),t.appendChild(document.createTextNode(`  `));let r=document.createElement(`span`);return r.className=`text-gray-300`,r.textContent=n[2],t.appendChild(r),t}return e.includes(`	`)?(t.textContent=e.replace(/\t/g,`  `),t.className=`text-gray-300 pl-0 whitespace-pre`,t):/^\s*[{}\[\]"]/.test(e)?(t.className=`text-gray-400 pl-0 whitespace-pre`,t.textContent=e,t):(t.textContent=e,t)}async function p(e){if(e)for(let n of e.split(`
`))t.appendChild(f(n)),l(),await c(i)}async function m(){for(;;){let n=e[s%e.length];s++,t.innerHTML=``;for(let e of n)await d(e.cmd),await c(200),await p(e.output),await c(a);await c(o)}}m();