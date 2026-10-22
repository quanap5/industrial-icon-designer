"""HTML builders for render_preview.py: the compare index and the context simulation pages.

Pages are static and offline: no script, no remote URL. Controls are radio inputs inside the page and
CSS `body:has(#id:checked)` rules show or hide content. All dynamic text is escaped, and ids derived
from set data (groups, sizes) are numeric, never raw text.

`src` is a duck-typed provider supplied by render_preview.Sources:
    ref(iid, size)                     -> relative png path or None
    png(iid, theme, state, size)       -> relative png path or None
    big(iid, theme, state)             -> relative png path or None
    inline(iid, size)                  -> inline svg body or ""
    webimg(iid, theme, state, size)    -> relative svg path or None
    alt(iid, size)                     -> alt text for the redrawn image
"""
from __future__ import annotations

import style_spec
from common import escape_html as esc

SIM_BANNER = "SIMULATION: standalone mock-up, not the actual application. It does not count as application validation."
ZOOM = 4
SCALES = (100, 125, 150, 200)
BADGE = {"approved": ("approved", "✔ approved"), "draft": ("draft", "✎ draft (pending approval)"),
         "missing": ("missing", "✖ no master yet")}

CSS = """
:root{--bg:#f1f5f9;--fg:#0f172a;--card:#fff;--line:#cbd5e1;--muted:#475569;--accent:#1d4ed8;--warnbg:#fff7ed;--warnbd:#fdba74;--chip:#e2e8f0}
@media (prefers-color-scheme:dark){:root{--bg:#0b1220;--fg:#e2e8f0;--card:#111a2e;--line:#334155;--muted:#94a3b8;--accent:#93c5fd;--warnbg:#3b2a12;--warnbd:#a16207;--chip:#1e293b}}
*{box-sizing:border-box}
body{font:14px/1.45 system-ui,sans-serif;margin:0;background:var(--bg);color:var(--fg)}
a{color:var(--accent)}h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:24px 0 8px}h3{font-size:14px;margin:0}h4{font-size:12px;margin:0 0 6px;color:var(--muted)}
.wrap{padding:16px 24px}.meta{color:var(--muted);font-size:12px;margin:2px 0 8px}.ok{color:#15803d}.bad{color:#b91c1c;font-weight:700}
@media (prefers-color-scheme:dark){.ok{color:#4ade80}.bad{color:#fca5a5}}
.banner{background:var(--warnbg);border:1px solid var(--warnbd);padding:8px 12px;border-radius:6px;margin:12px 0}
.badge{font-size:11px;padding:1px 8px;border-radius:9px;margin-left:8px;border:1px solid var(--muted);white-space:nowrap}
.badge.approved{border-color:#16a34a}.badge.draft{border-color:#ca8a04;border-style:dashed}.badge.missing{border-color:#dc2626;border-style:dotted}
table{border-collapse:collapse}td,th{padding:6px 10px;border:1px solid var(--line);text-align:center;font-size:12px}
.bar{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);padding:8px 24px;display:flex;flex-wrap:wrap;gap:6px 18px}
fieldset.ctl{border:0;margin:0;padding:0;display:flex;flex-wrap:wrap;align-items:center;gap:4px}
fieldset.ctl legend{float:left;font-size:12px;color:var(--muted);margin-right:6px;padding:0}
.opt{position:relative;display:inline-block}
.opt input{position:absolute;inset:0;opacity:0;margin:0;width:100%;height:100%;cursor:pointer}
.opt label{display:inline-flex;align-items:center;min-height:44px;padding:0 12px;border:1px solid var(--line);border-radius:6px;background:var(--chip);cursor:pointer}
.opt input:checked+label{background:var(--accent);color:var(--bg);border-color:var(--accent);font-weight:700}
.opt input:focus-visible+label{outline:3px solid var(--fg);outline-offset:2px}
.shell{display:grid;grid-template-columns:220px 1fr;gap:16px;padding:16px 24px;align-items:start}
.nav{position:sticky;top:64px;display:block}.nav legend{float:none;display:block;margin-bottom:4px}.nav .opt{display:block;margin-bottom:4px}.nav .opt label{width:100%;justify-content:space-between;gap:8px}
.cards{min-width:0}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;margin:0 0 14px}
.variants{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(340px,100%),1fr));gap:10px}
.variant{border:1px solid var(--line);border-radius:6px;padding:8px}
.compare{display:flex;flex-wrap:wrap;gap:8px}
.side{margin:0;flex:1 1 150px;border-width:2px;padding:6px;border-radius:6px}
.side.before{border-style:dashed;border-color:#64748b}.side.after{border-style:solid;border-color:#0369a1}
.side figcaption{font:700 11px system-ui,sans-serif;letter-spacing:.04em;text-transform:uppercase;margin-bottom:4px;color:inherit;opacity:.85}
.sizes{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end}
.px{display:inline-flex;flex-direction:column;align-items:center;gap:2px;font-size:11px}
.px img{image-rendering:pixelated}
.none{font-size:11px;font-style:italic;opacity:.8}
.zoomrow{display:flex;flex-direction:column;gap:4px;margin-top:8px;align-items:flex-start;max-width:100%}
.zoomrow .zlabel{font-size:11px;opacity:.8}.zoomrow img{image-rendering:pixelated;max-width:100%;height:auto}
.panel{border:1px solid var(--line);border-radius:8px;padding:12px;margin:10px 0;min-width:280px;background:var(--lbg)}
.sw{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr));gap:12px}
.surface{border:1px solid var(--line);border-radius:8px;padding:12px}
.surface.light{background:var(--lbg);color:var(--lfg)}.surface.dark{background:var(--dbg);color:var(--dfg)}
.surface .dis{color:var(--dis)}.surface h3{margin:10px 0 4px}.surface h4{color:inherit;opacity:.75;margin-bottom:8px}
.pair2{display:inline-flex;align-items:center;gap:6px}
.pair2 .tag{font-size:10px;opacity:.7}
.row{display:flex;align-items:center;gap:8px;padding:3px 0}.strip{display:flex;gap:8px;padding:4px 0;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;justify-content:center;padding:4px}
.ico{display:inline-block;width:calc(var(--w) * var(--k,1));height:calc(var(--w) * var(--k,1))}.ico svg{width:100%;height:100%;display:block}
.cimg{width:calc(var(--w) * var(--k,1));height:calc(var(--w) * var(--k,1));image-rendering:pixelated}
.cside{display:inline-flex;align-items:center;gap:4px}
.cside.dis{opacity:.45}
.legend{font-size:12px;color:var(--muted)}
.ribbon{display:flex;gap:18px;flex-wrap:wrap}.rgroup{border-right:1px solid rgba(128,128,128,.4);padding-right:14px}
.big{display:flex;flex-direction:column;align-items:center;gap:2px;font-size:11px}
.pagelinks a{margin-right:12px}
.foot{font-size:12px;color:var(--muted);margin:16px 24px}
.card:target{outline:3px solid var(--accent)}
@media (max-width:800px){.shell{grid-template-columns:1fr;padding:12px}.bar{position:static}.nav{position:static;display:flex;flex-wrap:wrap;gap:4px}.nav .opt{display:inline-block;margin:0}.nav legend{width:100%}.bar,.wrap{padding-left:12px;padding-right:12px}.compare{flex-direction:column}.foot{margin:12px}}
@media print{.bar,.nav{display:none}.shell{display:block}}
"""

