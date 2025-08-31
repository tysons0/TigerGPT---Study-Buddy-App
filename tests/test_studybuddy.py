

import unittest
import sqlite3
import sys
import os
from unittest.mock import patch, MagicMock      #used for python testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from studybuddy import StudyBuddySystem, SCHEMA_SQL



def get_test_conn():        #resets database for each test
    """Returns a fresh in-memory SQLite connection with schema initialized."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    return conn


class TestStudyBuddySystem(unittest.TestCase):
    def setUp(self):
        self.conn = get_test_conn()
        self.system = StudyBuddySystem()
        # Patch the system's get_conn method to use our in-memory DB
        self.original_get_conn = self.system.__class__.__dict__['create_profile'].__globals__['get_conn']
        self.system.__class__.__dict__['create_profile'].__globals__['get_conn'] = lambda: self.conn

    def tearDown(self):     # Restore the original get_conn after each test
        self.system.__class__.__dict__['create_profile'].__globals__['get_conn'] = self.original_get_conn
        self.conn.close()

    def test_create_profile_success(self):          #profile creation test, returns true if successful
        result = self.system.create_profile("alice", "Alice Smith")
        self.assertTrue(result)
    
    def test_create_profile_duplicate(self):            #duplicate test, returns false if username already exists
        self.system.create_profile("bob", "Bob Jones")
        result = self.system.create_profile("bob", "Bobby Jones")
        self.assertFalse(result)

    def test_add_and_list_courses(self):                    #add courses test, lists courses if added successfully, returns true
        self.system.create_profile("carol", "Carol White")
        self.assertTrue(self.system.add_course("carol", "MATH 101"))
        self.assertTrue(self.system.add_course("carol", "CS 200"))
        courses = self.system.list_courses("carol")
        self.assertIn("MATH 101", courses)
        self.assertIn("CS 200", courses)

    def test_add_duplicate_course(self):        #returns false if course already exists
        self.system.create_profile("dave", "Dave Black")
        self.system.add_course("dave", "BIO 150")
        result = self.system.add_course("dave", "BIO 150")
        self.assertFalse(result)

    def test_remove_course(self):       #removes course if it exists, checks if course is removed from list
        self.system.create_profile("erin", "Erin Green")
        self.system.add_course("erin", "CHEM 101")
        self.system.remove_course("erin", "CHEM 101")
        courses = self.system.list_courses("erin")
        self.assertNotIn("CHEM 101", courses)

    def test_add_and_list_availability(self):           #adds availability if valid, lists availability slots
        self.system.create_profile("frank", "Frank Blue")
        self.assertTrue(self.system.add_availability("frank", "Monday", "10:00", "12:00"))
        slots = self.system.list_availability("frank")
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]["day_of_week"], "Mon")

    def test_add_invalid_availability(self):            #tests invalid availability inputs, returns false if invalid
        self.system.create_profile("gina", "Gina Red")
        # Invalid day
        self.assertFalse(self.system.add_availability("gina", "Funday", "10:00", "12:00"))
        # Invalid time
        self.assertFalse(self.system.add_availability("gina", "Mon", "25:00", "26:00"))
        # End before start
        self.assertFalse(self.system.add_availability("gina", "Mon", "12:00", "10:00"))

    def test_find_classmates_by_course(self):       #finds classmates enrolled in the same course, returns list of classmates, returns correct classmates
        self.system.create_profile("hank", "Hank Gray")
        self.system.create_profile("ivy", "Ivy Pink")
        self.system.add_course("hank", "ENG 101")
        self.system.add_course("ivy", "ENG 101")
        classmates = self.system.find_classmates_by_course("hank", "ENG 101")
        self.assertEqual(len(classmates), 1)
        self.assertEqual(classmates[0]["username"], "ivy")

    def test_suggest_matches_no_overlap(self):          #tests suggest matches with no overlapping availability, returns empty list if no matches found
        self.system.create_profile("jack", "Jack Orange")
        self.system.create_profile("kate", "Kate Purple")
        self.system.add_course("jack", "HIST 101")
        self.system.add_course("kate", "HIST 101")
        self.system.add_availability("jack", "Mon", "08:00", "09:00")
        self.system.add_availability("kate", "Mon", "10:00", "11:00")
        suggestions = self.system.suggest_matches("jack")
        self.assertEqual(suggestions, [])

    def test_suggest_matches_with_overlap(self):        #tests suggest matches with overlapping availability, returns list of matches if found, checks if correct match is returned
        self.system.create_profile("leo", "Leo Silver")
        self.system.create_profile("maya", "Maya Gold")
        self.system.add_course("leo", "PHYS 101")
        self.system.add_course("maya", "PHYS 101")
        self.system.add_availability("leo", "Tue", "10:00", "12:00")
        self.system.add_availability("maya", "Tue", "11:00", "13:00")
        suggestions = self.system.suggest_matches("leo")
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["classmate_username"], "maya")

