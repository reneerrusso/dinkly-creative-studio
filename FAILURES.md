# DINKLY Failure Library

Use only the prevention language relevant to the current scene. If many failures are simultaneously likely, simplify the composition before generating.

| Failure | Likely misunderstanding | Prevention language | Simplify when | Edit when | Regenerate when |
|---|---|---|---|---|---|
| Wrong eyes | Another reference or generic cartoon style overrides the model | Preserve the exact black oval eyes with white highlights from the model sheet | Multiple references compete | One eye is locally wrong | Both characters use a new eye system |
| Long legs | `Standing` or `walking` triggers human anatomy | Feet are tiny nubs attached directly to the round body; no visible legs, knees, thighs, or calves | Pose requires a stride | One isolated limb appears | Full pose depends on legs |
| Human anatomy | Action implies gripping, bending, or human seated posture | Use only tiny nub arms and feet; no elbows, wrists, hands, fingers, knees, or torso | More than one complex action is requested | One hand-like shape is local | Anatomy is humanized throughout |
| Characters different sizes | Perspective or crowding changes scale | Dinka and Dinko have the same body size and remain on the same depth plane | Deep perspective is unnecessary | One character can be resized cleanly | Proportions differ throughout |
| Boy with three hair tufts | Generic tufted-mascot prior overrides the model | Dinko has exactly two hair tufts—count two before finalizing | Dramatic head angle hides the silhouette | Extra tuft is localized | Head shape is redesigned |
| Missing Girl bow | Prop, crop, or pose obscures a defining feature | Dinka's bright-red bow remains fully visible and unobscured | Tight crop removes head space | Bow can be restored locally | Girl identity drift is broad |
| Wrong ponytail | Model separates, recolors, or omits the ponytail | Dinka has the connected ponytail shape from the model sheet | Back view is not essential | Shape is locally repairable | Head silhouette is off-model |
| Oversized phone | Phone has no relative scale | Phone is about the size of Dinko's face and no more than 8–10% of the canvas | Detail is not story-critical | Phone alone is wrong | Scale affects all placement |
| Duplicate phone | Each viewing action becomes a separate device | Show exactly one phone and name which character holds it | Shared-phone action is unclear | Extra phone is isolated | Scene logic contains multiple devices |
| Blurry phone | Scene or interface consumes detail budget | Use a crisp one-color phone silhouette with no tiny UI text | Screen content is unnecessary | Phone region can be replaced | Product accuracy is central and unusable |
| Standing on vanity | `At the vanity` leaves support placement ambiguous | Bodies remain on the floor or visible chair seats; never on the vanity | Vanity is not essential | Placement can move locally | Furniture perspective is structurally wrong |
| Standing on kitchen island | Counter becomes a stage | Keep characters grounded beside the island; island top remains above and empty | Island can be a low table | Bodies can move without rebuild | Island and body scale are interdependent |
| Sitting on tabletop | `At a table` is interpreted as on the table | Each body rests on a visible chair seat behind the table | Chairs overcrowd the scene | Move bodies to existing seats | No viable seat geometry exists |
| Inside shopping cart | Cart is treated as a ride-on prop | Characters stand on the floor beside the cart; only groceries go inside | Cart is not essential | One body can move out | Cart dominates and blocks bodies |
| Floating | No floor or support is described | Align nub feet to one implied floor baseline with no gap | Perspective hides baseline | Small vertical correction works | Environment lacks spatial logic |
| Oversized toothbrushes | Toothbrush inherits human scale | Each toothbrush is narrower than one eye and shorter than one-third of body width | Bathroom detail is unnecessary | Replace toothbrush region | Arms and sink depend on wrong scale |
| Oversized mugs | Mug size is unspecified | Mug fits between nub arms and body without covering mouth or eyes | Multiple mugs clutter the frame | Mug can be scaled locally | Anatomy warped around mug |
| Unrealistic packaging | Product reference drives photorealism | Use a flat placeholder first; apply package accuracy in a second edit | Package has dense text or reflections | Placeholder region is isolated | Product style changed the image |
| Brand reference changes character style | Reference priority is unclear | Character reference controls characters only; product reference controls product only | Too many references are supplied | Character region can be restored | Whole image adopts campaign style |
| White replaces dark background | Default minimalist prior overrides format | Use one explicit solid dark background; never replace it with white | Dark treatment is unnecessary | Background-only edit is safe | Lighting and style also changed |
| Realistic environment | Setting description is too architectural | Use rounded flat-vector silhouettes with no texture, realism, or lighting | Detail is not story-critical | Background can be flattened | Characters also became realistic |
| Overly busy scene | Too many nouns and secondary actions | Use one action per character and three to five prop types | More than five prop types are requested | Isolated extras can be removed | Clutter determines composition |
| Too many colors | Every prop receives a unique color | Use one pastel background, one accent, and warm neutrals | Color is not story information | Recoloring is local | Palette drift affects everything |
| Different split backgrounds | Panels are described separately | Create one uninterrupted fill across the square before placing scenes | Separate locations are unnecessary | Recolor one panel | Lighting and palette differ structurally |
| Wrong chair/table placement | Seating geometry is vague | Name chair count, seat location, table position, and body support | Furniture adds no emotional clarity | Local movement is possible | Perspective cannot support seating |
| Characters obscured by props | Object is prioritized over silhouettes | Keep bow, ponytail, tufts, eyes, mouth, feet, and body visible | Prop can be removed | Resize one prop | Multiple defining features are hidden |
| Arms crossing unnaturally | Human holding language creates limbs | Nub arms touch or cradle one object close to the body and never cross the torso | Shared action is complex | One arm can be repaired | Both bodies are anatomically warped |

## Failure capture template

```text
Failure:
Affected prompt or asset:
Observed error:
Likely misunderstanding:
Prevention language:
Simpler alternative:
Edit boundary:
Regeneration trigger:
Date recorded:
```
