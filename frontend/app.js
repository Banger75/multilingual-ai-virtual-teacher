/* ============================================================
   VIRTUAL TEACHER
   COMPLETE FRONTEND JAVASCRIPT
   ============================================================ */

console.log("========== VIRTUAL TEACHER APP.JS LOADED ==========");

/* ============================================================
   ELEMENTS
   ============================================================ */

const classSelect = document.getElementById("classSelect");

const subjectSelect = document.getElementById("subjectSelect");

const languageSelect = document.getElementById("languageSelect");

const bookSelect = document.getElementById("bookSelect");

const questionElement = document.getElementById("question");

const askButton = document.getElementById("askButton");

const recordButton = document.getElementById("recordButton");

const statusElement = document.getElementById("status");

const teacherState = document.getElementById("teacherState");

const answerElement = document.getElementById("answer");

const answerAudioContainer = document.getElementById("answerAudioContainer");

const recordingStatus = document.getElementById("recordingStatus");

const recordedAudioContainer = document.getElementById(
  "recordedAudioContainer",
);

const selectionSummary = document.getElementById("selectionSummary");

const selectedClassDisplay = document.getElementById("selectedClassDisplay");

const selectedSubjectDisplay = document.getElementById(
  "selectedSubjectDisplay",
);

const selectedBookDisplay = document.getElementById("selectedBookDisplay");

const avatarSpeaking = document.getElementById("avatarSpeaking");

// Keep the 2D teacher avatar visible in the main classroom.
// The avatar can still animate while speaking, but it must not disappear
// when the Oral Test UI is added or reset.
const teacherIntroduction = document.querySelector(".teacher-introduction");
if (teacherIntroduction) {
  teacherIntroduction.classList.add("avatar-popup-visible");
}

function setTeacherAvatarSpeaking(isSpeaking) {
  if (teacherIntroduction) {
    teacherIntroduction.classList.toggle("avatar-speaking", isSpeaking);
  }
}

const teacherAvatarImage = document.querySelector(".teacher-avatar-image");
if (teacherAvatarImage) {
  teacherAvatarImage.addEventListener("error", () => {
    const wrap = document.getElementById("teacherAvatar");
    if (wrap) {
      wrap.innerHTML = "👩‍🏫";
      wrap.classList.add("avatar-image-fallback");
    }
  }, { once: true });
}


const boardStatus = document.getElementById("boardStatus");

const visualBoard = document.getElementById("visualBoard");

const canvas = document.getElementById("teachingCanvas");

const boardPlaceholder = document.getElementById("boardPlaceholder");

/* ============================================================
   UPLOAD ELEMENTS
   ============================================================ */

const openUploadButton = document.getElementById("openUploadButton");

const bookUploadModal = document.getElementById("bookUploadModal");

const closeUploadModal = document.getElementById("closeUploadModal");

const uploadDoneButton = document.getElementById("uploadDoneButton");

const startBookUpload = document.getElementById("startBookUpload");

const bookTitle = document.getElementById("bookTitle");

const uploadClass = document.getElementById("uploadClass");

const uploadSubject = document.getElementById("uploadSubject");

const bookFile = document.getElementById("bookFile");

const selectedFileName = document.getElementById("selectedFileName");

const uploadStatus = document.getElementById("uploadStatus");

// ============================================================
// UPLOAD PAGE / IMAGE
// ============================================================

const uploadPageButton = document.getElementById("uploadPageButton");

const uploadPageInput = document.getElementById("uploadPageInput");

let uploadedPageFile = null;

/* ============================================================
   STATE
   ============================================================ */

let allBooks = [];

let mediaRecorder = null;

let audioChunks = [];

let isRecording = false;

// Vision state
let visionPanel = null;

/* ============================================================
   INITIALIZE
   ============================================================ */

document.addEventListener("DOMContentLoaded", async () => {
  console.log("Virtual Teacher frontend initialized.");

  await loadBooks();

  updateSelectionUI();
});

/* ============================================================
   BOOK API
   ============================================================ */

async function loadBooks() {
  console.log("Loading books from /api/books...");

  try {
    const response = await fetch("/api/books", {
      method: "GET",
      cache: "no-store",
    });

    console.log("Books API status:", response.status);

    if (!response.ok) {
      throw new Error(`Books API returned HTTP ${response.status}`);
    }

    const data = await response.json();

    console.log("Books API response:", data);

    if (Array.isArray(data)) {
      allBooks = data;
    } else if (Array.isArray(data.books)) {
      allBooks = data.books;
    } else {
      allBooks = [];
    }

    console.log("Total books:", allBooks.length);

    populateBookDropdown();
  } catch (error) {
    console.error("LOAD BOOKS ERROR:", error);

    allBooks = [];

    resetBookDropdown("Unable to load books");
  }
}

/* ============================================================
   NORMALIZE BOOK DATA
   ============================================================ */

function normalizeBook(book) {
  return {
    name: book.name || book.filename || book.book || "",

    filename: book.filename || book.name || "",

    book: book.book || book.name || book.filename || "",

    class_name:
      book.class || book.class_name || book.className || book.grade || "",

    subject: normalizeSubject(book.subject || book.subject_name || ""),

    language: book.language || "",
  };
}

/* ============================================================
   NORMALIZE SUBJECT
   ============================================================ */

function normalizeSubject(subject) {
  if (!subject) {
    return "";
  }

  const value = String(subject).trim().toLowerCase();

  const mapping = {
    mathematics: "math",

    maths: "math",

    गणित: "math",

    english: "english",

    hindi: "hindi",

    punjabi: "punjabi",

    ਪੰਜਾਬੀ: "punjabi",

    science: "science",
  };

  return mapping[value] || value;
}

/* ============================================================
   EXTRACT CLASS FALLBACK
   ============================================================ */

function extractClassFromFilename(filename) {
  const text = String(filename);

  const match = text.match(/class[\s_-]*(\d+)/i);

  if (match) {
    return `Class ${match[1]}`;
  }

  return "";
}

/* ============================================================
   EXTRACT SUBJECT FALLBACK
   ============================================================ */

function extractSubjectFromFilename(filename) {
  const text = String(filename).toLowerCase();

  if (text.includes("hindi") || text.includes("pustak")) {
    return "hindi";
  }

  if (text.includes("english")) {
    return "english";
  }

  if (text.includes("punjabi") || text.includes("ganit-di-dunia")) {
    return "punjabi";
  }

  if (
    text.includes("math") ||
    text.includes("mathematics") ||
    text.includes("ganit")
  ) {
    return "math";
  }

  if (text.includes("science")) {
    return "science";
  }

  return "";
}

/* ============================================================
   POPULATE BOOK DROPDOWN
   ============================================================ */

function populateBookDropdown() {
  if (!bookSelect) {
    console.error("bookSelect element not found.");
    return;
  }

  bookSelect.innerHTML = "";

  const placeholder = document.createElement("option");

  placeholder.value = "";
  placeholder.textContent = "Select textbook";

  bookSelect.appendChild(placeholder);

  const selectedClass = classSelect?.value || "";

  const selectedSubject = normalizeSubject(subjectSelect?.value || "");

  console.log("Filtering books:", {
    selectedClass,
    selectedSubject,
    totalBooks: allBooks.length,
  });

  if (!selectedClass || !selectedSubject) {
    console.log("Class or subject not selected.");

    return;
  }

  const normalizedBooks = allBooks.map((book) => {
    return {
      name: book.name || book.filename || "",

      filename: book.filename || book.name || "",

      class: String(book.class || book.class_name || book.grade || "").replace(
        /^class\s*/i,
        "",
      ),

      subject: normalizeSubject(book.subject || book.subject_name || ""),

      language: book.language || "auto",
    };
  });

  console.log("Normalized books:", normalizedBooks);

  const matchingBooks = normalizedBooks.filter((book) => {
    const classMatches =
      book.class === String(selectedClass).replace(/^class\s*/i, "");

    const subjectMatches = book.subject === selectedSubject;

    console.log("Book check:", book.name, {
      bookClass: book.class,
      selectedClass,
      bookSubject: book.subject,
      selectedSubject,
      classMatches,
      subjectMatches,
    });

    return classMatches && subjectMatches;
  });

  console.log("Matching books:", matchingBooks);

  matchingBooks.forEach((book) => {
    const option = document.createElement("option");

    option.value = book.filename;

    option.textContent = book.name;

    bookSelect.appendChild(option);
  });

  if (matchingBooks.length === 0) {
    const option = document.createElement("option");

    option.value = "";

    option.textContent = "No books for this class and subject";

    option.disabled = true;

    bookSelect.appendChild(option);
  }
}

/* ============================================================
   NORMALIZE CLASS
   ============================================================ */

function normalizeClass(value) {
  if (!value) {
    return "";
  }

  return String(value).trim().toLowerCase().replace(/\s+/g, " ");
}

/* ============================================================
   CLASS CHANGE
   ============================================================ */

classSelect.addEventListener("change", () => {
  console.log("Class selected:", classSelect.value);

  populateBookDropdown();

  updateSelectionUI();
});

/* ============================================================
   SUBJECT CHANGE
   ============================================================ */

subjectSelect.addEventListener("change", () => {
  console.log("Subject selected:", subjectSelect.value);

  populateBookDropdown();

  updateSelectionUI();
});

/* ============================================================
   BOOK CHANGE
   ============================================================ */

bookSelect.addEventListener("change", () => {
  console.log("Book selected:", bookSelect.value);

  updateSelectionUI();
});

/* ============================================================
   UPDATE SELECTION UI
   ============================================================ */

function updateSelectionUI() {
  console.log("Updating selection UI...");

  const className = classSelect?.value || "—";

  const subject = getSubjectDisplayName(subjectSelect?.value || "");

  const book = getSelectedBookName();

  console.log("Selection UI:", {
    className,
    subject,
    book,
    selectedClassDisplay,
    selectedSubjectDisplay,
    selectedBookDisplay,
    selectionSummary,
  });

  // --------------------------------------------------------
  // Update individual selection displays safely
  // --------------------------------------------------------

  if (selectedClassDisplay) {
    selectedClassDisplay.textContent = className;
  }

  if (selectedSubjectDisplay) {
    selectedSubjectDisplay.textContent = subject;
  }

  if (selectedBookDisplay) {
    selectedBookDisplay.textContent = book || "—";
  }

  // --------------------------------------------------------
  // Update summary safely
  // --------------------------------------------------------

  if (selectionSummary) {
    if (classSelect?.value && subjectSelect?.value && bookSelect?.value) {
      selectionSummary.textContent = `${className} • ${subject} • ${book}`;
    } else if (classSelect?.value && subjectSelect?.value) {
      selectionSummary.textContent = `${className} • ${subject} • Select textbook`;
    } else {
      selectionSummary.textContent = "Select class, subject and book";
    }
  }

  console.log("Selection UI updated successfully.");
}

/* ============================================================
   SUBJECT DISPLAY NAME
   ============================================================ */

