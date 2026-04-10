# GEMINI.md - Project Context

## Project Overview
This project is a text-based repository for the **Mahaprajnaparamita Shastra** (大智度論, Dà zhìdù lùn), a massive Buddhist commentary attributed to Nagarjuna and translated into Chinese by Kumarajiva. The project appears to be focused on the curation, splitting, and verification of this classical text.

## Directory Overview
The project is organized into functional directories for text processing:

- `origin/`: Contains the original, full-length source text.
- `split/`: Intended for split versions of the text (e.g., by scroll, chapter, or volume). Currently empty.
- `check/`: Intended for verification files, annotations, or quality checks. Currently empty.

## Key Files
- `origin/origin.txt`: The primary source file containing the complete Chinese text of the *Mahaprajnaparamita Shastra*. It includes the preface by Sengrui (长安释僧睿述) and the main commentary. The file is quite large (over 60,000 lines).
- `README.md`: Basic project entry point (currently minimal).
- `LICENSE`: Project licensing information.

## Usage & Workflow
The directory structure suggests a text-processing workflow:
1.  **Source:** The text is sourced in `origin/`.
2.  **Processing:** The text is likely intended to be split into smaller, more manageable units in `split/` (e.g., 100 scrolls/卷).
3.  **Verification:** The `check/` directory is likely used to store notes or automated checks to ensure text integrity during the splitting process.

Future interactions should respect the classical nature of the text and ensure that any processing preserves the original structure (e.g., keeping the Gatha verses and Q&A formats intact).
