from flask import Flask, render_template, request, redirect, send_file, url_for, flash
import PyPDF2
import pdfplumber
import fitz  # PyMuPDF (MuPDF)
from gtts import gTTS
from googletrans import Translator
from langdetect import detect, DetectorFactory, LangDetectException  # ✅ Language Detection
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')

DetectorFactory.seed = 0  # Ensure consistent language detection results


# ========= PDF Extraction Functions =========

# Extract PDF text using PyPDF2
def extract_text_pyPDF2(pdf_path):
    """Extract text using PyPDF2"""
    try:
        text = ""
        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                page_text = pdf_reader.pages[page_num].extract_text() or ""
                text += page_text
        return text.strip() if text else None
    except Exception as e:
        flash(f"⚠️ PyPDF2 extraction failed: {str(e)}", "error")
        return None


# Extract PDF text using pdfplumber
def extract_text_pdfplumber(pdf_path):
    """Extract text using pdfplumber"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text
        return text.strip() if text else None
    except Exception as e:
        flash(f"⚠️ pdfplumber extraction failed: {str(e)}", "error")
        return None


# Extract PDF text using PyMuPDF
def extract_text_PyMuPDF(pdf_path):
    """Extract text using PyMuPDF"""
    try:
        text = ""
        pdf_document = fitz.open(pdf_path)
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            page_text = page.get_text() or ""
            text += page_text
        pdf_document.close()
        return text.strip() if text else None
    except Exception as e:
        flash(f"⚠️ PyMuPDF extraction failed: {str(e)}", "error")
        return None


# ========= Language Detection & Translation Functions =========

# Detect the language of the extracted text
def detect_language(text):
    """Automatically detect the language of the extracted text"""
    try:
        detected_lang = detect(text)
        return detected_lang
    except LangDetectException:
        flash("⚠️ Could not detect the language.", "error")
        return None


# Translate text
def translate_text(text, target_language):
    """Translate text to target language"""
    try:
        if not text or not target_language:
            flash("⚠️ No text or invalid language specified.", "error")
            return None

        translator = Translator()
        translated = translator.translate(text, dest=target_language)

        if translated and translated.text:
            return translated.text
        else:
            flash("⚠️ Translation returned empty.", "error")
            return None

    except Exception as e:
        flash(f"❌ Translation failed: {str(e)}", "error")
        return None


# Convert text to speech with dynamic filename
def convert_text_to_speech(text, output_filename):
    """Convert translated text to speech and save with custom filename"""
    try:
        if not text.strip():
            flash("⚠️ No text provided for speech synthesis.", "error")
            return None

        speech = gTTS(text)
        speech.save(output_filename)
        return output_filename

    except Exception as e:
        flash(f"❌ Text-to-speech conversion failed: {str(e)}", "error")
        return None


# ========= Flask Routes =========

@app.route("/", methods=["GET", "POST"])
def index():
    """Main route to upload PDF and convert to speech"""
    if request.method == "POST":
        pdf_file = request.files.get("pdf")
        target_language = request.form.get("target_language")

        # Validate input
        if not pdf_file or not pdf_file.filename.endswith('.pdf'):
            flash("❌ Please upload a valid PDF file.", "error")
            return redirect(url_for("index"))

        if not target_language:
            flash("❌ Please select a target language.", "error")
            return redirect(url_for("index"))

        # Save uploaded PDF temporarily
        pdf_name = os.path.splitext(pdf_file.filename)[0]  # Extract PDF name without extension
        pdf_path = f"{pdf_name}.pdf"
        pdf_file.save(pdf_path)

        # Try multiple extraction methods
        text = (
            extract_text_pyPDF2(pdf_path) or
            extract_text_pdfplumber(pdf_path) or
            extract_text_PyMuPDF(pdf_path)
        )

        # Remove the temporary PDF file
        os.remove(pdf_path)

        # Validate extracted text
        if not text:
            flash("❌ Failed to extract text from PDF. The file may contain images or unrecognizable content.", "error")
            return redirect(url_for("index"))

        # Automatically detect the language
        detected_lang = detect_language(text)
        if detected_lang:
            flash(f"🌐 Detected language: {detected_lang.upper()}", "info")
        else:
            flash("⚠️ Could not detect language. Proceeding with translation.", "warning")

        # Translate extracted text
        translated_text = translate_text(text, target_language)

        if not translated_text:
            flash("❌ Translation failed. Please try again.", "error")
            return redirect(url_for("index"))

        # Convert translated text to speech with dynamic filename
        audio_filename = f"{pdf_name}.mp3"  # Save as PDF name
        speech = convert_text_to_speech(translated_text, audio_filename)

        if not speech:
            flash("❌ Text-to-speech conversion failed.", "error")
            return redirect(url_for("index"))

        flash("✅ PDF converted to speech successfully!", "success")

        # Redirect to result page with audio filename
        return redirect(url_for("result", filename=audio_filename))

    return render_template("index.html")


@app.route("/result")
def result():
    """Route to display the result with play and download options"""
    filename = request.args.get("filename")
    if not filename or not os.path.exists(filename):
        flash("❌ No audio file found.", "error")
        return redirect(url_for("index"))

    return render_template("result.html", filename=filename)


@app.route("/download/<filename>")
def download(filename):
    """Route to download the generated speech file"""
    return send_file(filename, as_attachment=True, mimetype="audio/mpeg")


# ========= Main Execution =========

if __name__ == "__main__":
    app.run(debug=True)
