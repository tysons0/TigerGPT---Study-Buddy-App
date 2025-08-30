# init_db.py
import sqlite3, pathlib

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS student (
  username TEXT PRIMARY KEY,
  full_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollment (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL,
  course_code TEXT NOT NULL,
  UNIQUE(username, course_code),
  FOREIGN KEY (username) REFERENCES student(username) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS availability (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL,
  day_of_week TEXT NOT NULL CHECK(day_of_week IN ('Mon','Tue','Wed','Thu','Fri','Sat','Sun')),
  start_time TEXT NOT NULL,  -- "HH:MM"
  end_time   TEXT NOT NULL,  -- "HH:MM"
  UNIQUE(username, day_of_week, start_time, end_time),
  FOREIGN KEY (username) REFERENCES student(username) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  course_code TEXT NOT NULL,
  initiator_username TEXT NOT NULL,
  invitee_username   TEXT NOT NULL,
  day_of_week TEXT NOT NULL CHECK(day_of_week IN ('Mon','Tue','Wed','Thu','Fri','Sat','Sun')),
  start_time TEXT NOT NULL,
  end_time   TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('Proposed','Confirmed')),
  FOREIGN KEY (initiator_username) REFERENCES student(username),
  FOREIGN KEY (invitee_username)   REFERENCES student(username)
);

CREATE INDEX IF NOT EXISTS idx_enrollment_course ON enrollment(course_code);
CREATE INDEX IF NOT EXISTS idx_avail_user ON availability(username);
CREATE INDEX IF NOT EXISTS idx_session_invitee ON session(invitee_username, status);
"""

def init_db(db_path="studybuddy.db"):
    new = not pathlib.Path(db_path).exists()
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        con.executescript(SCHEMA_SQL)
        con.commit()
    finally:
        con.close()
    print(f"OK: {db_path} {'created' if new else 'updated'}")

def smoke_test(db_path="studybuddy.db"):
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON;")
    # create a sample user and course
    con.execute("INSERT OR IGNORE INTO student(username, full_name) VALUES(?,?)",
                ("tiger1", "Test Tiger"))
    con.execute("INSERT OR IGNORE INTO enrollment(username, course_code) VALUES(?,?)",
                ("tiger1", "MATH 4000"))
    con.commit()
    rows = con.execute("""
        SELECT s.username, s.full_name, e.course_code
        FROM student s JOIN enrollment e ON s.username = e.username
    """).fetchall()
    con.close()
    print("Smoke test rows:", rows)

if __name__ == "__main__":
    init_db()
    smoke_test()