STATIC_RULES = """
body:has(#th-light:checked) .variant[data-theme="dark"],body:has(#th-dark:checked) .variant[data-theme="light"],
body:has(#st-normal:checked) .variant[data-state="disabled"],body:has(#st-disabled:checked) .variant[data-state="normal"],
body:has(#md-before:checked) .after,body:has(#md-after:checked) .before,
body:not(:has(#zm:checked)) .zoomrow,
body:has(#sct-light:checked) .surface[data-theme="dark"],body:has(#sct-dark:checked) .surface[data-theme="light"]{display:none}
body:has(#sc-125:checked){--k:1.25}body:has(#sc-150:checked){--k:1.5}body:has(#sc-200:checked){--k:2}
"""


def page(title: str, body: str, extra_css: str = "") -> str:
    return (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>'
            f"<style>{CSS}{STATIC_RULES}{extra_css}</style></head><body>{body}</body></html>\n")


def theme_vars(spec: dict) -> str:
    t = spec["themes"]
    parts = []
    for key, short in (("light", "l"), ("dark", "d")):
        if t.get(key):
            parts.append(f"--{short}bg:{t[key]['background']};--{short}fg:{t[key]['normal']};--{short}dis:{t[key]['disabled']};")
    return ":root{" + "".join(parts) + "}"


