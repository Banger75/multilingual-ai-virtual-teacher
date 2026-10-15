console.log("Book manager loaded");


const uploadBookButton =
    document.getElementById(
        "uploadBookButton"
    );

const bookFile =
    document.getElementById(
        "bookFile"
    );

const bookSubject =
    document.getElementById(
        "bookSubject"
    );

const bookClass =
    document.getElementById(
        "bookClass"
    );

const bookUploadStatus =
    document.getElementById(
        "bookUploadStatus"
    );

const activeBook =
    document.getElementById(
        "activeBook"
    );


/*
==================================================
BOOK STORAGE
==================================================
*/

let uploadedBooks =
    JSON.parse(
        localStorage.getItem(
            "virtualTeacherBooks"
        ) || "[]"
    );


/*
==================================================
UPLOAD BUTTON
==================================================
*/

if (uploadBookButton) {

    uploadBookButton.addEventListener(
        "click",
        uploadBook
    );

}


/*
==================================================
UPLOAD BOOK
==================================================
*/

async function uploadBook() {

    const file =
        bookFile.files[0];


    if (!file) {

        bookUploadStatus.textContent =
            "Please select a PDF textbook.";

        return;
    }


    if (
        !file.name
            .toLowerCase()
            .endsWith(".pdf")
    ) {

        bookUploadStatus.textContent =
            "Only PDF files are supported.";

        return;
    }


    const subject =
        bookSubject.value;


    const classLevel =
        bookClass.value;


    const formData =
        new FormData();


    formData.append(
        "file",
        file
    );


    formData.append(
        "subject",
        subject
    );


    formData.append(
        "class_level",
        classLevel
    );


    uploadBookButton.disabled =
        true;


    bookUploadStatus.textContent =
        "Uploading and indexing textbook...";


    try {

        const response =
            await fetch(
                "/api/books/upload",
                {
                    method: "POST",
                    body: formData
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "Book upload failed."
            );

        }


        console.log(
            "BOOK RESPONSE:",
            data
        );


        /*
        ==========================================
        SAVE BOOK INFORMATION
        ==========================================
        */

        const book = {

            book_id:
                data.book_id,

            book_name:
                data.book_name,

            subject:
                data.subject,

            class_level:
                data.class_level,

            chunks:
                data.chunks

        };


        uploadedBooks.push(
            book
        );


        localStorage.setItem(
            "virtualTeacherBooks",
            JSON.stringify(
                uploadedBooks
            )
        );


        /*
        ==========================================
        UPDATE SELECTOR
        ==========================================
        */

        loadBookSelector();


        /*
        ==========================================
        STATUS
        ==========================================
        */

        bookUploadStatus.textContent =
            `✓ ${data.book_name} indexed successfully. ` +
            `${data.chunks} chunks created.`;


        bookFile.value = "";


    } catch (error) {

        console.error(
            "BOOK UPLOAD ERROR:",
            error
        );


        bookUploadStatus.textContent =
            `❌ ${error.message}`;


    } finally {

        uploadBookButton.disabled =
            false;

    }

}


/*
==================================================
LOAD BOOK SELECTOR
==================================================
*/

function loadBookSelector() {

    if (!activeBook) {
        return;
    }


    activeBook.innerHTML = "";


    const defaultOption =
        document.createElement(
            "option"
        );


    defaultOption.value = "";


    defaultOption.textContent =
        "Select a textbook";


    activeBook.appendChild(
        defaultOption
    );


    uploadedBooks.forEach(
        book => {

            const option =
                document.createElement(
                    "option"
                );


            option.value =
                book.book_id;


            option.textContent =
                `${book.book_name} — ` +
                `${book.subject} — ` +
                `Class ${book.class_level}`;


            option.dataset.subject =
                book.subject;


            option.dataset.classLevel =
                book.class_level;


            activeBook.appendChild(
                option
            );

        }
    );

}


/*
==================================================
BOOK SELECTED
==================================================
*/

if (activeBook) {

    activeBook.addEventListener(
        "change",
        () => {

            const selectedOption =
                activeBook
                    .selectedOptions[0];


            if (!selectedOption) {
                return;
            }


            localStorage.setItem(
                "activeBookId",
                activeBook.value
            );


            localStorage.setItem(
                "activeBookSubject",
                selectedOption.dataset.subject ||
                ""
            );


            localStorage.setItem(
                "activeBookClass",
                selectedOption.dataset.classLevel ||
                ""
            );


            console.log(
                "ACTIVE BOOK:",
                activeBook.value
            );

        }
    );

}


/*
==================================================
INITIAL LOAD
==================================================
*/

loadBookSelector();