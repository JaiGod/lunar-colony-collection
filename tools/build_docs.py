"""Builds README.md and index.html from the design specs in generate.py."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate as g

ROOT = g.ROOT
REPO = "https://github.com/JaiGod/lunar-colony-collection"
PAGES = "https://jaigod.github.io/lunar-colony-collection/"
RAW = REPO + "/raw/main"

def hexs(c): return '#%02x%02x%02x' % c[:3]

rows = []
for i, s in enumerate(g.SHIRTS, 1):
    rows.append(f"""### {i}. {s['name']}

<a href="shirts/{s['file']}.png"><img src="previews/{s['file']}_preview.png" alt="{s['name']} avatar preview" width="460"></a>
<a href="shirts/{s['file']}.png"><img src="shirts/{s['file']}.png" alt="{s['name']} Roblox template" width="230"></a>

**Theme:** {s['theme']}
**Palette:** `{hexs(s['p']['base1'])}` · `{hexs(s['p']['accent'])}` · `{hexs(s['p']['accent2'])}` · `{hexs(s['p']['trim'])}`
> *"{s['lore']}"*

📥 [View template](shirts/{s['file']}.png) · [Direct download]({RAW}/shirts/{s['file']}.png)
""")

pants = "\n".join(f"- **{s['name']}**: {s['theme']} → [template](pants/{s['file']}.png) · [download]({RAW}/pants/{s['file']}.png)" for s in g.PANTS)
toc = "\n".join(f"{i}. [{s['name']}](#{i}-{s['name'].lower().replace(' ', '-').replace('.', '')})" for i, s in enumerate(g.SHIRTS, 1))

readme = f"""# 🌙 JaKing Lunar Colony Collection: Roblox Classic Shirts

**10 original Roblox classic shirt templates** (plus 2 matching pants) themed around space exploration, coding, robotics and engineering. They're built for STEM students, NASA fans, programmers, robotics teams and engineering clubs.

