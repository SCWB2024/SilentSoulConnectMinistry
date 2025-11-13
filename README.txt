SoulStart Study Fix Pack (Minimal)
==================================
What this contains:
- templates/_base_study.html
- templates/study/index.html
- templates/study/series1.html ... series4.html
- routes_snippet.py.txt  (copy/paste into your app.py)

How to install (2 minutes):
1) Copy the 'templates' folder into your project so paths become:
   <your project>/templates/_base_study.html
   <your project>/templates/study/index.html
   <your project>/templates/study/series1.html ... series4.html

2) Open app.py and REPLACE your /study routes with the contents of routes_snippet.py.txt
   (Make sure 'from pathlib import Path' and 'from flask import render_template, url_for' are present at the top.)
   Also ensure SITE_THEME is defined as in your app.

3) Run:
   (soulstart) python app.py
   Then visit http://127.0.0.1:5000/study

Expected behavior:
- Study hub lists Series 1..4 based on the files found.
- Clicking a card opens that exact series#.html.
- No day pages, no XML required (you can add later if desired).

If you still see a 404 when clicking a series:
- Confirm the file exists at templates/study/seriesX.html (all lowercase).
- Confirm your app.py route function is named 'study_detail' and not shadowed.
- Restart Flask after copying files (Ctrl+C then 'python app.py').