def radios(name: str, legend: str, options: list[tuple[str, str]], checked: str, cls: str = "ctl") -> str:
    """Radio group; each option is (id, label) and the checked id is shown selected."""
    opts = "".join(f'<span class="opt"><input type="radio" name="{name}" id="{i}"{" checked" if i == checked else ""}>'
                   f'<label for="{i}">{label}</label></span>' for i, label in options)
    return f'<fieldset class="{cls}"><legend>{esc(legend)}</legend>{opts}</fieldset>'


def sized_rules(sizes: list[int]) -> str:
    return "".join(f'body:has(#sz-{s}:checked) .px:not([data-size="{s}"]){{display:none}}' for s in sizes)


def group_rules(count: int) -> str:
    return "".join(f'body:has(#g-{n}:checked) [data-g]:not([data-g="{n}"]){{display:none}}' for n in range(count))


def theme_controls(themes: list[str], prefix: str) -> str:
    opts = [(f"{prefix}-all", "Both")] + [(f"{prefix}-{t}", esc(t.capitalize())) for t in themes if t in ("light", "dark")]
    return radios(prefix, "Theme", opts, f"{prefix}-all")


def form_controls(forms: list[str]) -> str:
    """Filter by drawing form; only worth showing when the scope mixes more than one."""
    if len(forms) < 2:
        return ""
    return radios("fm", "Form", [("fm-all", "All")] + [(f"fm-{f}", esc(f)) for f in forms], "fm-all")


def form_rules(forms: list[str]) -> str:
    return "".join(f'body:has(#fm-{f}:checked) .icon:not([data-form="{f}"]){{display:none}}'
                   for f in forms) if len(forms) > 1 else ""


def group_nav(groups: list[tuple[str, int]], total: int, anchors: bool = True) -> str:
    opts = [("g-all", f"<span>All groups</span><span>{total}</span>")]
    opts += [(f"g-{n}", f"<span>{esc(name)}</span><span>{count}</span>") for n, (name, count) in enumerate(groups)]
    return radios("g", "Group", opts, "g-all", cls="ctl nav")


# ------------------------------------------------------------------ index

def _side(kind: str, label: str, bg: str, fg: str, inner: str) -> str:
    return (f'<figure class="side {kind}" style="background:{bg};color:{fg}"><figcaption>{label}</figcaption>{inner}</figure>')


