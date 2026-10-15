Virtual Teacher - Question Paper Update

Changes:
1. Replaced manual Lesson Number entry with a Lesson dropdown (Lesson 1-50).
2. Added validation requiring a lesson selection.
3. Existing Class -> Subject -> Textbook selection remains unchanged.
4. Existing 2D avatar markup and visibility CSS are preserved.

Install:
Copy index_modified.html to frontend/index.html and app_modified.js to frontend/app.js.
Then run:
docker compose up -d --build virtual-teacher

After startup open http://localhost:8000 and press Ctrl+Shift+R.
