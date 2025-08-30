# studybuddy.py
# Minimal menu-based Study Buddy app (SQLite)
# Implements SRS features only: profiles/courses, availability, search, suggestions,
# propose/confirm sessions, list sessions. No extras.

import os
import sqlite3
import re
from typing import List, Tuple, Optional

DB_PATH = "studybuddy.db"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

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


# --------------------------- Utilities (time & input) ---------------------------

def normalize_day(day_raw: str) -> Optional[str]:
    """Return canonical 'Mon'..'Sun' for inputs like 'Tue', 'Tuesday', 'thurs', etc."""
    s = (day_raw or "").strip().lower()
    aliases = {
        "mon": "Mon", "monday": "Mon",
        "tue": "Tue", "tues": "Tue", "tuesday": "Tue",
        "wed": "Wed", "weds": "Wed", "wednesday": "Wed",
        "thu": "Thu", "thur": "Thu", "thurs": "Thu", "thursday": "Thu",
        "fri": "Fri", "friday": "Fri",
        "sat": "Sat", "saturday": "Sat",
        "sun": "Sun", "sunday": "Sun",
    }
    return aliases.get(s)


def parse_time_hhmm(t: str) -> Optional[Tuple[int, int]]:
    """
    Accepts either:
      - 24h: 'HH:MM'  (e.g., '17:30')
      - 12h: 'H:MM AM/PM' (e.g., '5:30 PM', '11:05 am', '12:00AM', '12:00 pm')
    Returns (hour, minute) in 24-hour form, or None if invalid.
    """
    if not t:
        return None
    s = t.strip().lower()

    # Try 12-hour with am/pm first
    m = re.fullmatch(r"(\\d{1,2})\\s*:\\s*(\\d{2})\\s*([ap])\\.?\\s*m\\.?", s)
    if m:
        h = int(m.group(1))
        mnt = int(m.group(2))
        ap = m.group(3)  # 'a' or 'p'
        if not (1 <= h <= 12 and 0 <= mnt <= 59):
            return None
        # Convert to 24h
        if ap == "p" and h != 12:
            h += 12
        if ap == "a" and h == 12:
            h = 0
        return (h, mnt)

    # Fallback: strict 24-hour HH:MM
    m = re.fullmatch(r"(\\d{1,2})\\s*:\\s*(\\d{2})", s)
    if not m:
        return None
    h = int(m.group(1))
    mnt = int(m.group(2))
    if 0 <= h <= 23 and 0 <= mnt <= 59:
        return (h, mnt)
    return None


def to_minutes(hhmm: str) -> Optional[int]:
    p = parse_time_hhmm(hhmm)
    if p is None:
        return None
    h, m = p
    return h * 60 + m