def _variant(entry: dict, theme: str, tokens: dict, state: str, sizes: list[int], src) -> str:
    iid = entry["id"]
    bg, fg = tokens["background"], tokens["normal"]
    before, after = [], []
    for s in sizes:
        r = src.ref(iid, s)
        before.append(f'<span class="px" data-size="{s}">'
                      + (f'<img alt="reference" width="{s}" height="{s}" loading="lazy" src="{r}">' if r else '<span class="none">n/a</span>')
                      + f"<small>{s}px</small></span>")
        n = src.png(iid, theme, state, s) if entry["have_master"] else None
        after.append(f'<span class="px" data-size="{s}">'
                     + (f'<img alt="{esc(src.alt(iid, s))}" width="{s}" height="{s}" loading="lazy" src="{n}">' if n else '<span class="none">n/a</span>')
                     + f"<small>{s}px</small></span>")
    big = src.big(iid, theme, state) if entry["have_master"] else None
    zoom_ref = src.ref(iid, max(sizes))
    zb = (f'<div class="zoomrow"><span class="zlabel">enlarged ({ZOOM}x, supplement)</span>'
          f'<img alt="reference enlarged" width="{max(sizes) * ZOOM}" height="{max(sizes) * ZOOM}" loading="lazy" src="{zoom_ref}"></div>'
          if zoom_ref else "")
    za = (f'<div class="zoomrow"><span class="zlabel">enlarged (supplement)</span>'
          f'<img alt="enlarged supplement" width="128" height="128" loading="lazy" src="{big}"></div>' if big else "")
    no_ref = '' if zoom_ref else '<div class="none">No reference</div>'
    no_master = '' if entry["have_master"] else '<div class="none">No master yet</div>'
    return (f'<div class="variant" data-theme="{esc(theme)}" data-state="{esc(state)}"><h4>{esc(theme)} / {esc(state)}</h4>'
            f'<div class="compare">'
            + _side("before", "Before (reference)", bg, fg, f'<div class="sizes">{"".join(before)}</div>{zb}{no_ref}')
            + _side("after", "After (redrawn)", bg, fg, f'<div class="sizes">{"".join(after)}</div>{za}{no_master}')
            + "</div></div>")


def index_page(spec: dict, entries: list[dict], groups: list[tuple[str, int]], scope: str, contrast_html: str,
               palette_note: str, src) -> str:
    sizes = spec["preview_sizes_px"]
    cards = []
    for e in entries:
        variants = "".join(_variant(e, theme, tokens, state, sizes, src)
                           for theme, tokens in sorted(spec["themes"].items()) for state in spec["states"])
        cls, label = BADGE[e["badge"]]
        pair = f' | variant of <a href="#{esc(e["variant_of"])}">{esc(e["variant_of"])}</a>' if e["variant_of"] else ""
        cards.append(
            f'<section class="card icon" id="{esc(e["id"])}" data-g="{e["g"]}" data-form="{esc(e["form"])}">'
            f'<h3>{esc(e["id"])}<span class="badge {cls}">{label}</span></h3>'
            f'<div class="meta">{esc(e["meaning"])} | {esc(e["group"])} | {esc(e["role"])} | {esc(e["form"])}{pair}</div>'
            f'<div class="variants">{variants}</div></section>')
    themes = sorted(spec["themes"])
    forms = sorted({e["form"] for e in entries})
    controls = (
        theme_controls(themes, "th")
        + radios("st", "State", [("st-all", "Both"), ("st-normal", "Normal"), ("st-disabled", "Disabled")], "st-all")
        + radios("sz", "Size", [("sz-all", "All")] + [(f"sz-{s}", f"{s}px") for s in sizes], "sz-all")
        + form_controls(forms)
        + radios("md", "Show", [("md-both", "Before + After"), ("md-before", "Before only"), ("md-after", "After only")], "md-both")
        + '<fieldset class="ctl"><legend>Enlarged</legend><span class="opt"><input type="checkbox" id="zm" checked>'
          '<label for="zm">Supplement</label></span></fieldset>')
    head = (f"<h1>Icon preview: {esc(spec['set_id'])}</h1>"
            f'<div class="meta">Style {esc(spec["style_version"])} | mode {esc(style_spec.style_mode(spec))} | grid {spec["grid"]} | stroke {spec["stroke_width"]} | '
            f'{len(entries)} icons in scope ({esc(scope)})</div>{palette_note}'
            f'<div class="banner">Views are shown at actual size; enlarged views are a supplement only. Before is the reference as supplied, '
            f'After is the redrawn master. Contexts: <span class="pagelinks"><a href="contexts/desktop.html">Desktop simulation</a>'
            f'<a href="contexts/web.html">Web inline SVG simulation</a><a href="contexts/web-img.html">Web img simulation</a></span></div>'
            f"<h2>Contrast (token level)</h2>{contrast_html}")
    extra = sized_rules(sizes) + group_rules(len(groups)) + form_rules(forms)
    body = (group_nav_wrap(controls) + f'<div class="wrap">{head}</div>'
            f'<div class="shell">{group_nav(groups, len(entries))}<div class="cards"><h2>Icons</h2>{"".join(cards)}</div></div>'
            f'<p class="foot">Filters use CSS :has() and need a current browser; without it every icon and variant is shown.</p>')
    return page(f"Preview {spec['set_id']}", body, extra)