🌐 **[Open the live gallery website]({PAGES})** · 📦 [Download all (ZIP)]({REPO}/archive/refs/heads/main.zip) · 🛠️ [Creator Hub](https://create.roblox.com/)

Every item shares the same **Lunar Colony branding**: a hex-and-crescent emblem on the chest, matching trim and cuffs, Poppins typography, and a short lore line. Each shirt has its own colour palette. All designs are original, contain no third-party logos or characters, and are appropriate for all ages.

![Lunar Colony Collection contact sheet](previews/collection_sheet.png)

## 📑 Contents

{toc}

Also: [Matching sets](#-matching-sets) · [Upload guide](#-uploading-a-shirt-to-the-roblox-creator-hub) · [Links](#-links)

---

## 📁 Repository layout

```
/shirts      10 shirt templates, 585×559 PNG (Roblox classic shirt format)
/pants       2 matching pants templates, 585×559 PNG
/previews    front/back avatar mockups, matching-set previews, collection sheet
/tools       generate.py (renders every PNG) + build_docs.py (README & website)
index.html   browser gallery website (GitHub Pages)
README.md
```

## 👕 The shirts

{chr(10).join(rows)}
## 👖 Matching sets

{pants}

| Lunar Commander Mk-IV set | Developer Elite set |
|---|---|
| ![Mk-IV set](previews/lunar_commander_mk4_set_preview.png) | ![Developer Elite set](previews/developer_elite_set_preview.png) |
| ![Mk-IV pants template](pants/lunar_commander_mk4_pants.png) | ![Circuit pants template](pants/circuit_pants.png) |

---

## 🚀 Uploading a shirt to the Roblox Creator Hub

> Roblox's menus and upload fees change from time to time. If something looks different, follow the labels in the Creator Hub. Official reference: [Classic clothing docs](https://create.roblox.com/docs/art/classic-clothing).

1. **Download the template.** Click any *Direct download* link above, or open the file on GitHub and press **Download raw file**. Keep it as a **585 × 559 PNG**. Don't resize or recompress it.
2. **Check your account.** You must be signed in to the account (or [group](https://www.roblox.com/communities)) that will own the item. Selling clothing generally requires [Roblox Premium](https://www.roblox.com/premium/membership).
3. **Open the Creator Hub.** Go to [create.roblox.com](https://create.roblox.com/) → **Creations** → **Avatar Items**.
4. **Upload.** Choose to upload an asset, pick **Classic Shirt** (or **Classic Pants** for files in `/pants`), and select the PNG.
5. **Name & describe it.** Use the name and lore line from this README, for example:
   - Name: `Lunar Commander Mk-IV`
   - Description: `Lead humanity's first permanent lunar settlement. Built for explorers, engineers, and visionaries. — JaKing Lunar Colony Collection`
6. **Pay the upload fee (if shown) and submit.** The item goes through moderation, which usually takes minutes to a few hours.
7. **Put it on sale.** Once approved, open the item → **Sales** → enable **Item for Sale** and set a Robux price.
8. **Test it.** Equip it in the [Avatar Editor](https://www.roblox.com/my/avatar), or in Roblox Studio put a `Shirt` in a rig and set `ShirtTemplate` to your asset ID.

### Template map

- **Big centre square:** torso front. **Right-hand square:** torso back. **Thin strips beside them:** torso sides. **Top/bottom rectangles:** shoulders and hem.
- **The two lower cross shapes:** right arm (left cross) and left arm (right cross). The face with the round patch is the outer shoulder.
- The transparent area between faces isn't used, so leave it transparent.

## 🛍️ Selling strategy

- Release the 10 shirts as one **themed drop** with consistent thumbnails (from `/previews`).
- Put "Lunar Colony Collection" in every description so they appear together in search.
- Bundle the shirts with their matching pants: **Mk-IV** and **Developer Elite**.
- **Planned 3D UGC companions** (Blender meshes, made separately through the [UGC program](https://create.roblox.com/docs/marketplace/publishing-to-marketplace)):
  Cosmic Dominion Crown · Quantum Hacker Visor · Lunar Commander Helmet · Void Core Shoulder Pet · Singularity Wings · Ancient AI Relic Halo.
  The *Cosmic Dominion* and *Singularity Core* shirts already match these. All concepts are original and don't copy any existing limited item.

## 🛠️ Editing / regenerating

```bash
pip install pillow
python3 tools/generate.py     # renders /shirts, /pants, /previews
python3 tools/build_docs.py   # rebuilds README.md and index.html
```

Each design is a pair of Python functions (`f_*` = front, `b_*` = back) plus a palette entry in `SHIRTS`, so recolouring or adding a new shirt takes only a few lines.

## 🔗 Links

- 🌐 Live gallery: [{PAGES}]({PAGES})
- 📦 Repository: [{REPO}]({REPO})
- 🧭 Roblox Creator Hub: [create.roblox.com](https://create.roblox.com/)
- 📘 Classic clothing docs: [create.roblox.com/docs/art/classic-clothing](https://create.roblox.com/docs/art/classic-clothing)
- 🧑‍💻 More projects: [github.com/JaiGod](https://github.com/JaiGod)
- ❤️ Support the creator: [Patreon](https://www.patreon.com/c/JaineilRana)
- 💼 Creator: [Jaineil Rana on LinkedIn](https://www.linkedin.com/in/jaineil-rana-89005736a)

---

© JaKing (Jaineil Rana). Original designs.
"""
open(os.path.join(ROOT, "README.md"), "w").write(readme)

items = [dict(name=s['name'], file=s['file'], theme=s['theme'], lore=s['lore'], kind='shirt', accent=hexs(s['p']['accent'])) for s in g.SHIRTS]
items += [dict(name=s['name'], file=s['file'], theme=s['theme'], lore='', kind='pants', accent=hexs(s['p']['accent'])) for s in g.PANTS]
tpl = open(os.path.join(ROOT, "tools", "index_template.html")).read()
open(os.path.join(ROOT, "index.html"), "w").write(tpl.replace("__ITEMS__", json.dumps(items)).replace('href="README.md"', f'href="{REPO}#readme"'))
print("docs built")
