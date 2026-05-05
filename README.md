# Adaptive Reading Platform

## Overview

This project is a web-based reading platform built with Flask, HTML, CSS, JavaScript, and SQLite.  
It was designed to support reading through gamified features such as books, quests, streaks, health, levels, avatars, and backgrounds.

The system also tracks reading behaviour during a session. It uses this data to estimate user engagement and to decide when supportive messages or a short quiz should appear.

## Main Features

- Read short digital stories in a browser
- Unlock books in stages
- Gain XP and level up by completing books
- Build a reading streak
- Track buddy health based on reading behaviour
- Unlock avatars and backgrounds
- Detect engagement during reading
- Trigger quizzes when a finish looks suspiciously fast
- Store user progress in SQLite

## Technologies Used

- Python
- Flask
- HTML
- CSS
- JavaScript
- SQLite

## Project Structure

- `app.py` starts the Flask application
- `config.py` stores the main settings used by the app
- `db.py` handles database setup and connections
- `schema.sql` defines the database tables
- `routes/` contains page routes and API routes
- `logic/` contains the main application logic
- `models/` contains the engagement model code
- `templates/` contains the HTML pages
- `static/` contains JavaScript, CSS, images, and story data

## How to Run the Project

### 1. Install Python
Make sure Python 3 is installed on your computer.

### 2. Install Flask
Open a terminal in the project folder and run:

```bash
pip install flask
```

### 3. Start the app
Run:

```bash
python app.py
```

### 4. Open the app
Open your browser and go to:

```text
http://127.0.0.1:5000
```

## How to Use the App

### Home Page
The home page shows the main progress information and links to the main sections.

### Books Page
Open the books page to view available stages and stories.  
Books unlock in order, so some stories remain locked until earlier ones are completed.

### Reading Page
Choose an unlocked story and begin reading.  
While the user reads, the app tracks behaviour such as:

- idle time
- scroll speed
- scroll depth
- focus loss
- interaction rate

When the story is finished, press **Finish Book**.

Book 1 is used for calibration

### Quizzes
A quiz may appear when:

- the finish looks suspiciously fast
- the system randomly triggers an end check
- calibration is needed for Book 1

### Quests Page
The quests page shows progress goals such as:

- finishing the first book
- clearing Stage 1
- reaching a streak target
- keeping high buddy health
- reaching Level 2

### Stats Page
The stats page shows:

- level
- XP
- streak
- health
- recent engagement results
- recent quiz results

### Avatar Page
The avatar page lets the user select unlocked avatars and backgrounds.

## Database

The app uses SQLite.  
When the app starts, it creates the database tables from `schema.sql` if they do not already exist.

The main stored data includes:

- user state
- engagement events
- reading sessions
- quiz results
- calibration data

## Configuration

The main settings are stored in `config.py`.

Examples include:

- health values
- XP values
- engagement thresholds
- quiz rules
- tracker settings
- debug settings


## Notes

- This project is intended as a prototype for a final year project submission.
- Some values in `config.py` are designed to be adjusted during testing.
- Story content is stored in `static/stories.json`.
- The engagement values and thresholds were tuned to be less strict because the intended users were children. This helped avoid penalising normal child reading behaviour, such as slower reading, short pauses, or uneven scrolling, too quickly.
- The engagement panel is a development and testing feature. It was used to show that the engagement detection was working during implementation, but it would not be displayed in the final user version of the app.