def group_nav_wrap(controls: str) -> str:
    return f'<div class="bar" role="group" aria-label="Preview controls">{controls}</div>'


# ------------------------------------------------------------------ contexts

PROFILES = {
    "desktop": {"title": "Desktop context simulation", "note": "Desktop PNG profile (conservative, as exported). Display scaling here is CSS only and is not a DPI test."},
    "web": {"title": "Web context simulation (inline SVG)", "note": "Inline SVG using currentColor, as the Web export ships it."},
    "web-img": {"title": "Web context simulation (img, resolved colors)", "note": "Resolved-color SVG used through an img element, as with the --web-img export."},
}


def _nearest(sizes: list[int], size: int) -> int:
    return min(sizes, key=lambda s: abs(s - size))


class _Ctx:
    """Builds Before/After items for one profile; image paths are made relative to preview/contexts/."""

    def __init__(self, profile: str, spec: dict, src, theme: str):
        self.profile, self.spec, self.src, self.theme = profile, spec, src, theme
        self.sizes = spec["preview_sizes_px"]

    @staticmethod
    def up(rel):
        return f"../{rel}" if rel else None

    def before(self, iid: str, size: int, dis: bool) -> str:
        r = self.up(self.src.ref(iid, _nearest(self.sizes, size)))
        inner = (f'<img class="cimg" style="--w:{size}px" alt="reference {esc(iid)}" width="{size}" height="{size}" loading="lazy" src="{r}">'
                 if r else '<span class="none">No reference</span>')
        return f'<span class="cside before{" dis" if dis else ""}">{inner}</span>'

    def after(self, iid: str, size: int, dis: bool) -> str:
        state = "disabled" if dis else "normal"
        if self.profile == "web":
            svg = self.src.inline(iid, size)
            inner = f'<span class="ico" style="--w:{size}px">{svg}</span>' if svg else ""
        elif self.profile == "web-img":
            p = self.up(self.src.webimg(iid, self.theme, state, size))
            inner = (f'<img class="cimg" style="--w:{size}px" alt="redrawn {esc(iid)}" width="{size}" height="{size}" loading="lazy" src="{p}">'
                     if p else "")
        else:
            p = self.up(self.src.png(iid, self.theme, state, _nearest(self.sizes, size)))
            inner = (f'<img class="cimg" style="--w:{size}px" alt="redrawn {esc(iid)}" width="{size}" height="{size}" loading="lazy" src="{p}">'
                     if p else "")
        return f'<span class="cside after">{inner}</span>'

    def pair(self, iid: str, size: int, dis: bool = False) -> str:
        return f'<span class="pair2">{self.before(iid, size, dis)}{self.after(iid, size, dis)}</span>'


