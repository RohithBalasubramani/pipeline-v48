BUS SECTION (optional 4th key) — a PCC panel is physically TWO bus sections (A and B, coupler-tied). When the prompt addresses a bus section of the panel you resolved, ALSO return a "section" key:
- "A" or "B" — the prompt asks for ONE section ('voltage for pcc-1b' -> "B"; 'section a of pcc-2' -> "A").
- "both" — the prompt COMPARES the two sections of ONE panel ('compare pcc 1a and 1b', 'pcc-1 section a vs section b', 'both sections of panel 1'). This includes elided spellings where the panel prefix is written once ('compare pcc 1a and 1b' means sections A AND B of PCC-Panel-1).
- "none" — the prompt names no bus section (a whole-panel or non-panel prompt).
Omit the key when unsure. The "section" is about which BUS SECTION of the ONE resolved panel — it is NOT a second asset and never changes the "names" you return. Example: {"names":["PCC-Panel-1"],"confident":true,"section":"both"}.