def overlap_minutes(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    """Return overlap duration in minutes between two [start,end) intervals."""
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    return max(0, end - start)

def interval_includes(inner_start: int, inner_end: int, outer_start: int, outer_end: int) -> bool:
    """True if [inner_start, inner_end) lies fully inside [outer_start, outer_end)."""
    return outer_start <= inner_start and inner_end <= outer_end

def prompt(msg: str) -> str:
    return input(msg).strip()


# --------------------------- Data Access Layer ---------------------------

def get_conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def init_db():
    first = not os.path.exists(DB_PATH)
    with get_conn() as con:
        con.executescript(SCHEMA_SQL)
    if first:
        print(f"[init] Created {DB_PATH}")


# --------------------------- Core System (SRS FR-1..FR-5) ---------------------------

class StudyBuddySystem:
    """Thin service layer that the menu calls. Keeps logic readable and testable."""

    # ---------- FR-1 Profile & Courses ----------
    def create_profile(self, username: str, full_name: str) -> bool:
        if not username or not full_name:
            print("Error: username and full name required.")
            return False
        try:
            with get_conn() as con:
                con.execute("INSERT INTO student(username, full_name) VALUES(?, ?)", (username, full_name))
            print("Profile created.")
            return True
        except sqlite3.IntegrityError:
            print("Error: username already exists. (AC-1)")
            return False

    def get_profile(self, username: str) -> Optional[sqlite3.Row]:
        with get_conn() as con:
            row = con.execute("SELECT * FROM student WHERE username = ?", (username,)).fetchone()
        return row

    def add_course(self, username: str, course_code: str) -> bool:
        course_code = course_code.strip()
        if not course_code:
            print("Error: course code required.")
            return False
        try:
            with get_conn() as con:
                con.execute("INSERT INTO enrollment(username, course_code) VALUES(?, ?)", (username, course_code))
            print("Course added.")
            return True
        except sqlite3.IntegrityError:
            print("Error: duplicate course not allowed. (FR-1.3)")
            return False

    def remove_course(self, username: str, course_code: str) -> None:
        with get_conn() as con:
            con.execute("DELETE FROM enrollment WHERE username = ? AND course_code = ?", (username, course_code))
        print("If present, course removed.")

    def list_courses(self, username: str) -> List[str]:
        with get_conn() as con:
            rows = con.execute("SELECT course_code FROM enrollment WHERE username = ? ORDER BY course_code", (username,)).fetchall()
        return [r["course_code"] for r in rows]

    # ---------- FR-2 Availability ----------
    def add_availability(self, username: str, day: str, start: str, end: str) -> bool:
        day_norm = normalize_day(day)
        if day_norm is None:
            print("Error: day must be one of Mon..Sun.")
            return False
        s = to_minutes(start)
        e = to_minutes(end)
        if s is None or e is None:
            print('Error: time must be "HH:MM" (24-hour) or "H:MM AM/PM".')
            return False
        if s >= e:
            print("Error: start must be earlier than end. (AC-2)")
            return False
        try:
            with get_conn() as con:
                con.execute(
                    "INSERT INTO availability(username, day_of_week, start_time, end_time) VALUES(?,?,?,?)",
                    (username, day_norm, start, end),
                )
            print("Availability added.")
            return True
        except sqlite3.IntegrityError:
            print("Error: exact duplicate availability not allowed. (FR-2.4)")
            return False

    def remove_availability(self, availability_id: int) -> None:
        with get_conn() as con:
            con.execute("DELETE FROM availability WHERE id = ?", (availability_id,))
        print("If present, availability removed.")

    def list_availability(self, username: str) -> List[sqlite3.Row]:
        with get_conn() as con:
            rows = con.execute(
                "SELECT id, day_of_week, start_time, end_time FROM availability WHERE username = ? "
                "ORDER BY CASE day_of_week "
                "WHEN 'Mon' THEN 1 WHEN 'Tue' THEN 2 WHEN 'Wed' THEN 3 WHEN 'Thu' THEN 4 "
                "WHEN 'Fri' THEN 5 WHEN 'Sat' THEN 6 WHEN 'Sun' THEN 7 END, start_time",
                (username,),
            ).fetchall()
        return rows

    # ---------- FR-3 Search & Suggestions ----------
    def find_classmates_by_course(self, username: str, course_code: str) -> List[sqlite3.Row]:
        with get_conn() as con:
            rows = con.execute(
                """
                SELECT s.username, s.full_name
                FROM enrollment e
                JOIN student s ON s.username = e.username
                WHERE e.course_code = ? AND s.username <> ?
                ORDER BY s.username
                """,
                (course_code, username),
            ).fetchall()
        return rows

    def suggest_matches(self, username: str) -> List[dict]:
        """Return list of {classmate_username, shared_courses, overlap_day, overlap_start, overlap_end}."""
        my_courses = set(self.list_courses(username))
        if not my_courses:
            return []

        # Find potential classmates across all my courses
        with get_conn() as con:
            rows = con.execute(
                """
                SELECT DISTINCT s.username, s.full_name, e.course_code
                FROM enrollment e
                JOIN student s ON s.username = e.username
                WHERE e.course_code IN ({})
                  AND s.username <> ?
                """.format(",".join("?" * len(my_courses))),
                (*sorted(my_courses), username),
            ).fetchall()

        # Group classmates → shared courses
        classmates = {}
        for r in rows:
            classmates.setdefault(r["username"], {"full_name": r["full_name"], "courses": set()})
            classmates[r["username"]]["courses"].add(r["course_code"])

        # Load availability once
        my_avail = self._availability_by_day(username)

        suggestions = []
        for cname, info in classmates.items():
            c_avail = self._availability_by_day(cname)
            # Check any overlap ≥ 30 minutes on any day
            example = self._first_overlap_example(my_avail, c_avail, min_minutes=30)
            if example is not None:
                day, start_min, end_min = example
                suggestions.append({
                    "classmate_username": cname,
                    "full_name": info["full_name"],
                    "shared_courses": sorted(info["courses"]),
                    "overlap_day": day,
                    "overlap_start": f"{start_min//60:02d}:{start_min%60:02d}",
                    "overlap_end": f"{end_min//60:02d}:{end_min%60:02d}",
                })
        return suggestions

    def _availability_by_day(self, username: str):
        """Map day -> list of (start_min, end_min)."""
        daymap = {d: [] for d in DAYS}
        for row in self.list_availability(username):
            s = to_minutes(row["start_time"])
            e = to_minutes(row["end_time"])
            if s is not None and e is not None:
                daymap[row["day_of_week"]].append((s, e))
        return daymap

    def _first_overlap_example(self, mine, theirs, min_minutes=30):
        for d in DAYS:
            for (ms, me) in mine[d]:
                for (ts, te) in theirs[d]:
                    ov = overlap_minutes(ms, me, ts, te)
                    if ov >= min_minutes:
                        start = max(ms, ts)
                        end = start + ov
                        return (d, start, end)
        return None

    # ---------- FR-4 Sessions ----------
    def propose_session(self, initiator: str, invitee: str, course_code: str,
                        day: str, start: str, end: str) -> Optional[int]:
        # Validate people and course sharing
        if not self.get_profile(initiator) or not self.get_profile(invitee):
            print("Error: both users must exist.")
            return None
        if course_code not in set(self.list_courses(initiator)):
            print("Error: initiator is not enrolled in that course.")
            return None
        # Invitee must also be enrolled
        invitee_courses = set(self.list_courses(invitee))
        if course_code not in invitee_courses:
            print("Error: invitee is not enrolled in that course.")
            return None

        day_norm = normalize_day(day)
        if day_norm is None:
            print("Error: day must be one of Mon..Sun.")
            return None
        smin, emin = to_minutes(start), to_minutes(end)
        if smin is None or emin is None or smin >= emin:
            print("Error: invalid start/end times. (AC-5)")
            return None

        # Check requested window lies within any overlap ≥30m of both users
        my_avail = self._availability_by_day(initiator)
        their_avail = self._availability_by_day(invitee)
        requested_len = emin - smin
        if requested_len < 30:
            print("Error: proposed session must be at least 30 minutes.")
            return None

        ok = False
        for (ms, me) in my_avail[day_norm]:
            for (ts, te) in their_avail[day_norm]:
                ov = overlap_minutes(ms, me, ts, te)
                if ov >= 30 and interval_includes(smin, emin, max(ms, ts), min(me, te)):
                    ok = True
                    break
            if ok:
                break
        if not ok:
            print("Error: proposal outside overlapping availability. (FR-4.2 / AC-5)")
            return None

        with get_conn() as con:
            cur = con.execute(
                """
                INSERT INTO session(course_code, initiator_username, invitee_username,
                                    day_of_week, start_time, end_time, status)
                VALUES(?,?,?,?,?,?, 'Proposed')
                """,
                (course_code, initiator, invitee, day_norm, start, end),
            )
            session_id = cur.lastrowid
        print(f"Proposed session #{session_id} recorded.")
        return session_id

    def list_sessions_for(self, username: str) -> List[sqlite3.Row]:
        with get_conn() as con:
            rows = con.execute(
                """
                SELECT id, course_code, initiator_username, invitee_username,
                       day_of_week, start_time, end_time, status
                FROM session
                WHERE initiator_username = ? OR invitee_username = ?
                ORDER BY id DESC
                """,
                (username, username),
            ).fetchall()
        return rows

    def list_proposed_for_invitee(self, invitee: str) -> List[sqlite3.Row]:
        with get_conn() as con:
            rows = con.execute(
                """
                SELECT id, course_code, initiator_username, day_of_week, start_time, end_time
                FROM session
                WHERE invitee_username = ? AND status = 'Proposed'
                ORDER BY id DESC
                """,
                (invitee,),
            ).fetchall()
        return rows

    def confirm_session(self, session_id: int, invitee: str) -> bool:
        with get_conn() as con:
            sess = con.execute(
                "SELECT * FROM session WHERE id = ?", (session_id,)
            ).fetchone()
            if not sess:
                print("Error: session not found.")
                return False
            if sess["invitee_username"] != invitee:
                print("Error: only the invitee can confirm this session.")
                return False
            if sess["status"] == "Confirmed":
                print("Info: session already confirmed.")
                return True

            # Check conflicts with invitee's confirmed sessions (same day overlap)
            rows = con.execute(
                """
                SELECT day_of_week, start_time, end_time
                FROM session
                WHERE status = 'Confirmed'
                  AND (initiator_username = ? OR invitee_username = ?)
                """,
                (invitee, invitee),
            ).fetchall()

            smin = to_minutes(sess["start_time"])
            emin = to_minutes(sess["end_time"])
            for r in rows:
                if r["day_of_week"] != sess["day_of_week"]:
                    continue
                rs, re = to_minutes(r["start_time"]), to_minutes(r["end_time"])
                if overlap_minutes(smin, emin, rs, re) > 0:
                    print("Error: overlaps an existing confirmed session. (FR-4.5 / AC-6)")
                    return False

            con.execute("UPDATE session SET status = 'Confirmed' WHERE id = ?", (session_id,))
            print("Session confirmed.")
            return True


# --------------------------- Menu UI (SRS §7) ---------------------------

class MenuUI:
    def __init__(self, system: StudyBuddySystem):
        self.sys = system
        self.active_user: Optional[str] = None

    def run(self):
        self._ensure_active_user_on_start()
        while True:
            print("\n=== Main Menu ===")
            print("1) Switch / Log in as user")
            print("2) Create profile")
            print("3) View my profile & courses")
            print("4) Manage my courses")
            print("5) Manage my availability")
            print("6) Find classmates by course")
            print("7) See suggested matches")
            print("8) Propose a study session")
            print("9) Confirm my proposed sessions")
            print("10) List my sessions")
            print("0) Exit")
            choice = prompt("Choose: ")
            if choice == "1":
                self.switch_user()
            elif choice == "2":
                self.create_profile_flow()
            elif choice == "3":
                self.view_profile_flow()
            elif choice == "4":
                self.manage_courses_flow()
            elif choice == "5":
                self.manage_availability_flow()
            elif choice == "6":
                self.find_classmates_flow()
            elif choice == "7":
                self.suggest_matches_flow()
            elif choice == "8":
                self.propose_session_flow()
            elif choice == "9":
                self.confirm_sessions_flow()
            elif choice == "10":
                self.list_sessions_flow()
            elif choice == "0":
                print("Goodbye.")
                break
            else:
                print("Invalid choice.")

    def _ensure_active_user_on_start(self):
        print("Welcome to Study Buddy (Menu).")
        while not self.active_user:
            u = prompt("Enter username (or leave blank to create a new one): ")
            if u:
                if self.sys.get_profile(u):
                    self.active_user = u
                    print(f"Active user set to {u}.")
                    return
                else:
                    print("No such user.")
            ans = prompt("Create new profile? (y/n): ").lower()
            if ans.startswith("y"):
                self.create_profile_flow()
                if self.active_user:
                    return
            else:
                print("You need an active user to continue.")

    # ----- Flows -----

    def switch_user(self):
        u = prompt("Username to switch to: ")
        if self.sys.get_profile(u):
            self.active_user = u
            print(f"Active user is now {u}.")
        else:
            print("No such user.")

    def create_profile_flow(self):
        u = prompt("New username: ")
        n = prompt("Full name: ")
        if self.sys.create_profile(u, n):
            self.active_user = u

    def view_profile_flow(self):
        self._need_active()
        prof = self.sys.get_profile(self.active_user)
        if not prof:
            print("No such user.")
            return
        print(f"\nUser: {prof['username']}  Name: {prof['full_name']}")
        courses = self.sys.list_courses(self.active_user)
        print("Courses:", ", ".join(courses) if courses else "(none)")

    def manage_courses_flow(self):
        self._need_active()
        while True:
            print("\n-- Manage Courses --")
            print("1) Add course")
            print("2) Remove course")
            print("3) View my courses")
            print("0) Back")
            c = prompt("Choose: ")
            if c == "1":
                course = prompt("Course code (e.g., MATH 4000): ")
                self.sys.add_course(self.active_user, course)
            elif c == "2":
                course = prompt("Course code to remove: ")
                self.sys.remove_course(self.active_user, course)
            elif c == "3":
                courses = self.sys.list_courses(self.active_user)
                print("My courses:", ", ".join(courses) if courses else "(none)")
            elif c == "0":
                break
            else:
                print("Invalid choice.")

    def manage_availability_flow(self):
        self._need_active()
        while True:
            print("\n-- Manage Availability --")
            print("1) List")
            print("2) Add slot")
            print("3) Remove slot")
            print("0) Back")
            c = prompt("Choose: ")
            if c == "1":
                rows = self.sys.list_availability(self.active_user)
                if not rows:
                    print("(no availability)")
                else:
                    for r in rows:
                        print(f"#{r['id']} {r['day_of_week']} {r['start_time']}–{r['end_time']}")
            elif c == "2":
                day = prompt("Day (Mon..Sun or full name): ")
                start = prompt('Start time "HH:MM": ')
                end = prompt('End time "HH:MM": ')
                self.sys.add_availability(self.active_user, day, start, end)
            elif c == "3":
                sid = prompt("Availability id to remove: ")
                if sid.isdigit():
                    self.sys.remove_availability(int(sid))
                else:
                    print("Invalid id.")
            elif c == "0":
                break
            else:
                print("Invalid choice.")

    def find_classmates_flow(self):
        self._need_active()
        course = prompt("Course code to search (e.g., MATH 4000): ")
        rows = self.sys.find_classmates_by_course(self.active_user, course)
        if not rows:
            print("No classmates found for that course. (AC-3)")
        else:
            for r in rows:
                print(f"- {r['username']} ({r['full_name']})")

    def suggest_matches_flow(self):
        self._need_active()
        suggestions = self.sys.suggest_matches(self.active_user)
        if not suggestions:
            print("No matches found. (AC-4)")
            return
        for s in suggestions:
            shared = ", ".join(s["shared_courses"])
            print(f"- {s['classmate_username']} ({s['full_name']}) | courses: {shared} "
                  f"| overlap: {s['overlap_day']} {s['overlap_start']}–{s['overlap_end']}")

    def propose_session_flow(self):
        self._need_active()
        invitee = prompt("Invitee username: ")
        course = prompt("Shared course code: ")
        day = prompt("Day (Mon..Sun or full name): ")
        start = prompt('Start time "HH:MM": ')
        end = prompt('End time "HH:MM": ')
        self.sys.propose_session(self.active_user, invitee, course, day, start, end)

    def confirm_sessions_flow(self):
        self._need_active()
        rows = self.sys.list_proposed_for_invitee(self.active_user)
        if not rows:
            print("No proposed sessions to confirm.")
            return
        print("-- Proposed sessions --")
        for r in rows:
            print(f"#{r['id']} from {r['initiator_username']} | {r['course_code']} "
                  f"| {r['day_of_week']} {r['start_time']}–{r['end_time']}")
        sid = prompt("Enter session id to confirm (or blank to cancel): ")
        if sid and sid.isdigit():
            self.sys.confirm_session(int(sid), self.active_user)

    def list_sessions_flow(self):
        self._need_active()
        rows = self.sys.list_sessions_for(self.active_user)
        if not rows:
            print("(no sessions)")
            return
        for r in rows:
            print(f"#{r['id']} {r['status']} | {r['course_code']} | {r['day_of_week']} "
                  f"{r['start_time']}–{r['end_time']} | "
                  f"{r['initiator_username']} -> {r['invitee_username']}")

    def _need_active(self):
        if not self.active_user:
            raise RuntimeError("Active user required. (should not happen after start)")
        # no return value; used just as a guard


# --------------------------- Entry Point ---------------------------

def main():
    init_db()
    system = StudyBuddySystem()
    ui = MenuUI(system)
    ui.run()

if __name__ == "__main__":
    main()