def _surface(profile: str, theme: str, spec: dict, ids: list[str], names: dict[str, str], src) -> str:
    c = _Ctx(profile, spec, src, theme)
    dis_id = ids[len(ids) // 2] if ids else None

    def row(i, size, label, extra=""):
        d = i == dis_id
        return f'<div class="row{" dis" if d else ""}">{c.pair(i, size, d)}<span>{esc(label)}</span>{extra}</div>'

    def strip(items, size):
        return "".join(f'<span class="btn{" dis" if i == dis_id else ""}">{c.pair(i, size, i == dis_id)}</span>' for i in items)

    if profile == "desktop":
        ribbon = ('<div class="ribbon"><div class="rgroup"><div class="strip">'
                  + "".join(f'<span class="big">{c.pair(i, 32)}<span>{esc(i)}</span></span>' for i in ids[:3])
                  + "</div></div>"
                  + (('<div class="rgroup">' + "".join(f'<div class="row">{c.pair(i, 16)}<span>{esc(i)}</span></div>' for i in ids[3:6]) + "</div>") if ids[3:6] else "")
                  + "</div>")
        devices = "".join(row(i, 16, i, f'<span style="margin-left:auto;opacity:.6">{"offline" if i == dis_id else "online"}</span>')
                          for i in ids[-5:])
        inner = (f"<h3>Toolbar (24px)</h3><div class='strip'>{strip(ids[:8], 24)}</div>"
                 f"<h3>Menu (16px)</h3>{''.join(row(i, 16, names[i]) for i in ids[:6])}"
                 f"<h3>Ribbon-like (32px / 16px)</h3>{ribbon}<h3>Device list (16px)</h3>{devices}")
    else:
        inner = (f"<h3>Navigation (24px, {'inline SVG' if profile == 'web' else 'img'})</h3>{''.join(row(i, 24, i) for i in ids[:6])}"
                 f"<h3>Actions (20px)</h3><div class='strip'>{strip(ids[:6], 20)}</div>"
                 f"<h3>List (16px)</h3>{''.join(row(i, 16, names[i]) for i in ids[-5:])}")
    return (f'<div class="surface {esc(theme)}" data-theme="{esc(theme)}" style="--dis:{spec["themes"][theme]["disabled"]}">'
            f"<h4>{esc(theme)} surface</h4>{inner}</div>")


def context_page(profile: str, spec: dict, entries: list[dict], groups: list[tuple[str, int]], src) -> str:
    """One context page; icon screens are rendered for All and for every group, shown by the group filter."""
    info = PROFILES[profile]
    themes = [t for t in ("light", "dark") if t in spec["themes"]]
    names = {e["id"]: e["meaning"] for e in entries}

    def block(n, subset):
        ids = [e["id"] for e in subset]
        surfaces = "".join(_surface(profile, t, spec, ids, names, src) for t in themes)
        return f'<div class="sw" data-g="{n}">{surfaces}</div>' if ids else ""

    blocks = [block("all", entries)] + [block(n, [e for e in entries if e["g"] == n]) for n in range(len(groups))]
    controls = (theme_controls(themes, "sct")
                + (radios("sc", "Display scaling (CSS)", [(f"sc-{s}", f"{s}%") for s in SCALES], "sc-100") if profile == "desktop" else ""))
    nav = group_nav(groups, len(entries))
    others = "".join(f'<a href="{n}.html">{esc(t)}</a>' for n, t in (("desktop", "Desktop (PNG)"), ("web", "Web inline SVG"), ("web-img", "Web img")) if n != profile)
    body = (group_nav_wrap(controls)
            + f'<div class="wrap"><h1>{esc(info["title"])}</h1><div class="banner">{esc(SIM_BANNER)}</div>'
              f'<p class="meta">{esc(info["note"])}</p>'
              f'<p class="legend">Each item shows Before (reference, left) and After (redrawn, right). The faded item has no disabled reference, '
              f'so Before is shown at reduced opacity as an approximation.</p>'
              f'<p class="meta pagelinks"><a href="../index.html">Back to preview</a>{others}</p></div>'
              f'<div class="shell">{nav}<div class="cards">{"".join(blocks)}</div></div>')
    extra = theme_vars(spec) + group_rules_ctx(len(groups))
    return page(info["title"], body, extra)


def group_rules_ctx(count: int) -> str:
    """Context pages hold an 'all' block plus one per group; the checked group's block is the only one shown."""
    names = ["all"] + [str(n) for n in range(count)]
    return ",".join(f'body:has(#g-{n}:checked) .sw:not([data-g="{n}"])' for n in names) + "{display:none}"
