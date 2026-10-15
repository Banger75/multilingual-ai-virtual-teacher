# Persistent textbook page-image cache

This update changes vision page rendering from "render on every vision
request" to "render once when a PDF book is uploaded".

New storage:

data/
  books/
    English_Class 5.pdf

  book_pages/
    English_Class_5_<hash>/
      page_001.png
      page_002.png
      ...
      pages.json

The existing frontend image URL prefix remains:

/vision-pages/<book_id>/page_013.png

New uploads:
- save the PDF
- save book metadata
- render every PDF page once
- create pages.json

Existing books:
Run once inside the project/container:

python -m backend.vision.page_store --all

For Docker:

docker compose exec virtual-teacher python -m backend.vision.page_store --all

No Qdrant volume needs to be deleted.