function getSubjectDisplayName(subject) {
  const names = {
    english: "English",

    math: "Mathematics",

    science: "Science",

    punjabi: "Punjabi",

    hindi: "Hindi",
  };

  return names[normalizeSubject(subject)] || "—";
}

/* ============================================================
   SELECTED BOOK NAME
   ============================================================ */

function getSelectedBookName() {
  if (!bookSelect.value) {
    return "";
  }

  const book = allBooks
    .map(normalizeBook)
    .find((item) => item.filename === bookSelect.value);

  return book?.name || bookSelect.value;
}

/* ============================================================
   RESET BOOK DROPDOWN
   ============================================================ */

function resetBookDropdown(message) {
  bookSelect.innerHTML = "";

  const option = document.createElement("option");

  option.value = "";

  option.textContent = message;

  bookSelect.appendChild(option);
}

/* ============================================================
   OPEN UPLOAD MODAL
   ============================================================ */

openUploadButton.addEventListener("click", () => {
  bookUploadModal.classList.remove("hidden");

  uploadStatus.className = "upload-status";

  uploadStatus.textContent = "Ready to upload.";

  clearUploadForm();
});

/* ============================================================
   CLOSE UPLOAD MODAL
   ============================================================ */

function closeUploadPopup() {
  bookUploadModal.classList.add("hidden");
}

closeUploadModal.addEventListener("click", closeUploadPopup);

uploadDoneButton.addEventListener("click", closeUploadPopup);

bookUploadModal.addEventListener("click", (event) => {
  if (event.target === bookUploadModal) {
    closeUploadPopup();
  }
});

/* ============================================================
   ESCAPE KEY
   ============================================================ */

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !bookUploadModal.classList.contains("hidden")) {
    closeUploadPopup();
  }
});

/* ============================================================
   FILE SELECTION
   ============================================================ */

bookFile.addEventListener("change", () => {
  if (bookFile.files.length === 0) {
    selectedFileName.textContent = "No file selected";

    return;
  }

  selectedFileName.textContent = bookFile.files[0].name;

  uploadStatus.className = "upload-status";

  uploadStatus.textContent = "PDF selected. Ready to upload.";
});

/* ============================================================
   UPLOAD BOOK
   ============================================================ */

startBookUpload.addEventListener("click", uploadBook);

async function uploadBook() {
  console.log("========== BOOK UPLOAD START ==========");

  const title = bookTitle.value.trim();

  const selectedClass = uploadClass.value.trim();

  const selectedSubject = normalizeSubject(uploadSubject.value);

  const file = bookFile.files[0];

  /* --------------------------------------------------------
       VALIDATION
       -------------------------------------------------------- */

  if (!title) {
    showUploadError("Please enter the book name.");

    return;
  }

  if (!selectedClass) {
    showUploadError("Please select the class.");

    return;
  }

  if (!selectedSubject) {
    showUploadError("Please select the subject.");

    return;
  }

  if (!file) {
    showUploadError("Please choose a PDF textbook.");

    return;
  }

  if (!file.name.toLowerCase().endsWith(".pdf")) {
    showUploadError("Only PDF textbooks are allowed.");

    return;
  }

  /* --------------------------------------------------------
       FORM DATA
       -------------------------------------------------------- */

  const formData = new FormData();

  /*
       These field names must match
       the FastAPI endpoint.
    */

  formData.append("title", title);

  formData.append("class_name", selectedClass);

  formData.append("subject", selectedSubject);

  formData.append("file", file);

  /* --------------------------------------------------------
       UI
       -------------------------------------------------------- */

  startBookUpload.disabled = true;

  uploadStatus.className = "upload-status loading";

  uploadStatus.textContent = "⏳ Uploading textbook...";

  try {
    const response = await fetch("/api/books/upload", {
      method: "POST",
      body: formData,
    });

    console.log("Upload HTTP status:", response.status);

    const rawText = await response.text();

    console.log("Upload raw response:", rawText);

    let data = {};

    try {
      data = JSON.parse(rawText);
    } catch {
      data = {
        message: rawText,
      };
    }

    if (!response.ok) {
      throw new Error(
        data.detail ||
          data.message ||
          `Upload failed with HTTP ${response.status}`,
      );
    }

    /* ----------------------------------------------------
           SUCCESS
           ---------------------------------------------------- */

    uploadStatus.className = "upload-status success";

    uploadStatus.innerHTML = `
            <strong>
                ✅ Book uploaded successfully!
            </strong>
            <br>
            ${escapeHtml(title)}
            • ${escapeHtml(selectedClass)}
            • ${escapeHtml(getSubjectDisplayName(selectedSubject))}
            `;

    console.log("BOOK UPLOAD SUCCESS:", data);

    /* ----------------------------------------------------
           REFRESH BOOKS
           ---------------------------------------------------- */

    await loadBooks();

    /*
           Automatically select the newly
           uploaded class and subject.
        */

    classSelect.value = selectedClass;

    subjectSelect.value = selectedSubject;

    populateBookDropdown();

    /*
           Try to select newly uploaded book.
        */

    const uploadedFilename = data.filename || data.book?.filename || file.name;

    const matchingOption = Array.from(bookSelect.options).find(
      (option) => option.value === uploadedFilename,
    );

    if (matchingOption) {
      bookSelect.value = matchingOption.value;
    }

    updateSelectionUI();

    /*
           Keep popup open so user can
           clearly see success.
        */

    startBookUpload.disabled = false;
  } catch (error) {
    console.error("BOOK UPLOAD ERROR:", error);

    showUploadError(error.message);

    startBookUpload.disabled = false;
  }
}

/* ============================================================
   UPLOAD ERROR
   ============================================================ */

function showUploadError(message) {
  uploadStatus.className = "upload-status error";

  uploadStatus.innerHTML = `
        <strong>
            ❌ Upload failed
        </strong>
        <br>
        ${escapeHtml(message)}
        `;
}

/* ============================================================
   CLEAR UPLOAD FORM
   ============================================================ */

function clearUploadForm() {
  bookTitle.value = "";

  uploadClass.value = "";

  uploadSubject.value = "";

  bookFile.value = "";

  selectedFileName.textContent = "No file selected";
}

/* ============================================================
   VISION / PICTURE EXPLANATION
   ============================================================ */

