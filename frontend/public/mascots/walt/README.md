# WALT mascot assets

WALT is an original Warehouse Control Tower AI character. The package is self-hosted and follows
the standard transparent Codex/Petdex 8×9 atlas contract.

- Cell: 192×208 px
- Grid: 8 columns × 9 rows
- Atlas: 1536×1872 px
- Runtime: `spritesheet.webp` with PNG fallback
- Source anchor: `source/walt-character-anchor.png`
- Editable motion frames: `frames/*.png`

Regenerate the package from the approved anchor:

```powershell
python scripts/generate_walt_atlas.py
```

The React adapter adds Control Tower-specific states such as listening, analysing,
speaking, warning, sleeping and waking without changing the interoperable nine
atlas rows.
