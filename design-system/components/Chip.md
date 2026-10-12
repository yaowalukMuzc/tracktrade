# Chip

Selectable pill for multi-select tags: sessions, timeframes, emotion tags, mistake tags, filters.

- Classes: `tt-chip` (`--on` selected). Emotion tags add valence: `tt-chip--pos` (positive → profit tint) / `tt-chip--neg` (negative → loss tint); neutral tags use the plain brand selection. `tt-chip--add` (dashed) opens "create tag".
- Consumer provides: label (TH/EN from `emotion_tags.label_th/label_en`), selected state, valence.
- 32px high; wrap in `tt-row` (8px gap). Never use a chip for a single action — that's a Button.