function isVisionQuestion(question) {
  const text = String(question || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");

  if (!text) return false;

  const hasPageNumber = /\bpage\s*(?:number\s*)?\d+\b/i.test(text);

  const hasVisionVerb = [
    "explain",
    "describe",
    "look at",
    "what is happening",
    "what are",
    "what do you see",
    "identify",
    "analyze",
    "analyse",
  ].some((phrase) => text.includes(phrase));

  const hasVisualWord = [
    "picture",
    "image",
    "illustration",
    "photo",
    "photograph",
    "diagram",
    "visual",
  ].some((word) => text.includes(word));

  const explicitUploadedVisual = [
    "this image",
    "this picture",
    "this photo",
    "uploaded image",
    "uploaded picture",
    "uploaded page",
  ].some((phrase) => text.includes(phrase));

  /*
     IMPORTANT:
     "Do you have a picture of Milkha Singh?"
     must NOT go to /api/vision/explain.

     "Explain the picture on page 13"
     MUST go to Vision.
  */
  if (hasPageNumber && hasVisionVerb && hasVisualWord) {
    return true;
  }

  if (explicitUploadedVisual && (hasVisionVerb || hasVisualWord)) {
    return true;
  }

  if (
    text.includes("what is happening") &&
    (hasPageNumber || explicitUploadedVisual)
  ) {
    return true;
  }

  return false;
}

function setVisionThinking() {
  statusElement.textContent = "👁️ Looking at the picture...";
  teacherState.textContent = "🟡 Looking...";
  avatarSpeaking.textContent =
    "I am looking carefully at the textbook picture...";
  boardStatus.textContent = "🟡 Analyzing picture";
  askButton.disabled = true;

  answerElement.innerHTML = `
        <div class="empty-answer thinking-answer">
            <div class="thinking-spinner"></div>
            <h3>Teacher is looking at the picture...</h3>
            <p>Finding the textbook page and understanding the illustration.</p>
        </div>
    `;
}

function parseVisionSections(answer) {
  const text = String(answer || "").trim();

  const vocabulary =
    text
      .match(
        /picture\s+vocabulary\s*:?\s*([\s\S]*?)(?=\n\s*what\s+is\s+happening\s*:?\s*|$)/i,
      )?.[1]
      ?.trim() || text;

  const happening =
    text.match(/what\s+is\s+happening\s*:?\s*([\s\S]*)$/i)?.[1]?.trim() ||
    "The picture explanation is shown above.";

  return { vocabulary, happening };
}

function formatVisionText(text) {
  const lines = String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (!lines.length) return "<p>No information returned.</p>";

  return lines
    .map((line) => {
      const clean = line.replace(/^[-•*]\s*/, "").trim();
      return `<p>• ${escapeHtml(clean)}</p>`;
    })
    .join("");
}

function showVisionResult(data) {
  if (!visualBoard) {
    throw new Error("Visual workspace was not found.");
  }

  const whiteboardPanel = visualBoard.closest(".whiteboard-panel");

  const teachingArea = visualBoard.closest(".teaching-area");

  // Enable side-by-side vision mode.
  if (teachingArea) {
    teachingArea.classList.add("vision-mode");
  }

  // Make whiteboard visible.
  if (whiteboardPanel) {
    whiteboardPanel.style.setProperty("display", "block", "important");

    whiteboardPanel.style.setProperty("width", "50%", "important");

    whiteboardPanel.style.setProperty("height", "100%", "important");

    whiteboardPanel.style.setProperty("flex", "1 1 50%", "important");

    whiteboardPanel.style.setProperty("min-width", "0", "important");

    whiteboardPanel.style.setProperty("min-height", "0", "important");
  }

  // Make visual board fill its half.
  visualBoard.style.setProperty("display", "block", "important");

  visualBoard.style.setProperty("width", "100%", "important");

  visualBoard.style.setProperty("height", "100%", "important");

  visualBoard.style.setProperty("min-width", "0", "important");

  visualBoard.style.setProperty("min-height", "0", "important");

  visualBoard.style.setProperty("position", "relative", "important");

  // Hide normal canvas.
  if (canvas) {
    canvas.style.display = "none";
  }

  if (boardPlaceholder) {
    boardPlaceholder.classList.add("hidden");
    boardPlaceholder.style.display = "none";
  }

  // Remove previous vision panel.
  if (visionPanel) {
    visionPanel.remove();
    visionPanel = null;
  }

  const imageUrl = data.image_url || "";

  const sections = parseVisionSections(data.answer || "");

  // ========================================================
  // CREATE VISION IMAGE PANEL
  // ========================================================

  visionPanel = document.createElement("div");

  visionPanel.id = "visionPanel";
  visionPanel.className = "vision-panel";

  visionPanel.innerHTML = `
    <div class="vision-image-area">

      <!-- ZOOM TOOLBAR -->
      <div class="vision-image-toolbar">

        <button
          type="button"
          id="visionZoomOut"
          title="Zoom out">
          −
        </button>

        <span id="visionZoomLevel">
          125%
        </span>

        <button
          type="button"
          id="visionZoomIn"
          title="Zoom in">
          +
        </button>

        <button
          type="button"
          id="visionZoomReset">
          Reset
        </button>

        ${
          imageUrl
            ? `
              <button
                type="button"
                class="vision-fullscreen-button"
                id="visionFullscreenButton">
                Full Screen
              </button>
            `
            : ""
        }

      </div>

      <!-- FIXED IMAGE VIEWPORT -->
      <div
        class="vision-image-viewport"
        id="visionImageViewport">

        ${
          imageUrl
            ? `
              <img
                id="visionPageImage"
                class="vision-page-image"
                src="${escapeHtml(imageUrl)}"
                alt="Textbook page ${escapeHtml(data.printed_page ?? "")}"
              />
            `
            : `
              <div class="vision-no-image">
                Textbook page image is not available.
              </div>
            `
        }

      </div>

      <!-- PAGE INFORMATION -->
      <div class="vision-page-info">

        <span>
          📖 ${escapeHtml(data.book || "")}
        </span>

        <span>
          Page ${escapeHtml(data.printed_page ?? "")}
        </span>

      </div>

    </div>
  `;

  visualBoard.appendChild(visionPanel);

  // ========================================================
  // EXISTING ANSWER PANEL
  // ========================================================

  answerElement.innerHTML = `
    <div class="vision-answer-content">

      <div class="vision-answer-title">
        📚 Picture Vocabulary
      </div>

      <div class="vision-answer-body">
        ${formatVisionText(sections.vocabulary)}
      </div>

      <div class="vision-answer-title vision-happening-title">
        🎬 What is Happening?
      </div>

      <div class="vision-answer-body">
        ${formatVisionText(sections.happening)}
      </div>

    </div>
  `;

  // ========================================================
  // IMAGE + ZOOM
  // ========================================================

  const image = document.getElementById("visionPageImage");

  const zoomInButton = document.getElementById("visionZoomIn");

  const zoomOutButton = document.getElementById("visionZoomOut");

  const zoomResetButton = document.getElementById("visionZoomReset");

  const zoomLevel = document.getElementById("visionZoomLevel");

  let visionZoom = 1.25;

  function updateVisionZoom() {
    if (!image) return;

    image.style.width = `${visionZoom * 100}%`;

    image.style.maxWidth = "none";

    image.style.height = "auto";

    if (zoomLevel) {
      zoomLevel.textContent = `${Math.round(visionZoom * 100)}%`;
    }
  }

  zoomInButton?.addEventListener("click", () => {
    visionZoom = Math.min(3, visionZoom + 0.25);

    updateVisionZoom();
  });

  zoomOutButton?.addEventListener("click", () => {
    visionZoom = Math.max(0.75, visionZoom - 0.25);

    updateVisionZoom();
  });

  zoomResetButton?.addEventListener("click", () => {
    visionZoom = 1.25;
    updateVisionZoom();
  });

  updateVisionZoom();

  // ========================================================
  // FULLSCREEN
  // ========================================================

  const fullscreenButton = document.getElementById("visionFullscreenButton");

  if (fullscreenButton && image) {
    fullscreenButton.addEventListener("click", async () => {
      try {
        if (image.requestFullscreen) {
          await image.requestFullscreen();
        }
      } catch (error) {
        console.warn("Vision fullscreen error:", error);
      }
    });
  }

  // ========================================================
  // IMAGE DIAGNOSTICS
  // ========================================================

  if (image) {
    image.addEventListener("load", () => {
      console.log(
        "VISION IMAGE LOADED:",
        image.naturalWidth,
        "x",
        image.naturalHeight,
      );
    });

    image.addEventListener("error", () => {
      console.error("VISION IMAGE FAILED:", image.src);
    });
  }

  // ========================================================
  // STATUS
  // ========================================================

  if (statusElement) {
    statusElement.textContent = "Visual explanation ready";
  }

  if (teacherState) {
    teacherState.textContent = "🟢 Ready";
  }

  if (avatarSpeaking) {
    avatarSpeaking.textContent = "Here is the picture explanation.";
  }

  if (boardStatus) {
    boardStatus.textContent = "🟢 Visual explanation ready";
  }
}
function clearVisionPanel() {
  if (visionPanel) {
    visionPanel.remove();
    visionPanel = null;
  }

  const teachingArea = visualBoard?.closest(".teaching-area");

  if (teachingArea) {
    teachingArea.classList.remove("vision-mode");
  }

  const whiteboardPanel = visualBoard?.closest(".whiteboard-panel");

  if (whiteboardPanel) {
    whiteboardPanel.style.removeProperty("display");
    whiteboardPanel.style.removeProperty("width");
    whiteboardPanel.style.removeProperty("height");
    whiteboardPanel.style.removeProperty("flex");
    whiteboardPanel.style.removeProperty("min-width");
    whiteboardPanel.style.removeProperty("min-height");
    whiteboardPanel.style.removeProperty("box-sizing");
  }

  if (canvas) {
    canvas.style.display = "";
  }

  if (boardPlaceholder) {
    boardPlaceholder.style.display = "";
    boardPlaceholder.classList.remove("hidden");
  }
}

async function askVision(question) {
  const selectedClass = normalizeClass(classSelect?.value || "");
  const selectedSubject = normalizeSubject(subjectSelect?.value || "");
  const selectedBook = bookSelect?.value || "";

  if (!selectedClass) throw new Error("Please select your class first.");
  if (!selectedSubject) throw new Error("Please select a subject first.");
  if (!selectedBook) throw new Error("Please select a textbook first.");

  setVisionThinking();

  try {
    const response = await fetch("/api/vision/explain", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        class_name: selectedClass,
        subject: selectedSubject,
        book: selectedBook,
        language: languageSelect?.value || "auto",
      }),
    });

    const whiteboardPanel = visualBoard?.closest(".whiteboard-panel");

    if (whiteboardPanel) {
      whiteboardPanel.style.display = "";
    }

    const raw = await response.text();

    if (!response.ok) {
      throw new Error(`Vision server error ${response.status}: ${raw}`);
    }

    let data;
    try {
      data = JSON.parse(raw);
    } catch {
      throw new Error("Vision server returned invalid JSON.");
    }

    if (!data.success) {
      throw new Error(
        data.error || "The vision teacher could not explain this picture.",
      );
    }

    questionElement.value = data.question || question;
    const visionAnswer =
      typeof data.answer === "string" ? data.answer : String(data.answer ?? "");

    answerElement.textContent = visionAnswer;

    showVisionResult({
      ...data,
      answer: visionAnswer,
    });
    stopTeacherThinking();
    answerAudioContainer.innerHTML = "";

    return data;
  } catch (error) {
    stopTeacherThinking();

    console.error("ASK VISION ERROR:", error);

    statusElement.textContent = "Vision error";
    teacherState.textContent = "🔴 Error";
    avatarSpeaking.textContent = "I could not understand the picture.";

    answerElement.innerHTML = `
            <div class="empty-answer">
                <div class="empty-icon">⚠️</div>
                <h3>Unable to explain the picture</h3>
                <p>${escapeHtml(error.message)}</p>
            </div>
        `;

    throw error;
  }
}

// Inject vision styling so index.html does not need to change yet.
(function injectVisionStyles() {
  if (document.getElementById("visionPanelStyles")) return;

  const style = document.createElement("style");
  style.id = "visionPanelStyles";

  style.textContent = `
    /* ========================================================
       VISION IMAGE AREA
       ======================================================== */

    #visualBoard {
      position: relative;
      width: 100%;
      height: 100%;
    }

    /* ========================================================
      VISION SIDE-BY-SIDE MODE
      ======================================================== */

    /*
    * Only vision mode changes the teaching area.
    * Normal questions are completely unchanged.
    */
    .teaching-area.vision-mode {
      display: flex !important;
      flex-direction: row !important;
      align-items: stretch !important;

      width: 100% !important;
      min-width: 0 !important;
      min-height: 0 !important;
    }

    /* Left side: image */
    .teaching-area.vision-mode .whiteboard-panel {
      display: block !important;

      flex: 1 1 50% !important;

      width: 50% !important;
      min-width: 0 !important;
      min-height: 0 !important;

      box-sizing: border-box;
    }

    /* Right side: existing teacher explanation */
    .teaching-area.vision-mode .teacher-panel {
      flex: 1 1 50% !important;

      width: 50% !important;
      min-width: 0 !important;
      min-height: 0 !important;

      box-sizing: border-box;
    }

    .vision-panel {
      position: absolute;

      inset: 0;

      width: 100%;
      height: 100%;

      display: flex;

      align-items: center;
      justify-content: center;

      box-sizing: border-box;

      padding: 8px;
      margin: 0;

      overflow: hidden;

      background: transparent;

      z-index: 20;
    }

    .vision-image-area {
      position: relative;
      width: 100%;
      height: 100%;
      min-width: 0;
      min-height: 0;

      display: flex;
      flex-direction: column;

      overflow: hidden;
    }

    .vision-image-toolbar {
      flex: 0 0 auto;

      height: 42px;

      display: flex;
      align-items: center;
      justify-content: center;

      gap: 8px;

      padding: 5px 8px;

      box-sizing: border-box;

      background: #fff;
      border-bottom: 1px solid #e5e7eb;

      z-index: 5;
    }

    .vision-image-toolbar button {
      border: 1px solid #d1d5db;
      background: #fff;
      border-radius: 6px;

      min-width: 32px;
      height: 30px;

      padding: 3px 9px;

      cursor: pointer;
      font-size: 14px;
      font-weight: 600;
    }

    .vision-image-viewport {
      position: relative;

      flex: 1 1 auto;

      width: 100%;
      min-width: 0;
      min-height: 0;

      overflow: auto;

      display: block;

      padding: 4px;

      box-sizing: border-box;

      background: #fff;
    }

    .vision-page-image {
      display: block;

      width: 140%;
      max-width: none !important;

      height: auto;

      margin: 0;
      padding: 0;

      border: 0;
    }

    /* ========================================================
       VISION WRITTEN ANSWER
       Uses the existing Teacher Explanation panel.
       ======================================================== */

    .vision-answer-content {
      width: 100%;
      box-sizing: border-box;
    }

    .vision-answer-title {
      font-size: 16px;
      font-weight: 700;

      margin-bottom: 8px;
    }

    .vision-answer-body {
      font-size: inherit;
      line-height: 1.55;
    }

    .vision-answer-body p {
      margin: 0 0 6px 0;
    }

    .vision-happening-title {
      margin-top: 18px;
    }

    /* ========================================================
       FULLSCREEN IMAGE
       ======================================================== */

    #visionPageImage:fullscreen {
      width: 100vw;
      height: 100vh;

      max-width: none;
      max-height: none;

      object-fit: contain;

      background: #000000;
    }

    /* ========================================================
       RESPONSIVE
       ======================================================== */

    @media (max-width: 800px) {
      .vision-panel {
        padding: 5px;
      }

      .vision-fullscreen-button {
        width: 30px;
        height: 30px;
        font-size: 14px;
      }
    }
  `;

  document.head.appendChild(style);
})();

