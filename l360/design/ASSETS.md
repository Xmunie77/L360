# Brand image assets — add manually

Two PNGs belong in this folder but could not be transferred losslessly from the
Google Drive "L360" folder by the build agent (binary files cannot pass through
its text channel without corruption — verified by PNG CRC checks and discarded
rather than committed broken).

Please add them by downloading from Drive and committing (or drag-and-drop into
this folder on GitHub):

| File | Source | Spec |
|---|---|---|
| `learning360-logo-white.png` | Drive → L360 folder | Primary lockup, 406×104, white on transparent |
| `learning360-mark-orange.png` | Drive → L360 folder | Mark, 512×512, orange on transparent |

Until they land, the app renders the wordmark as styled text ("Learning 360°",
Work Sans, per `DESIGN_SYSTEM.md` §1 naming rules) and ships a neutral PWA icon.
Replace both the header logo and the PWA icons once the real PNGs are committed —
see `l360/web/` README notes.
