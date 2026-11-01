# SmartEdu: smart exam and learning portal

Proctored online exams, assignments, attendance and study material for colleges. Teachers build exams and assignments,
students sit proctored exams and submit work, the AI engine marks answers and finds weak topics, and guardians get
exam results and attendance by email. Admins manage people and departments.

Built with Django 5.2, SQLite, Bootstrap 5 (bundled, works offline), scikit-learn and OpenCV (optional).

## What changed in this version: departments and semesters

"Class" is gone. Every student belongs to one **department** and one **semester**, and everything is sent to a department **and** semester.

| Area | What it does now |
|------|------------------|
| Departments | A fixed list of 17: Agricultural Engineering, Applied Electronics and Instrumentation Engineering, Applied Science & Humanities, Bio Technology, Chemical Engineering, Civil Engineering, Computer Science and Engineering (CSE), Computer Science & Engineering (AI & ML), CSE (Cyber Security), CSE (Data Science), Electrical Engineering, Electronics & Communication Engineering (ECE), Food Technology, Information Technology (IT), Mechanical Engineering, Master of Business Administration (MBA), Master of Computer Applications (MCA). |
| Semesters | **8 semesters** for every department except **MBA and MCA, which have 4**. The semester drop-down changes by itself when you pick the department. The server checks it too. |
| Admin: students | Register a student with **two drop-downs** (department, then semester) plus the guardian's name and email. **Edit** any student to change the semester (or department) and **delete** a student. Filter the list by department and semester. |
| Admin: teachers | Register a teacher **in a specific department**, **edit** it later, and **delete** a teacher. |
| Teacher | Sends every **exam, assignment and study material** to a department and semester chosen from two drop-downs. Attendance and the student list are also by department and semester. |
| Student | Sees only the exams, assignments, study material, announcements and attendance of **their own department and semester**. When the admin moves a student up a semester, the new semester's work appears and the old one disappears. |

Earlier additions are all still here: assignments with star ratings, missed-exam reasons with proof and a one-student re-attempt chance, guardian emails for results and attendance, and the performance graph.

## Run it in VS Code (about 5 minutes)