/* ============================================================
   ASK TEACHER
   ============================================================ */

askButton.addEventListener("click", () => {
  const question = questionElement.value.trim();

  if (!question) {
    alert("Please type a question first.");

    questionElement.focus();

    return;
  }

  askTeacher(question);
});

/* ============================================================
   ASK UPLOADED PAGE / IMAGE
   ============================================================ */

async function askUploadedPage(question) {
  if (!uploadedPageFile) {
    throw new Error("No page image has been selected.");
  }

  setTeacherThinking();

  statusElement.textContent = "Analyzing uploaded page...";
  teacherState.textContent = "🟡 Analyzing...";
  avatarSpeaking.textContent =
    "I am reading and understanding the uploaded page...";

  const formData = new FormData();

  formData.append("file", uploadedPageFile);

  formData.append("question", question);

  formData.append("language", languageSelect?.value || "auto");

  const responseMode =
    document.querySelector('input[name="responseMode"]:checked')?.value ||
    "written";

  formData.append("response_mode", responseMode);

  try {
    const response = await fetch("/api/vision/upload", {
      method: "POST",
      body: formData,
    });

    console.log("UPLOADED PAGE STATUS:", response.status);

    const raw = await response.text();

    console.log("UPLOADED PAGE RESPONSE:", raw);

    if (!response.ok) {
      throw new Error(`Uploaded page server error ${response.status}: ${raw}`);
    }

    let data;

    try {
      data = JSON.parse(raw);
    } catch {
      throw new Error("Uploaded page server returned invalid JSON.");
    }

    if (!data.success) {
      throw new Error(
        data.error ||
          data.detail ||
          "The uploaded page could not be explained.",
      );
    }

    const answer =
      typeof data.answer === "string" ? data.answer : String(data.answer ?? "");

    /*
     * ==========================================================
     * TEXT MODE
     * ==========================================================
     *
     * Keep the existing teacher answer area.
     */

    if (data.mode === "text") {
      clearVisionPanel();

      if (answerElement) {
        answerElement.textContent =
          answer.trim() || "The teacher did not return an answer.";
      }

      stopTeacherThinking();

      statusElement.textContent = "Answer ready";

      teacherState.textContent = "🟢 Ready";

      avatarSpeaking.textContent = "Here is your explanation.";

      boardStatus.textContent = "🟢 Ready";

      if (
        (responseMode === "spoken" || responseMode === "both") &&
        data.audio_url
      ) {
        showAnswerAudio(data.audio_url);
      } else {
        answerAudioContainer.innerHTML = "";
      }

      return data;
    }

    /*
     * ==========================================================
     * VISION MODE
     * ==========================================================
     *
     * Show the uploaded image in the existing visual workspace.
     *
     * The written explanation remains in the normal answer box.
     */

    if (data.mode === "vision") {
      if (answerElement) {
        answerElement.textContent =
          answer.trim() || "The teacher did not return an answer.";
      }

      /*
       * The uploaded file is local to the browser, so create
       * a temporary browser URL for the visual panel.
       */
      const localImageUrl = URL.createObjectURL(uploadedPageFile);

      showVisionResult({
        success: true,
        mode: "vision",
        question: question,
        answer: answer,
        book: "Uploaded Page",
        printed_page: "",
        pdf_index: "",
        image_url: localImageUrl,
      });

      stopTeacherThinking();

      statusElement.textContent = "Visual explanation ready";

      teacherState.textContent = "🟢 Ready";

      avatarSpeaking.textContent = "Here is the picture explanation.";

      boardStatus.textContent = "🟢 Visual explanation ready";

      if (
        (responseMode === "spoken" || responseMode === "both") &&
        data.audio_url
      ) {
        showAnswerAudio(data.audio_url);
      } else {
        answerAudioContainer.innerHTML = "";
      }

      return data;
    }

    throw new Error(`Unknown uploaded page mode: ${data.mode}`);
  } finally {
    /*
     * The uploaded page belongs only to this question.
     *
     * Clear the selected file so a later normal question
     * does not accidentally reuse the previous page.
     */

    uploadedPageFile = null;

    if (uploadPageInput) {
      uploadPageInput.value = "";
    }

    if (uploadPageButton) {
      uploadPageButton.textContent = "📎 Upload Page";
    }
  }
}

/* ============================================================
   ASK TEACHER FUNCTION
   ============================================================ */

async function* readChatLines(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      pending += done ? decoder.decode() : decoder.decode(value, { stream: true });
      const lines = pending.split(/\r?\n/);
      pending = lines.pop();
      for (const line of lines) {
        if (line.trim()) yield line.trim();
      }
      if (done) {
        if (pending.trim()) yield pending.trim();
        break;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

async function askTeacher(question) {
  /*
   * ============================================================
   * UPLOADED PAGE / IMAGE
   * ============================================================
   *
   * If the student selected an image/page, send it to the
   * uploaded-page endpoint first.
   *
   * The backend decides:
   *
   *   visual question -> Qwen3-VL
   *   text question   -> OCR + Qwen text model
   *
   * This must happen BEFORE isVisionQuestion(), otherwise an
   * uploaded image could accidentally use the textbook-page
   * vision endpoint.
   */

  if (uploadedPageFile) {
    try {
      await askUploadedPage(question);
    } catch (error) {
      console.error("UPLOADED PAGE REQUEST FAILED:", error);
    }

    return;
  }

  /*
   * ============================================================
   * EXISTING TEXTBOOK VISION
   * ============================================================
   *
   * This remains unchanged.
   *
   * Example:
   *
   *   "Explain the picture on page 13"
   *
   * uses the cached textbook page image.
   */

  if (isVisionQuestion(question)) {
    try {
      await askVision(question);
    } catch (error) {
      console.error("VISION REQUEST FAILED:", error);
    }

    return;
  }

  const selectedClassRaw = classSelect?.value || "";

  const selectedClass = normalizeClass(selectedClassRaw);

  const selectedSubject = normalizeSubject(subjectSelect?.value || "");

  const selectedBook = bookSelect?.value || "";

  if (!selectedClass) {
    alert("Please select your class first.");

    return;
  }

  if (!selectedSubject) {
    alert("Please select a subject first.");

    return;
  }

  if (!selectedBook) {
    alert("Please select a textbook first.");

    return;
  }

  const responseMode =
    document.querySelector('input[name="responseMode"]:checked')?.value ||
    "written";

  console.log("QUESTION:", question);

  console.log("CLASS:", selectedClass);

  console.log("SUBJECT:", selectedSubject);

  console.log("BOOK:", selectedBook);

  console.log("RESPONSE MODE:", responseMode);

  setTeacherThinking();

  try {
    const response = await fetch("/api/chat", {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        question: question,

        class_name: selectedClass,

        subject: selectedSubject,

        book: selectedBook,

        response_mode: responseMode,

        language: languageSelect?.value || "auto",
      }),
    });

    console.log("Chat status:", response.status);

    if (!response.ok) {
      const raw = await response.text();
      throw new Error(`Server ${response.status}: ${raw}`);
    }

    // /api/chat returns newline-delimited JSON (NDJSON).
    let finalData = null;
    let streamedAnswer = "";

    for await (const line of readChatLines(response)) {
      let data;

      try {
        data = JSON.parse(line);
      } catch (parseError) {
        console.warn("Skipping invalid chat stream line:", line, parseError);
        continue;
      }

      console.log("STREAM DATA:", data);

      if (data.type === "chunk") {
        const chunkText =
          typeof data.text === "string" ? data.text : String(data.text ?? "");

        streamedAnswer += chunkText;

        if (answerElement) {
          answerElement.textContent = streamedAnswer;
        }

        if (teacherState) {
          teacherState.textContent = "🗣️ Speaking...";
        }

        if (statusElement) {
          statusElement.textContent = "Teacher is answering...";
        }

        if (avatarSpeaking) {
          avatarSpeaking.textContent = "Here is your explanation...";
        }

        continue;
      }

      if (data.type === "done") {
        finalData = data;
        answerElement.textContent = data.answer || streamedAnswer;
        stopTeacherThinking();
        statusElement.textContent = "Answer ready";
        teacherState.textContent = "🟢 Ready";
        continue;
      }

      if (data.type === "audio" && finalData) {
        finalData.audio_url = data.audio_url;
        continue;
      }

      if (data.type === "error") {
        throw new Error(data.message || "Teacher server returned an error.");
      }
    }

    if (!finalData) {
      throw new Error("Teacher did not send a final response.");
    }

    console.log("CHAT RESPONSE:", finalData);

    const rawAnswer =
      finalData.answer ?? finalData.response ?? finalData.message ?? "";

    const candidateAnswer = rawAnswer || streamedAnswer || "";

    const answer =
      typeof candidateAnswer === "string"
        ? candidateAnswer
        : candidateAnswer &&
            typeof candidateAnswer === "object" &&
            "text" in candidateAnswer
          ? String(candidateAnswer.text ?? "")
          : String(candidateAnswer);

    console.log("ANSWER DATA:", candidateAnswer);

    console.log("ANSWER TYPE:", typeof candidateAnswer);

    if (answerElement) {
      answerElement.textContent =
        answer.trim() || "The teacher did not return an answer.";
    }

    stopTeacherThinking();

    statusElement.textContent = "Answer ready";

    teacherState.textContent = "🟢 Ready";

    avatarSpeaking.textContent = "Here is your explanation";

    boardStatus.textContent = "🟢 Ready";

    /*
           Show simple visual explanation
           when Mathematics is selected.
        */

    if (selectedSubject === "mathematics") {
      showMathBoard(question, answer);
    } else {
      clearVisualBoard();
    }

    /*
           Audio
        */

    if (
      (responseMode === "spoken" || responseMode === "both") &&
      finalData.audio_url
    ) {
      showAnswerAudio(finalData.audio_url);
    } else {
      answerAudioContainer.innerHTML = "";
    }
  } catch (error) {
    stopTeacherThinking();

    console.error("ASK TEACHER ERROR:", error);

    statusElement.textContent = "Error";

    teacherState.textContent = "🔴 Error";

    avatarSpeaking.textContent = "I could not get the answer.";

    answerElement.innerHTML = `
            <div class="empty-answer">

                <div class="empty-icon">
                    ⚠️
                </div>

                <h3>
                    Unable to get an answer
                </h3>

                <p>
                    ${escapeHtml(error.message)}
                </p>

            </div>
            `;
  }
}

/* ============================================================
   TEACHER THINKING
   ============================================================ */

function setTeacherThinking() {
  statusElement.textContent = "⏳ Processing...";

  teacherState.textContent = "🟡 Thinking...";

  avatarSpeaking.textContent =
    "Reading your textbook and preparing the answer...";

  boardStatus.textContent = "🟡 Processing";

  askButton.disabled = true;

  answerElement.innerHTML = `
        <div class="empty-answer thinking-answer">

            <div class="thinking-spinner"></div>

            <h3>
                Teacher is thinking...
            </h3>

            <p id="thinkingMessage">
                Reading your selected textbook...
            </p>

        </div>
    `;

  // Show progress messages
  const messages = [
    "Reading your selected textbook...",
    "Finding the relevant lesson...",
    "Searching the textbook...",
    "Preparing the explanation...",
    "Almost ready...",
  ];

  let index = 0;

  window.thinkingTimer = setInterval(() => {
    const element = document.getElementById("thinkingMessage");

    if (!element) {
      return;
    }

    index = (index + 1) % messages.length;

    element.textContent = messages[index];
  }, 1500);
}

function stopTeacherThinking() {
  if (window.thinkingTimer) {
    clearInterval(window.thinkingTimer);

    window.thinkingTimer = null;
  }

  askButton.disabled = false;
}

/* ============================================================
   ANSWER AUDIO
   ============================================================ */

function showAnswerAudio(audioURL) {
  answerAudioContainer.innerHTML = "";

  const audio = document.createElement("audio");

  audio.controls = true;

  audio.src = audioURL;

  audio.style.width = "100%";

  audio.addEventListener("play", () => setTeacherAvatarSpeaking(true));
  audio.addEventListener("pause", () => setTeacherAvatarSpeaking(false));
  audio.addEventListener("ended", () => setTeacherAvatarSpeaking(false));
  audio.addEventListener("error", () => setTeacherAvatarSpeaking(false));

  answerAudioContainer.appendChild(audio);

  audio.play().catch(() => {
    console.log("Autoplay blocked by browser.");
  });
}

/* ============================================================
   MATH BOARD
   ============================================================ */

function showMathBoard(question, answer) {
  boardPlaceholder.classList.add("hidden");

  const ctx = canvas.getContext("2d");

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  ctx.font = "bold 30px Segoe UI";

  ctx.fillStyle = "#4338ca";

  ctx.fillText("📐 Mathematics Explanation", 45, 55);

  ctx.font = "bold 20px Segoe UI";

  ctx.fillStyle = "#334155";

  ctx.fillText("Question:", 45, 105);

  ctx.font = "18px Segoe UI";

  drawWrappedText(ctx, question, 45, 140, 650, 27);

  ctx.font = "bold 20px Segoe UI";

  ctx.fillStyle = "#047857";

  ctx.fillText("Solution:", 45, 255);

  ctx.font = "18px Segoe UI";

  ctx.fillStyle = "#334155";

  drawWrappedText(ctx, answer, 45, 290, 650, 27);

  boardStatus.textContent = "🟢 Visual explanation ready";
}

/* ============================================================
   WRAPPED TEXT
   ============================================================ */

function drawWrappedText(ctx, text, x, y, maxWidth, lineHeight) {
  const words = String(text).split(/\s+/);

  let line = "";

  for (let i = 0; i < words.length; i++) {
    const testLine = line + words[i] + " ";

    const metrics = ctx.measureText(testLine);

    if (metrics.width > maxWidth && i > 0) {
      ctx.fillText(line, x, y);

      line = words[i] + " ";

      y += lineHeight;
    } else {
      line = testLine;
    }
  }

  ctx.fillText(line, x, y);
}

/* ============================================================
   CLEAR BOARD
   ============================================================ */

function clearVisualBoard() {
  clearVisionPanel();

  const ctx = canvas.getContext("2d");

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  boardPlaceholder.classList.remove("hidden");

  boardStatus.textContent = "🟢 Ready";
}

/* ============================================================
   BOARD CLEAR
   ============================================================ */

document
  .getElementById("boardClearButton")
  .addEventListener("click", clearVisualBoard);

/* ============================================================
   BOARD TEXT
   ============================================================ */

document.getElementById("boardTextButton").addEventListener("click", () => {
  const text = prompt("Enter text for the board:");

  if (!text) {
    return;
  }

  boardPlaceholder.classList.add("hidden");

  const ctx = canvas.getContext("2d");

  ctx.font = "24px Segoe UI";

  ctx.fillStyle = "#334155";

  ctx.fillText(text, 50, 80);
});

/* ============================================================
   BOARD LINE
   ============================================================ */

document.getElementById("boardLineButton").addEventListener("click", () => {
  boardPlaceholder.classList.add("hidden");

  const ctx = canvas.getContext("2d");

  ctx.beginPath();

  ctx.moveTo(100, 180);

  ctx.lineTo(500, 180);

  ctx.lineWidth = 4;

  ctx.strokeStyle = "#6366f1";

  ctx.stroke();
});

/* ============================================================
   BOARD CIRCLE
   ============================================================ */

document.getElementById("boardCircleButton").addEventListener("click", () => {
  boardPlaceholder.classList.add("hidden");

  const ctx = canvas.getContext("2d");

  ctx.beginPath();

  ctx.arc(300, 250, 90, 0, Math.PI * 2);

  ctx.lineWidth = 4;

  ctx.strokeStyle = "#ec4899";

  ctx.stroke();
});

/* ============================================================
   BOARD RECTANGLE
   ============================================================ */

document
  .getElementById("boardRectangleButton")
  .addEventListener("click", () => {
    boardPlaceholder.classList.add("hidden");

    const ctx = canvas.getContext("2d");

    ctx.lineWidth = 4;

    ctx.strokeStyle = "#10b981";

    ctx.strokeRect(180, 180, 300, 160);
  });

/* ============================================================
   MICROPHONE
   ============================================================ */

recordButton.addEventListener("click", async () => {
  if (isRecording) {
    stopRecording();
  } else {
    await startRecording();
  }
});

// ============================================================
// SELECT PAGE IMAGE
// ============================================================

if (uploadPageButton && uploadPageInput) {
  uploadPageButton.addEventListener("click", () => {
    uploadPageInput.click();
  });

  uploadPageInput.addEventListener("change", () => {
    const file = uploadPageInput.files?.[0];

    if (!file) {
      uploadedPageFile = null;
      uploadPageButton.textContent = "📎 Upload Page";
      return;
    }

    uploadedPageFile = file;

    uploadPageButton.textContent = `📎 ${file.name}`;

    console.log("UPLOADED PAGE SELECTED:", file.name, file.type, file.size);
  });
}

/* ============================================================
   START RECORDING
   ============================================================ */

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        noiseSuppression: true,
        echoCancellation: true,
        autoGainControl: true,
        channelCount: 1,
      },
    });

    audioChunks = [];

    let mimeType = "";

    if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
      mimeType = "audio/webm;codecs=opus";
    } else if (MediaRecorder.isTypeSupported("audio/webm")) {
      mimeType = "audio/webm";
    }

    mediaRecorder = mimeType
      ? new MediaRecorder(stream, {
          mimeType: mimeType,
        })
      : new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());

      const audioBlob = new Blob(audioChunks, {
        type: mediaRecorder.mimeType,
      });

      if (audioBlob.size === 0) {
        recordingStatus.textContent = "No audio recorded.";

        return;
      }

      const audioURL = URL.createObjectURL(audioBlob);

      recordedAudioContainer.innerHTML = "";

      const audio = document.createElement("audio");

      audio.controls = true;

      audio.src = audioURL;

      audio.style.width = "100%";

      recordedAudioContainer.appendChild(audio);

      await sendAudio(audioBlob);
    };

    mediaRecorder.start(1000);

    isRecording = true;

    recordButton.textContent = "⏹ Stop";

    recordingStatus.textContent = "🎤 Listening...";

    statusElement.textContent = "Listening...";
  } catch (error) {
    console.error("MICROPHONE ERROR:", error);

    recordingStatus.textContent = error.message;

    statusElement.textContent = "Microphone error";
  }
}

/* ============================================================
   STOP RECORDING
   ============================================================ */

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }

  isRecording = false;

  recordButton.textContent = "🎤 Speak";

  recordingStatus.textContent = "Processing speech...";

  statusElement.textContent = "Processing...";
}

/* ============================================================
   SEND AUDIO
   ============================================================ */