**Before you start:** install [Python 3.10 to 3.13](https://www.python.org/downloads/) (tick "Add python.exe to PATH" on Windows)
and [VS Code](https://code.visualstudio.com/) with the **Python** extension.

1. Django uses SQLite by default, so no separate database server is needed.
2. **Unzip** `SmartEdu.zip`. You get a folder called `SmartEdu` with `manage.py` inside it.
3. In VS Code choose **File > Open Folder** and pick that `SmartEdu` folder (the one that contains `manage.py`).
4. No database configuration is required. Django creates `db.sqlite3` in the project folder when you run migrations.
   Existing data stored in PostgreSQL is not copied automatically; export/import it separately if you need to keep it.
5. Open a terminal with **Ctrl + `** (Terminal > New Terminal) and run the setup:

   **Windows (PowerShell or CMD)**
   ```
   setup.bat
   ```
   **macOS / Linux**
   ```
   bash setup.sh
   ```
   This creates a virtual environment (`venv`), installs the packages, initializes the SQLite database and loads demo data.
   If you prefer to do it by hand, see "Manual setup" below.
6. When VS Code asks *"We noticed a new environment"*, click **Yes**. Or press `Ctrl+Shift+P`, choose
   **Python: Select Interpreter**, and pick the one inside `venv`.
7. **Start the app**: press **F5** (choose "SmartEdu: run server") or run `run.bat` / `bash run.sh`.
8. Open **http://127.0.0.1:8000/** in Chrome or Edge. Stop the server with `Ctrl+C`.

**Already have the previous version?** Copy over the new files, then run `python manage.py migrate` once (it renames the class field to department and adds semester;
old students get semester 1). Then run `python manage.py upgrade_departments`: it renames common old names (for example *Computer Science Engineering*) to the new official ones
and lists anything it could not match. Fix those, and every student's real semester, in *Admin > Students > pencil icon*. For fresh demo data run `python manage.py seed_demo --reset`.

### Demo logins

| Role    | Username   | Password     | Department and semester |
|---------|------------|--------------|-------------------------|
| Admin   | `admin`    | `admin123`   | |
| Teacher | `teacher1` | `teacher123` | Mathematics, registered in CSE |
| Teacher | `teacher2` | `teacher123` | Physics, registered in Mechanical Engineering |
| Student | `student1` to `student8` | `student123` | CSE, semester 3 |
| Student | `student9`, `student10` | `student123` | Mechanical Engineering, semester 2 |
| Student | `student11` | `student123` | MCA, semester 2 (MCA has 4 semesters) |
| Student | `student12` | `student123` | CSE, **semester 4** (sees none of the semester 3 work) |

On the login page, the "Demo accounts" buttons fill these in for you (only shown while `DEBUG` is on).

### Try the new features

1. **Assignments.** Log in as **teacher1**, open *Assignments > New assignment*, type a topic, tick *Computer Science Engineering* and send.
   Log in as **student1**, open *Assignments*, press *Submit* and upload a PDF, Word file or a photo.
   Back as **teacher1**, open the assignment, press *Review and rate*, choose 1 to 5 stars and save. **student1** now sees the rating.
2. **Missed exam.** Log in as **student8**: the dashboard shows a red banner because *Matrices Mid-term Quiz* closed without an attempt.
   Open *Missed exams*, press *Give reason and proof*, write why and upload a PDF or photo, and send.
   Then log in as **teacher1**, open *Re-attempt requests*, read the reason, open the proof, and press *Approve* (choose a new deadline) or *Reject* (write a comment).
   Only that student can then take the exam. Three other requests are already in the demo data to compare: **student1** is waiting for a decision,
   **student4** has an approved chance (can take the exam now) and **student7** was rejected.
   To make your own closed exam, create one as a teacher with a closing time a few minutes away, let it close, then log in as a student who did not attempt it.
3. **Guardian emails.** Log in as **teacher1**, open *Attendance*, mark a day and save. Then open *Admin > Guardian emails* to read every email.
   Submitting any exam as a student also creates a result email. Without a mail server the emails appear in the VS Code terminal and in that log.
4. **Performance graph.** Log in as **student2** and open *Performance*, or as **teacher1** open *Students > View* for any student.
5. **Department and semester.** As **admin** open *Students > Register student*. Pick a department, then a semester. Pick *MCA* or *MBA* and the list drops to 4 semesters.
   The guardian name and email are required.
6. **Semester follows the student.** As **teacher1** send an assignment, an exam or study material to *CSE, Semester 4*. Only **student12** sees it, not **student1**.
   As **admin** open *Students*, press the pencil on **student12**, change the semester to 3, and save: student12 now sees the semester 3 work.
7. **Edit and delete.** As **admin** open *Teachers*, press the pencil to change a teacher's department, or the bin to delete. Deleting asks for confirmation and shows
   exactly what will also be removed (exams, submissions, uploaded files). *Switch off* is the gentler choice that keeps all records.

## What is in the box

| Area | Features |
|------|----------|
| Student | Dashboard, exams with live status, proctored exam page (autosave, server timer), results with AI feedback, **assignments with ratings**, **missed exams with reason and proof**, **performance graph of exams and assignments**, weak topics with revision links, study material, attendance, notifications |
| Teacher | Create and publish exams **for a department and semester, with a closing time**, MCQ and written questions, results, manual mark override, proctoring log, allow retake, **assignments (topic only) for a department and semester, with review and star rating**, **re-attempt requests (approve for one student or reject)**, study material for a department and semester, bulk attendance, per-student **performance graph**, analytics |
| Admin | Dashboard, register students (**department and semester drop-downs, guardian name and email required**) and teachers (**in a department**), **edit** students and teachers (semester, department), **delete** students and teachers, switch accounts on or off, reset passwords, departments overview, all exams, announcements to a department and semester, **guardian email log and test email** |
| AI engine | MCQ key check, written answers by TF-IDF similarity plus keyword bonus, weak-topic detection, below-70% flag, understanding level, revision links |
| Proctoring | Camera and mic, fullscreen, tab switch, copy and paste blocked, webcam face check, three violations cancel the exam |

**About proctoring:** these are browser-based checks. They discourage and record misconduct, but a determined
student can get around any browser check. Teachers review the log and can allow a retake after a false alarm.

## Departments and semesters: the rules

- The department list is fixed (17 departments, listed above). There is no free-text department any more.
- A semester is a whole number: 1 to 8, or 1 to 4 for MBA and MCA. Choosing a department narrows the semester list; the server rejects impossible pairs such as *MCA, semester 6*.
- Content is matched on **both** department and semester. A student in *CSE, semester 4* does not see *CSE, semester 3* exams, assignments, study material or announcements,
  and cannot open them even by typing the web address.
- Each teacher is registered in one department, and that department is the default in the exam, assignment and study material forms. By default a teacher can still send to **any**
  department (one teacher can teach many, for example Applied Science & Humanities). To limit teachers to their own department, set `TEACHER_LIMIT_TO_OWN_DEPARTMENT = True` in `config/settings.py`.
- Moving a student to another semester (Admin > Students > pencil) notifies the student. Past results and attendance stay with the student.
- Deleting a student or teacher is permanent and removes their records and uploaded files; the admin must confirm on a page that lists what will be removed.

## Guardian emails: how to make them really send

Each student has a guardian name and email. SmartEdu emails the guardian:

- the **exam result** (score, percentage, level, topics to revise) as soon as the exam is submitted, and a notice if the exam is **cancelled**;
- the **attendance** (present, late or absent) when a teacher saves attendance. The same status for the same day is never emailed twice.

Every email is saved in *Admin > Guardian emails*, including failures and the reason.

**Test mode (default):** with no mail settings the emails are printed in the terminal and logged, but not delivered.
**To send real emails:** copy `.env.example` to `.env` and fill in your SMTP details (for Gmail use an *App password*), restart the server, then
use *Admin > Guardian emails > Send test* to check. A student without a guardian email is skipped (the admin form makes it mandatory for new students).

## Missed exams and re-attempts: the rules

- Every exam has an **opens** and a **closes** time. A student can start it only between those times. The exam timer still runs from the moment they start.
- A student who never started it before the closing time can send **one request** per exam with a reason (at least 15 characters) and **proof** (PDF, JPG, PNG or Word, up to 10 MB). Proof is required.
- The teacher who created the exam sees the request. **Approve** needs a new deadline and gives that student only another chance. **Reject** needs a comment. Others stay locked out.
- A student who started but did not finish is not "missed": the normal timer and the teacher's *Allow retake* button apply.
- Proof files are private: only the student, the teacher of that exam and admins can open them.

## Assignments: the rules

- The teacher sends a **topic** (plus an optional note and due date) to one or more departments. Students are notified.
- Allowed uploads: pdf, doc, docx, ppt, pptx, xls, xlsx, txt, jpg, jpeg, png, up to 15 MB. A student can replace the file until it is reviewed. Late work is accepted and marked **late**.
- The teacher gives a **1 to 5 star rating** and a review. The student is notified and sees both. After review the submission is locked.
- Files are private: the student, the teacher who set the assignment and admins only.

## Performance graph

One line chart per student: **exam results (percent)** and **assignment ratings (stars x 20, so 5 stars is 100%)** on a shared timeline, with a dashed 70% line.
Tiles show the exam average, the average rating out of 5, and an **overall** figure (the average of the two). Students see their own graph; teachers see it for each student.

## Manual setup (if `setup.bat` doesn't work for you)

```
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
# SQLite is used automatically; no database server or credentials are needed.
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

## Everyday commands

| Task | Command |
|------|---------|
| Start the server | `python manage.py runserver` (or F5) |
| Reset demo data | `python manage.py seed_demo --reset` |
| Convert an old database's department names | `python manage.py upgrade_departments` |
| Run the test suite (47 tests, about 3 minutes) | `python manage.py test` |
| Make your own admin | `python manage.py createsuperuser` (then set its role to ADMIN in /django-admin/) |
| Open the raw data editor | http://127.0.0.1:8000/django-admin/ |

## Project layout

```
SmartEdu/
  manage.py, requirements.txt, .env.example, setup.bat/.sh, run.bat/.sh
  config/            settings.py, urls.py
  apps/
    accounts/        users, roles, login, departments.py (the 17 departments and semester counts), seed_demo and upgrade_departments commands, tests
    admin_portal/    admin pages (people, departments, emails, announcements)
    teacher/         teacher pages        student/    student pages
    exams/           exams, questions, submissions, autosave, closing-time helpers
    assignments/     assignments, uploads, ratings
    reattempt/       missed-exam requests, proof, approve or reject
    materials/       study material
    notifications/   notifications and the guardian email service (emails.py, EmailLog)
    performance/     reports, weak topics, recommendations, series.py (the graph data)
    attendance/ proctoring/
  ai_engine/         evaluation/ (marking), performance/ (weak topics), proctoring/ (face check)
  templates/  static/   HTML and CSS/JS (Bootstrap, icons, Chart.js bundled: works offline)
```

Departments are stored in a `department` field and semesters in a `semester` field on students, exams, assignments, study material and attendance.

## Settings you may want to change (`config/settings.py`)

| Setting | Meaning |
|---------|---------|
| `AI_THRESHOLD_FAIL = 70` | Scores below this are highlighted and flagged |
| `AI_PROCTORING_MAX_VIOLATIONS = 3` | Violations that cancel an exam |
| `PROCTORING_FRAME_INTERVAL = 10` | Seconds between webcam snapshots |
| `PROCTORING_ALLOW_NO_CAMERA` | Demo mode without a webcam (on only while `DEBUG` is on) |
| `MATERIAL_MAX_MB`, `ASSIGNMENT_MAX_MB`, `PROOF_MAX_MB` | Upload size limits (25, 15, 10) |
| `SMARTEDU_EMAIL_*`, `SMARTEDU_FROM_EMAIL` | Mail server settings (in `.env`) |

For a real deployment: set `SMARTEDU_DEBUG=0`, a long random `SMARTEDU_SECRET_KEY` and `SMARTEDU_ALLOWED_HOSTS`, serve over **https**
(browsers allow the camera only on https or localhost), and run behind a proper web server.

## Troubleshooting

- **`python` is not recognised (Windows):** reinstall Python and tick "Add python.exe to PATH", or use `py` instead of `python`.
- **PowerShell says scripts are disabled when activating `venv`:** run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use CMD, or use `setup.bat` / `run.bat`.
- **`pip install` fails on opencv:** it is optional. Delete the `opencv-python-headless` line from `requirements.txt` and install again.
- **`No module named django`:** the virtual environment isn't selected. Look for `(venv)` in the terminal and pick the interpreter inside `venv`.
- **Camera does not start:** use Chrome or Edge on `http://127.0.0.1:8000` or `localhost`, and allow the permission in the address bar.
- **No guardian emails arrive:** that is normal in test mode. See "Guardian emails" above. Check *Admin > Guardian emails* for the reason if sending fails.
- **Page looks unstyled after an update:** hard refresh with Ctrl + F5.
- **"no such column" or "no such table":** run `python manage.py migrate`.
- **Old students show a blank department:** their old class name is not in the official list. Run `python manage.py upgrade_departments`, then fix the rest in *Admin > Students*.
- **"Port already in use":** run `python manage.py runserver 8001`.
- **Start with a fresh SQLite database:** run `python manage.py migrate` and `python manage.py seed_demo`.