async function sendAudio(audioBlob) {
  try {
    const formData = new FormData();

    formData.append("file", audioBlob, "question.webm");

    formData.append("class_name", classSelect?.value || "");
    formData.append("subject", subjectSelect?.value || "");
    formData.append("book", bookSelect?.value || "");
    formData.append("language", languageSelect?.value || "auto");

    const response = await fetch("/speech/ask", {
      method: "POST",

      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Speech server error: ${response.status}`);
    }

    const data = await response.json();

    questionElement.value = data.question || "";

    if (data.corrected && data.raw_question) {
      recordingStatus.textContent = `Heard: ${data.raw_question} → Understood: ${data.question}`;
    } else {
      recordingStatus.textContent = `Heard: ${data.question || ""}`;
    }

    answerElement.textContent = data.answer || "";

    statusElement.textContent = "Answer ready";

    teacherState.textContent = "🟢 Ready";

    avatarSpeaking.textContent = "Here is your answer";

    if (data.audio_url) {
      showAnswerAudio(data.audio_url);
    }
  } catch (error) {
    console.error("SEND AUDIO ERROR:", error);

    statusElement.textContent = "Error";

    recordingStatus.textContent = error.message;
  }
}

/* ============================================================
   CLEAR ANSWER
   ============================================================ */

document.getElementById("clearAnswerButton").addEventListener("click", () => {
  answerElement.innerHTML = `
            <div class="empty-answer">

                <div class="empty-icon">
                    💡
                </div>

                <h3>
                    Ask me something!
                </h3>

                <p>
                    Your teacher's explanation
                    will appear here.
                </p>

            </div>
            `;

  answerAudioContainer.innerHTML = "";

  clearVisualBoard();

  statusElement.textContent = "Ready";

  teacherState.textContent = "🟢 Ready";

  avatarSpeaking.textContent = "Ready to help you learn";
});

/* ============================================================
   REPEAT ANSWER
   ============================================================ */

document.getElementById("repeatAnswerButton").addEventListener("click", () => {
  const audio = answerAudioContainer.querySelector("audio");

  if (audio) {
    audio.currentTime = 0;

    audio.play();

    return;
  }

  const text = answerElement.innerText.trim();

  if (text && "speechSynthesis" in window) {
    const speech = new SpeechSynthesisUtterance(text);

    speech.rate = 0.9;

    window.speechSynthesis.speak(speech);
  }
});

/* ============================================================
   SLOW SPEECH
   ============================================================ */

document.getElementById("slowSpeechButton").addEventListener("click", () => {
  const text = answerElement.innerText.trim();

  if (!text || !("speechSynthesis" in window)) {
    return;
  }

  window.speechSynthesis.cancel();

  const speech = new SpeechSynthesisUtterance(text);

  speech.rate = 0.55;

  speech.pitch = 1;

  window.speechSynthesis.speak(speech);
});

/* ============================================================
   STOP SPEECH
   ============================================================ */

document.getElementById("stopSpeechButton").addEventListener("click", () => {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }

  const audio = answerAudioContainer.querySelector("audio");

  if (audio) {
    audio.pause();
  }
});

/* ============================================================
   HTML ESCAPE
   ============================================================ */

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")

    .replaceAll("<", "&lt;")

    .replaceAll(">", "&gt;")

    .replaceAll('"', "&quot;")

    .replaceAll("'", "&#039;");
}



/* ============================================================
   QUESTION PAPER GENERATOR
   ============================================================ */

const questionPaperModal = document.getElementById("questionPaperModal");
const openQuestionPaperButton = document.getElementById(
  "openQuestionPaperButton",
);
const closeQuestionPaperModal = document.getElementById(
  "closeQuestionPaperModal",
);
const closeQuestionPaperButton = document.getElementById(
  "closeQuestionPaperButton",
);
const generateQuestionPaperButton = document.getElementById(
  "generateQuestionPaperButton",
);
const questionPaperStatus = document.getElementById(
  "questionPaperStatus",
);
const questionPaperResult = document.getElementById(
  "questionPaperResult",
);
const questionPaperResultActions = document.getElementById(
  "questionPaperResultActions",
);
const toggleAnswerKeyButton = document.getElementById(
  "toggleAnswerKeyButton",
);
const printQuestionPaperButton = document.getElementById(
  "printQuestionPaperButton",
);
const newQuestionPaperButton = document.getElementById(
  "newQuestionPaperButton",
);

let latestQuestionPaper = null;
let questionPaperAnswerKeyVisible = false;

function injectQuestionPaperStyles() {
  if (document.getElementById("questionPaperStyles")) return;

  const style = document.createElement("style");
  style.id = "questionPaperStyles";

  style.textContent = `
    /* ========================================================
       QUESTION PAPER BUTTON
       ======================================================== */

    #openQuestionPaperButton {
      border: 1px solid rgba(49, 94, 251, 0.20);
      background: linear-gradient(135deg, #eef2ff, #f8faff);
      color: #334155;
      border-radius: 10px;
      padding: 10px 14px;
      font-weight: 700;
      cursor: pointer;
      white-space: nowrap;
    }

    #openQuestionPaperButton:hover {
      transform: translateY(-1px);
      box-shadow: 0 8px 20px rgba(49, 94, 251, 0.12);
    }

    /* ========================================================
       MODAL
       ======================================================== */

    .question-paper-modal {
      position: fixed;
      inset: 0;
      z-index: 5000;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      background: rgba(15, 23, 42, 0.62);
      backdrop-filter: blur(6px);
      overflow-y: auto;
    }

    .question-paper-modal.hidden,
    .question-paper-result.hidden,
    .question-paper-result-actions.hidden {
      display: none !important;
    }

    .question-paper-dialog {
      width: min(1050px, 100%);
      max-height: calc(100vh - 40px);
      overflow-y: auto;
      background: #ffffff;
      border-radius: 20px;
      box-shadow: 0 24px 80px rgba(15, 23, 42, 0.28);
      padding: 22px;
    }

    .question-paper-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }

    .question-paper-header h2 {
      margin: 4px 0 4px;
      font-size: 26px;
      color: #172033;
    }

    .question-paper-header p {
      margin: 0;
      color: #64748b;
      font-size: 14px;
    }

    .question-paper-selection {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
      margin-bottom: 18px;
    }

    .qp-selection-card {
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 12px;
      background: #f8fafc;
      min-width: 0;
    }

    .qp-selection-card span {
      display: block;
      color: #64748b;
      font-size: 12px;
      margin-bottom: 4px;
    }

    .qp-selection-card strong {
      display: block;
      color: #1e293b;
      overflow-wrap: anywhere;
    }

    .question-paper-form {
      border: 1px solid #e2e8f0;
      border-radius: 16px;
      padding: 16px;
      background: #ffffff;
    }

    .qp-field label,
    .qp-count-field label {
      display: block;
      font-weight: 700;
      color: #334155;
      font-size: 13px;
      margin-bottom: 6px;
    }

    .qp-field input,
    .qp-field select,
    .qp-count-field input {
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #cbd5e1;
      border-radius: 9px;
      padding: 10px 11px;
      background: #fff;
      color: #1e293b;
    }

    .question-paper-form > .qp-field:first-child {
      display: inline-block;
      width: 48%;
      margin-right: 3%;
      vertical-align: top;
    }

    .question-paper-form > .qp-field:nth-child(2) {
      display: inline-block;
      width: 48%;
      vertical-align: top;
    }

    .qp-count-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
      margin-top: 14px;
    }

    .qp-count-field {
      padding: 11px;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      background: #f8fafc;
    }

    .question-paper-status {
      margin-top: 14px;
      padding: 10px 12px;
      border-radius: 10px;
      background: #f8fafc;
      color: #64748b;
      font-size: 13px;
      white-space: pre-wrap;
    }

    .question-paper-status.loading {
      background: #eff6ff;
      color: #1d4ed8;
    }

    .question-paper-status.error {
      background: #fef2f2;
      color: #b91c1c;
    }

    .question-paper-status.success {
      background: #f0fdf4;
      color: #166534;
    }

    .question-paper-actions,
    .question-paper-result-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 9px;
      margin-top: 14px;
    }

    .question-paper-actions button,
    .question-paper-result-actions button {
      border: 0;
      border-radius: 9px;
      padding: 10px 14px;
      font-weight: 700;
      cursor: pointer;
    }

    .generate-question-paper-button {
      background: #315efb;
      color: white;
    }

    .secondary-question-paper-button {
      background: #e2e8f0;
      color: #334155;
    }

    .question-paper-result-actions button {
      background: #eef2ff;
      color: #334155;
    }

    .question-paper-result {
      margin-top: 18px;
      border: 1px solid #dbe2ea;
      border-radius: 16px;
      background: #fff;
      padding: 26px;
    }

    .qp-paper {
      max-width: 900px;
      margin: 0 auto;
      color: #172033;
    }

    .qp-paper-header {
      text-align: center;
      border-bottom: 2px solid #1e293b;
      padding-bottom: 14px;
      margin-bottom: 18px;
    }

    .qp-paper-header h1 {
      margin: 0 0 5px;
      font-size: 25px;
    }

    .qp-paper-header h2 {
      margin: 0 0 10px;
      font-size: 20px;
    }

    .qp-meta {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 8px 18px;
      font-size: 13px;
      color: #475569;
    }

    .qp-instructions {
      margin: 15px 0 20px;
      padding: 11px 13px;
      background: #f8fafc;
      border-radius: 8px;
      font-size: 13px;
    }

    .qp-section {
      margin-top: 22px;
    }

    .qp-section h3 {
      margin: 0 0 12px;
      padding-bottom: 7px;
      border-bottom: 1px solid #cbd5e1;
      font-size: 18px;
    }

    .qp-question {
      margin: 0 0 18px;
      line-height: 1.6;
      break-inside: avoid;
    }

    .qp-question-number {
      font-weight: 800;
      margin-right: 4px;
    }

    .qp-options {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 4px 18px;
      margin: 7px 0 0 24px;
    }

    .qp-option {
      padding: 2px 0;
    }

    .qp-answer-line {
      display: inline-block;
      min-width: 230px;
      border-bottom: 1px solid #334155;
      transform: translateY(-3px);
    }

    .qp-answer-key {
      display: none;
      margin-top: 25px;
      border-top: 2px dashed #94a3b8;
      padding-top: 18px;
    }

    .qp-answer-key.visible {
      display: block;
    }

    .qp-key-item {
      margin: 5px 0;
      line-height: 1.5;
    }

    .qp-footer-note {
      margin-top: 24px;
      text-align: center;
      color: #64748b;
      font-size: 12px;
    }

    @media (max-width: 800px) {
      .question-paper-modal {
        padding: 8px;
      }

      .question-paper-dialog {
        max-height: calc(100vh - 16px);
        padding: 14px;
        border-radius: 14px;
      }

      .question-paper-selection,
      .qp-count-grid {
        grid-template-columns: 1fr 1fr;
      }

      .question-paper-form > .qp-field:first-child,
      .question-paper-form > .qp-field:nth-child(2) {
        display: block;
        width: 100%;
        margin-right: 0;
        margin-bottom: 12px;
      }

      .qp-options {
        grid-template-columns: 1fr;
      }

      .question-paper-result {
        padding: 15px;
      }
    }

    @media (max-width: 500px) {
      .question-paper-selection,
      .qp-count-grid {
        grid-template-columns: 1fr;
      }

      .question-paper-header h2 {
        font-size: 21px;
      }
    }

    @media print {
      body > * {
        display: none !important;
      }

      #questionPaperModal {
        display: block !important;
        position: static !important;
        background: white !important;
        padding: 0 !important;
      }

      #questionPaperModal .question-paper-dialog {
        display: block !important;
        max-height: none !important;
        width: 100% !important;
        box-shadow: none !important;
        padding: 0 !important;
        overflow: visible !important;
      }

      #questionPaperModal .question-paper-header,
      #questionPaperModal .question-paper-form,
      #questionPaperModal .question-paper-result-actions {
        display: none !important;
      }

      #questionPaperModal .question-paper-result {
        display: block !important;
        border: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
      }

      #questionPaperModal .qp-answer-key {
        display: none !important;
      }

      #questionPaperModal .qp-paper {
        max-width: none !important;
      }
    }
  `;

  document.head.appendChild(style);
}

function updateQuestionPaperSelection() {
  const qpClass = document.getElementById("qpSelectedClass");
  const qpSubject = document.getElementById("qpSelectedSubject");
  const qpBook = document.getElementById("qpSelectedBook");

  if (qpClass) {
    qpClass.textContent = classSelect?.value || "—";
  }

  if (qpSubject) {
    qpSubject.textContent = getSubjectDisplayName(subjectSelect?.value || "");
  }

  if (qpBook) {
    qpBook.textContent = getSelectedBookName() || "—";
  }
}

function resetQuestionPaperResult() {
  latestQuestionPaper = null;
  questionPaperAnswerKeyVisible = false;

  if (questionPaperResult) {
    questionPaperResult.innerHTML = "";
    questionPaperResult.classList.add("hidden");
  }

  if (questionPaperResultActions) {
    questionPaperResultActions.classList.add("hidden");
  }

  if (toggleAnswerKeyButton) {
    toggleAnswerKeyButton.textContent = "🔑 Show Answer Key";
  }
}

function openQuestionPaperModal() {
  updateQuestionPaperSelection();
  resetQuestionPaperResult();

  if (questionPaperStatus) {
    questionPaperStatus.className = "question-paper-status";
    questionPaperStatus.textContent =
      "Select a class, subject and textbook, then generate the paper.";
  }

  if (questionPaperModal) {
    questionPaperModal.classList.remove("hidden");
    questionPaperModal.setAttribute("aria-hidden", "false");
  }
}

function closeQuestionPaperPopup() {
  if (questionPaperModal) {
    questionPaperModal.classList.add("hidden");
    questionPaperModal.setAttribute("aria-hidden", "true");
  }
}

function validateQuestionPaperSelection() {
  const selectedClass = normalizeClass(classSelect?.value || "");
  const selectedSubject = normalizeSubject(subjectSelect?.value || "");
  const selectedBook = bookSelect?.value || "";

  if (!selectedClass) {
    throw new Error("Please select your class first.");
  }

  if (!selectedSubject) {
    throw new Error("Please select a subject first.");
  }

  if (!selectedBook) {
    throw new Error("Please select a textbook first.");
  }

  return {
    class_name: selectedClass,
    subject: selectedSubject,
    book: selectedBook,
  };
}

function getQuestionPaperCounts() {
  const getCount = (id) => {
    const value = Number(document.getElementById(id)?.value ?? 0);

    if (!Number.isFinite(value) || value < 0 || value > 50) {
      throw new Error("Each question count must be between 0 and 50.");
    }

    return Math.floor(value);
  };

  const counts = {
    mcq_count: getCount("qpMcqCount"),
    fill_blank_count: getCount("qpFillBlankCount"),
    true_false_count: getCount("qpTrueFalseCount"),
    short_answer_count: getCount("qpShortAnswerCount"),
  };

  const total =
    counts.mcq_count +
    counts.fill_blank_count +
    counts.true_false_count +
    counts.short_answer_count;

  if (total === 0) {
    throw new Error("Please request at least one question.");
  }

  return counts;
}

async function generateQuestionPaper() {
  if (!generateQuestionPaperButton) return;

  try {
    const selection = validateQuestionPaperSelection();
    const counts = getQuestionPaperCounts();

    const lessonNumber = Number(
      document.getElementById("qpLessonNumber")?.value ?? 0,
    );

    if (!Number.isInteger(lessonNumber) || lessonNumber < 1) {
      throw new Error("Please enter a valid lesson number.");
    }

    const language =
      document.getElementById("qpLanguage")?.value ||
      languageSelect?.value ||
      "auto";

    const requestBody = {
      lesson_number: lessonNumber,
      class_name: selection.class_name,
      subject: selection.subject,
      book: selection.book,
      language,
      ...counts,
    };

    console.log("QUESTION PAPER REQUEST:", requestBody);

    generateQuestionPaperButton.disabled = true;

    if (questionPaperStatus) {
      questionPaperStatus.className = "question-paper-status loading";
      questionPaperStatus.textContent =
        "⏳ Generating a textbook-grounded question paper...\\n" +
        "The server will validate every question against the selected lesson.";
    }

    resetQuestionPaperResult();

    const response = await fetch("/api/question-paper", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestBody),
    });

    const raw = await response.text();

    console.log("QUESTION PAPER STATUS:", response.status);
    console.log("QUESTION PAPER RESPONSE:", raw);

    let data = {};

    try {
      data = JSON.parse(raw);
    } catch {
      data = { detail: raw };
    }

    if (!response.ok) {
      throw new Error(
        data.detail ||
          data.message ||
          `Question paper generation failed with HTTP ${response.status}`,
      );
    }

    latestQuestionPaper = data;
    renderQuestionPaper(data);

    if (questionPaperStatus) {
      questionPaperStatus.className = "question-paper-status success";
      questionPaperStatus.textContent =
        `✅ Question paper generated successfully. ` +
        `${Number(data.total_questions ?? 0)} questions created.`;
    }

    if (questionPaperResultActions) {
      questionPaperResultActions.classList.remove("hidden");
    }

    if (questionPaperResult) {
      questionPaperResult.classList.remove("hidden");
    }
  } catch (error) {
    console.error("QUESTION PAPER ERROR:", error);

    if (questionPaperStatus) {
      questionPaperStatus.className = "question-paper-status error";
      questionPaperStatus.textContent =
        `❌ ${error.message || "Could not generate the question paper."}`;
    }
  } finally {
    generateQuestionPaperButton.disabled = false;
  }
}

function renderQuestionPaper(data) {
  if (!questionPaperResult) return;

  const lessonNumber = data.lesson_number ?? "";
  const lessonTitle = data.lesson_title || "Lesson";
  const language = data.language || "Auto";
  const totalQuestions = data.total_questions ?? 0;
  const source = data.source || {};

  const mcqs = Array.isArray(data.mcqs) ? data.mcqs : [];
  const fillBlanks = Array.isArray(data.fill_in_the_blanks)
    ? data.fill_in_the_blanks
    : [];
  const trueFalse = Array.isArray(data.true_false)
    ? data.true_false
    : [];
  const shortAnswers = Array.isArray(data.short_answers)
    ? data.short_answers
    : [];

  let questionNumber = 1;
  let answerKeyHtml = "";

  const escape = (value) => escapeHtml(String(value ?? ""));

  const renderMcqs = () => {
    if (!mcqs.length) return "";

    let html = `
      <section class="qp-section">
        <h3>A. Multiple Choice Questions</h3>
    `;

    mcqs.forEach((item) => {
      const options = item.options || {};
      const optionKeys = ["A", "B", "C", "D"];

      html += `
        <div class="qp-question">
          <div>
            <span class="qp-question-number">${questionNumber}.</span>
            ${escape(item.question)}
          </div>
          <div class="qp-options">
            ${optionKeys
              .map(
                (key) => `
                  <div class="qp-option">
                    <strong>${key}.</strong> ${escape(options[key] ?? "")}
                  </div>
                `,
              )
              .join("")}
          </div>
        </div>
      `;

      answerKeyHtml += `
        <div class="qp-key-item">
          <strong>${questionNumber}.</strong>
          ${escape(item.answer || "")}
          ${
            options[item.answer]
              ? ` — ${escape(options[item.answer])}`
              : ""
          }
        </div>
      `;

      questionNumber += 1;
    });

    html += "</section>";
    return html;
  };

  const renderFillBlanks = () => {
    if (!fillBlanks.length) return "";

    let html = `
      <section class="qp-section">
        <h3>B. Fill in the Blanks</h3>
    `;

    fillBlanks.forEach((item) => {
      html += `
        <div class="qp-question">
          <span class="qp-question-number">${questionNumber}.</span>
          ${escape(item.question)}
        </div>
      `;

      answerKeyHtml += `
        <div class="qp-key-item">
          <strong>${questionNumber}.</strong>
          ${escape(item.answer || "")}
        </div>
      `;

      questionNumber += 1;
    });

    html += "</section>";
    return html;
  };

  const renderTrueFalse = () => {
    if (!trueFalse.length) return "";

    let html = `
      <section class="qp-section">
        <h3>C. True / False</h3>
    `;

    trueFalse.forEach((item) => {
      html += `
        <div class="qp-question">
          <span class="qp-question-number">${questionNumber}.</span>
          ${escape(item.question)}
          <strong style="margin-left:8px;">(True / False)</strong>
        </div>
      `;

      answerKeyHtml += `
        <div class="qp-key-item">
          <strong>${questionNumber}.</strong>
          ${item.answer ? "True" : "False"}
        </div>
      `;

      questionNumber += 1;
    });

    html += "</section>";
    return html;
  };

  const renderShortAnswers = () => {
    if (!shortAnswers.length) return "";

    let html = `
      <section class="qp-section">
        <h3>D. Short Answer Questions</h3>
    `;

    shortAnswers.forEach((item) => {
      html += `
        <div class="qp-question">
          <span class="qp-question-number">${questionNumber}.</span>
          ${escape(item.question)}
          <div style="margin-top:12px;">
            <span class="qp-answer-line"></span>
          </div>
        </div>
      `;

      answerKeyHtml += `
        <div class="qp-key-item">
          <strong>${questionNumber}.</strong>
          ${escape(item.answer || "")}
        </div>
      `;

      questionNumber += 1;
    });

    html += "</section>";
    return html;
  };

  const sourceText =
    source.book ||
    getSelectedBookName() ||
    bookSelect?.value ||
    "";

  questionPaperResult.innerHTML = `
    <div class="qp-paper" id="printableQuestionPaper">

      <div class="qp-paper-header">
        <h1>Question Paper</h1>
        <h2>${escape(lessonTitle)}</h2>

        <div class="qp-meta">
          <span><strong>Class:</strong> ${escape(
            data.class_name || classSelect?.value || "",
          )}</span>
          <span><strong>Subject:</strong> ${escape(
            data.subject || getSubjectDisplayName(subjectSelect?.value || ""),
          )}</span>
          <span><strong>Lesson:</strong> ${escape(lessonNumber)}</span>
          <span><strong>Language:</strong> ${escape(language)}</span>
          <span><strong>Total:</strong> ${escape(totalQuestions)}</span>
        </div>
      </div>

      <div class="qp-instructions">
        <strong>Instructions:</strong>
        Read each question carefully and answer all questions.
      </div>

      ${renderMcqs()}
      ${renderFillBlanks()}
      ${renderTrueFalse()}
      ${renderShortAnswers()}

      <div class="qp-answer-key" id="qpAnswerKey">
        <h3>Answer Key</h3>
        ${answerKeyHtml || "<p>No answer key available.</p>"}
      </div>

      <div class="qp-footer-note">
        Source textbook: ${escape(sourceText)}
      </div>
    </div>
  `;
}

function toggleQuestionPaperAnswerKey() {
  const key = document.getElementById("qpAnswerKey");

  if (!key || !toggleAnswerKeyButton) return;

  questionPaperAnswerKeyVisible = !questionPaperAnswerKeyVisible;

  key.classList.toggle(
    "visible",
    questionPaperAnswerKeyVisible,
  );

  toggleAnswerKeyButton.textContent = questionPaperAnswerKeyVisible
    ? "🙈 Hide Answer Key"
    : "🔑 Show Answer Key";
}

function printQuestionPaper() {
  if (!latestQuestionPaper) return;

  const wasVisible = questionPaperAnswerKeyVisible;

  // Always print the student paper without the answer key.
  const key = document.getElementById("qpAnswerKey");
  key?.classList.remove("visible");

  window.print();

  if (wasVisible) {
    key?.classList.add("visible");
  }
}

function resetQuestionPaperForm() {
  resetQuestionPaperResult();

  if (questionPaperStatus) {
    questionPaperStatus.className = "question-paper-status";
    questionPaperStatus.textContent =
      "Select a class, subject and textbook, then generate the paper.";
  }
}

injectQuestionPaperStyles();

openQuestionPaperButton?.addEventListener(
  "click",
  openQuestionPaperModal,
);

closeQuestionPaperModal?.addEventListener(
  "click",
  closeQuestionPaperPopup,
);

closeQuestionPaperButton?.addEventListener(
  "click",
  closeQuestionPaperPopup,
);

generateQuestionPaperButton?.addEventListener(
  "click",
  generateQuestionPaper,
);

toggleAnswerKeyButton?.addEventListener(
  "click",
  toggleQuestionPaperAnswerKey,
);

printQuestionPaperButton?.addEventListener(
  "click",
  printQuestionPaper,
);

newQuestionPaperButton?.addEventListener(
  "click",
  resetQuestionPaperForm,
);

questionPaperModal?.addEventListener("click", (event) => {
  if (event.target === questionPaperModal) {
    closeQuestionPaperPopup();
  }
});

document.addEventListener("keydown", (event) => {
  if (
    event.key === "Escape" &&
    questionPaperModal &&
    !questionPaperModal.classList.contains("hidden")
  ) {
    closeQuestionPaperPopup();
  }
});

// Keep the Question Paper modal's selected-book display synchronized
// with the existing Class / Subject / Textbook controls.
classSelect?.addEventListener("change", updateQuestionPaperSelection);
subjectSelect?.addEventListener("change", updateQuestionPaperSelection);
bookSelect?.addEventListener("change", updateQuestionPaperSelection);


/* ============================================================
   ORAL TEST — PHASE 3 CONFIGURATION
   ============================================================ */

const oralTestModal = document.getElementById("oralTestModal");
const openOralTestButton = document.getElementById("openOralTestButton");
const closeOralTestModal = document.getElementById("closeOralTestModal");
const closeOralTestButton = document.getElementById("closeOralTestButton");
const prepareOralTestButton = document.getElementById("prepareOralTestButton");
const oralTestStatus = document.getElementById("oralTestStatus");
const oralTestPreview = document.getElementById("oralTestPreview");

let oralTestConfiguration = null;

function updateOralTestSelection() {
  const classValue = classSelect?.value || "";
  const subjectValue = subjectSelect?.value || "";
  const bookValue = bookSelect?.value || "";

  const classDisplay = document.getElementById("oralSelectedClass");
  const subjectDisplay = document.getElementById("oralSelectedSubject");
  const bookDisplay = document.getElementById("oralSelectedBook");

  if (classDisplay) classDisplay.textContent = classValue || "—";
  if (subjectDisplay) {
    subjectDisplay.textContent =
      typeof getSubjectDisplayName === "function"
        ? getSubjectDisplayName(subjectValue) || "—"
        : subjectValue || "—";
  }
  if (bookDisplay) {
    bookDisplay.textContent =
      typeof getSelectedBookName === "function"
        ? getSelectedBookName() || bookValue || "—"
        : bookValue || "—";
  }
}

function openOralTestModal() {
  updateOralTestSelection();
  if (oralTestStatus) {
    oralTestStatus.className = "oral-test-status";
    oralTestStatus.textContent =
      "Configure the test, then continue to question-bank preparation.";
  }
  oralTestModal?.classList.remove("hidden");
  oralTestModal?.setAttribute("aria-hidden", "false");
}

function closeOralTestPopup() {
  oralTestModal?.classList.add("hidden");
  oralTestModal?.setAttribute("aria-hidden", "true");
}

function getOralQuestionTypes() {
  return Array.from(
    document.querySelectorAll('input[name="oralQuestionType"]:checked'),
  ).map((input) => input.value);
}

function prepareOralTest() {
  const className = classSelect?.value || "";
  const subject = subjectSelect?.value || "";
  const book = bookSelect?.value || "";
  const lessonNumber = Number(
    document.getElementById("oralLessonNumber")?.value || 0,
  );
  const language =
    document.getElementById("oralLanguage")?.value || "auto";
  const studentCount = Number(
    document.getElementById("oralStudentCount")?.value || 0,
  );
  const questionsPerStudent = Number(
    document.getElementById("oralQuestionsPerStudent")?.value || 0,
  );
  const difficulty =
    document.getElementById("oralDifficulty")?.value || "mixed";
  const timeLimit = Number(
    document.getElementById("oralTimeLimit")?.value || 0,
  );
  const questionTypes = getOralQuestionTypes();

  if (!className || !subject || !book) {
    throw new Error(
      "Please select the class, subject and textbook in the main controls first.",
    );
  }

  if (!Number.isInteger(lessonNumber) || lessonNumber < 1) {
    throw new Error("Please enter a valid lesson number.");
  }

  if (!Number.isInteger(studentCount) || studentCount < 1) {
    throw new Error("Number of students must be at least 1.");
  }

  if (!Number.isInteger(questionsPerStudent) || questionsPerStudent < 1) {
    throw new Error("Questions per student must be at least 1.");
  }

  if (!questionTypes.length) {
    throw new Error("Select at least one question type.");
  }

  oralTestConfiguration = {
    class_name: className,
    subject,
    book,
    lesson_number: lessonNumber,
    language,
    student_count: studentCount,
    questions_per_student: questionsPerStudent,
    difficulty,
    time_limit_seconds: timeLimit,
    question_types: questionTypes,
  };

  console.log("ORAL TEST CONFIGURATION:", oralTestConfiguration);

  if (oralTestStatus) {
    oralTestStatus.className = "oral-test-status success";
    oralTestStatus.textContent =
      "✅ Oral test configuration saved. The next step will build and validate the question bank.";
  }

  if (oralTestPreview) {
    oralTestPreview.classList.remove("hidden");
    oralTestPreview.innerHTML = `
      <div class="oral-preview-header">🎯 Test Configuration Ready</div>
      <div class="oral-preview-grid">
        <div><strong>Students</strong><span>${studentCount}</span></div>
        <div><strong>Questions each</strong><span>${questionsPerStudent}</span></div>
        <div><strong>Total responses</strong><span>${studentCount * questionsPerStudent}</span></div>
        <div><strong>Difficulty</strong><span>${escapeHtml(difficulty)}</span></div>
        <div><strong>Time</strong><span>${timeLimit === 0 ? "No limit" : `${timeLimit}s`}</span></div>
        <div><strong>Types</strong><span>${questionTypes.length}</span></div>
      </div>
      <p>Roll-number randomization, textbook-grounded question selection, speech capture and scoring will be connected in the next step.</p>
    `;
  }
}

function injectOralTestStyles() {
  if (document.getElementById("oralTestStyles")) return;

  const style = document.createElement("style");
  style.id = "oralTestStyles";
  style.textContent = `
    #openOralTestButton {
      border: 1px solid rgba(124, 58, 237, 0.18);
      background: linear-gradient(135deg, #f5f3ff, #faf5ff);
      color: #5b21b6;
      border-radius: 10px;
      padding: 10px 14px;
      font-weight: 700;
      cursor: pointer;
      white-space: nowrap;
    }
    #openOralTestButton:hover { transform: translateY(-1px); }
    .oral-test-modal {
      position: fixed;
      inset: 0;
      z-index: 5100;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      background: rgba(15, 23, 42, .64);
      backdrop-filter: blur(6px);
      overflow-y: auto;
    }
    .oral-test-modal.hidden { display: none !important; }
    .oral-test-dialog {
      width: min(1050px, 100%);
      max-height: calc(100vh - 40px);
      overflow-y: auto;
      background: #fff;
      border-radius: 20px;
      box-shadow: 0 24px 80px rgba(15,23,42,.28);
      padding: 22px;
    }
    .oral-test-header {
      display:flex; align-items:flex-start; justify-content:space-between;
      gap:16px; margin-bottom:18px;
    }
    .oral-test-header h2 { margin:4px 0; font-size:26px; color:#172033; }
    .oral-test-header p { margin:0; color:#64748b; font-size:14px; }
    .oral-selection-grid {
      display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:18px;
    }
    .oral-selection-card {
      border:1px solid #e2e8f0; border-radius:12px; padding:12px; background:#f8fafc; min-width:0;
    }
    .oral-selection-card span { display:block; color:#64748b; font-size:12px; margin-bottom:4px; }
    .oral-selection-card strong { display:block; color:#1e293b; overflow-wrap:anywhere; }
    .oral-form { border:1px solid #e2e8f0; border-radius:16px; padding:16px; }
    .oral-form-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
    .oral-field label { display:block; font-weight:700; color:#334155; font-size:13px; margin-bottom:6px; }
    .oral-field input, .oral-field select {
      width:100%; box-sizing:border-box; border:1px solid #cbd5e1; border-radius:9px;
      padding:10px 11px; background:#fff; color:#1e293b;
    }
    .oral-question-types {
      margin-top:16px; padding:13px; border:1px solid #e2e8f0; border-radius:12px; background:#f8fafc;
      display:flex; flex-wrap:wrap; gap:12px; align-items:center;
    }
    .oral-subtitle { width:100%; font-weight:800; color:#334155; }
    .oral-question-types label { font-size:13px; color:#334155; font-weight:600; }
    .oral-question-types input { margin-right:5px; }
    .oral-test-status {
      margin-top:14px; padding:10px 12px; border-radius:10px; background:#f8fafc; color:#64748b;
      font-size:13px; white-space:pre-wrap;
    }
    .oral-test-status.success { background:#f0fdf4; color:#166534; }
    .oral-test-status.error { background:#fef2f2; color:#b91c1c; }
    .oral-test-actions { display:flex; flex-wrap:wrap; gap:9px; margin-top:14px; }
    .oral-test-actions button { border:0; border-radius:9px; padding:10px 14px; font-weight:700; cursor:pointer; }
    .prepare-oral-test-button { background:#7c3aed; color:#fff; }
    .secondary-oral-test-button { background:#e2e8f0; color:#334155; }
    .oral-test-preview { margin-top:16px; border:1px solid #ddd6fe; border-radius:14px; padding:15px; background:#faf5ff; }
    .oral-test-preview.hidden { display:none; }
    .oral-preview-header { font-weight:800; color:#5b21b6; margin-bottom:12px; }
    .oral-preview-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
    .oral-preview-grid div { background:#fff; border:1px solid #ede9fe; border-radius:10px; padding:10px; }
    .oral-preview-grid strong { display:block; color:#64748b; font-size:11px; }
    .oral-preview-grid span { display:block; color:#1e293b; font-weight:800; margin-top:3px; }
    .oral-test-preview p { color:#64748b; font-size:13px; margin:12px 0 0; }
    @media (max-width: 760px) {
      .oral-selection-grid, .oral-form-grid, .oral-preview-grid { grid-template-columns:1fr; }
    }
  `;
  document.head.appendChild(style);
}

injectOralTestStyles();

openOralTestButton?.addEventListener("click", openOralTestModal);
closeOralTestModal?.addEventListener("click", closeOralTestPopup);
closeOralTestButton?.addEventListener("click", closeOralTestPopup);
prepareOralTestButton?.addEventListener("click", () => {
  try {
    prepareOralTest();
  } catch (error) {
    if (oralTestStatus) {
      oralTestStatus.className = "oral-test-status error";
      oralTestStatus.textContent = `❌ ${error.message}`;
    }
  }
});

oralTestModal?.addEventListener("click", (event) => {
  if (event.target === oralTestModal) closeOralTestPopup();
});

classSelect?.addEventListener("change", updateOralTestSelection);
subjectSelect?.addEventListener("change", updateOralTestSelection);
bookSelect?.addEventListener("change", updateOralTestSelection);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && oralTestModal && !oralTestModal.classList.contains("hidden")) {
    closeOralTestPopup();
  }
});
