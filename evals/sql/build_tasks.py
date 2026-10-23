"""Source of truth for the SQL eval set: three SQLite databases, 45 tasks with reference queries.

    .venv/bin/python evals/sql/build_tasks.py      # writes tasks.jsonl and holdout_levels.jsonl

Written on 2026-10-23, before the SQL pack's claims, level cues, prompt or policies existed.
A task is the text a user would paste: the tables' CREATE statements, then a question. The
model sees the schema only; it is graded by running its query on the hidden data below and
comparing the rows with the reference query's (evals/run_sql.py): same columns in the same
order, rows as a multiset, or as a list when the question asks for an order.

The data is generated from a fixed seed, so the databases are the same on every build. The
script refuses to write a task whose reference returns no rows, or whose result changes when
the rows are inserted in reverse order (a tie at a LIMIT, or an order the question doesn't
fix), so every task has one right answer.

Levels, as written for this set:
    calm      one table: filters, sorting, a single aggregate
    alert     one join or one GROUP BY (or a plain join plus a GROUP BY)
    intensive subqueries or CTEs, window functions, rows that are missing (never/not any),
              self-joins, top-1 per group, comparisons against an aggregate
"""

import json
import random
import sqlite3
from pathlib import Path

SEED = 20261023
OUT = Path(__file__).parent

SCHEMAS = {
    "shop": """CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    joined TEXT NOT NULL  -- date, YYYY-MM-DD
);
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('books', 'games', 'music', 'tools')),
    price REAL NOT NULL
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    order_date TEXT NOT NULL,  -- date, YYYY-MM-DD
    status TEXT NOT NULL CHECK (status IN ('pending', 'shipped', 'cancelled'))
);
CREATE TABLE order_items (
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    PRIMARY KEY (order_id, product_id)
);""",
    "school": """CREATE TABLE teachers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL CHECK (department IN ('Math', 'Physics', 'History', 'Biology'))
);
CREATE TABLE courses (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    department TEXT NOT NULL CHECK (department IN ('Math', 'Physics', 'History', 'Biology')),
    credits INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL REFERENCES teachers(id)
);
CREATE TABLE students (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    year INTEGER NOT NULL CHECK (year BETWEEN 1 AND 4),
    major TEXT  -- NULL while undeclared
);
CREATE TABLE enrollments (
    student_id INTEGER NOT NULL REFERENCES students(id),
    course_id INTEGER NOT NULL REFERENCES courses(id),
    term TEXT NOT NULL CHECK (term IN ('2023F', '2024S', '2024F')),
    grade INTEGER,  -- 0 to 100; NULL while the course is in progress
    PRIMARY KEY (student_id, course_id, term)
);""",
    "company": """CREATE TABLE departments (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    budget INTEGER NOT NULL  -- yearly, in dollars
);
CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    manager_id INTEGER REFERENCES employees(id),  -- NULL for the CEO
    salary INTEGER NOT NULL,  -- yearly, in dollars
    hire_date TEXT NOT NULL  -- date, YYYY-MM-DD
);
CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    start_date TEXT NOT NULL,  -- date, YYYY-MM-DD
    end_date TEXT  -- NULL while the project is ongoing
);
CREATE TABLE assignments (
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    project_id INTEGER NOT NULL REFERENCES projects(id),
    hours INTEGER NOT NULL,
    PRIMARY KEY (employee_id, project_id)
);""",
}

FIRST = ["Ava", "Ben", "Cara", "Dev", "Ema", "Finn", "Gia", "Hugo", "Iris", "Jon", "Kai", "Lena", "Milo", "Nia",
         "Omar", "Pia", "Quin", "Rosa", "Sam", "Tara", "Uma", "Vic", "Wes", "Xena", "Yara", "Zed", "Alma", "Boris",
         "Cleo", "Dana", "Eli", "Faye", "Gus", "Hana", "Ivan", "Jade", "Kurt", "Lia", "Max", "Noor"]
LAST = ["Abbott", "Baker", "Chen", "Diaz", "Evans", "Fox", "Gupta", "Hale", "Ito", "Jones", "Khan", "Lopez", "Moss",
        "Novak", "Ortiz", "Patel", "Quist", "Reyes", "Silva", "Tran", "Ueda", "Vance", "Wong", "Young", "Zhou"]


def date(r, y0, y1):
    return f"{r.randint(y0, y1)}-{r.randint(1, 12):02d}-{r.randint(1, 28):02d}"


def people(r, n):
    names = [f"{f} {lst}" for f in FIRST for lst in LAST]
    return r.sample(names, n)


def shop_rows(r):
    cities = ["Austin", "Boston", "Chicago", "Denver", "Seattle"]
    customers = [(i, n, r.choice(cities), date(r, 2021, 2024)) for i, n in enumerate(people(r, 30), 1)]
    names = {"books": ["Atlas of Rivers", "Night Garden", "Paper Moons", "The Long Road"],
             "games": ["Castle Siege", "Hex Quest", "Star Miners", "Word Duel"],
             "music": ["Blue Hours", "Cedar Songs", "Neon Tide", "Quiet Engines"],
             "tools": ["Claw Hammer", "Hand Drill", "Socket Set", "Tape Measure"]}
    products, pid = [], 0
    for cat, ns in names.items():
        for n in ns:
            pid += 1
            products.append((pid, n, cat, round(r.uniform(6, 90), 2)))
    orders, items = [], []
    for oid in range(1, 81):
        # customers 27-30 never order; products 15-16 are never ordered
        orders.append((oid, r.randint(1, 26), date(r, 2023, 2024),
                       r.choices(["pending", "shipped", "cancelled"], [2, 6, 1])[0]))
        for p in r.sample(range(1, 15), r.randint(1, 4)):
            items.append((oid, p, r.randint(1, 5)))
    return {"customers": customers, "products": products, "orders": orders, "order_items": items}


def school_rows(r):
    depts = ["Math", "Physics", "History", "Biology"]
    teachers = [(i, n, depts[(i - 1) % 4]) for i, n in enumerate(people(r, 8), 1)]
    titles = {"Math": ["Calculus I", "Linear Algebra", "Number Theory", "Statistics"],
              "Physics": ["Mechanics", "Optics", "Thermodynamics"],
              "History": ["Ancient Rome", "Modern Europe", "World Wars", "Silk Road"],
              "Biology": ["Genetics", "Ecology", "Cell Biology"]}
    courses, cid = [], 0
    for d, ts in titles.items():
        for t in ts:
            cid += 1
            teacher = r.choice([tid for tid, _, td in teachers if td == d])
            courses.append((cid, t, d, r.randint(2, 5), teacher))
    students = [(i, n, r.randint(1, 4), r.choice(depts + [None])) for i, n in enumerate(people(r, 40), 1)]
    enrollments = []
    for sid, *_ in students:
        for c in r.sample(range(1, cid + 1), r.randint(2, 5)):
            term = r.choice(["2023F", "2024S", "2024F"])
            grade = None if term == "2024F" and r.random() < 0.5 else r.randint(48, 100)
            enrollments.append((sid, c, term, grade))
    return {"teachers": teachers, "courses": courses, "students": students, "enrollments": enrollments}


def company_rows(r):
    departments = [(1, "Executive", 900000), (2, "Engineering", 1500000), (3, "Research", 700000),
                   (4, "Sales", 650000), (5, "Support", 420000), (6, "Finance", 500000)]
    names = people(r, 36)
    employees = [(1, names[0], 1, None, 250000, "2010-03-15")]
    heads = {}
    for d in range(2, 7):  # each department's head reports to the CEO
        eid = len(employees) + 1
        heads[d] = eid
        employees.append((eid, names[eid - 1], d, 1, r.randrange(150000, 210000, 1000), date(r, 2010, 2016)))
    while len(employees) < 36:
        eid = len(employees) + 1
        d = r.randint(2, 6)
        salary = r.randrange(50000, 140000, 1000)
        if eid in (9, 17, 26):  # these earn more than their head, so "earns more than their manager" has rows
            salary = employees[heads[d] - 1][4] + 1000 * eid
        employees.append((eid, names[eid - 1], d, heads[d], salary, date(r, 2012, 2024)))
    for i, e in enumerate(employees):  # Executive staff: two reports of the CEO
        if e[0] in (35, 36):
            employees[i] = (e[0], e[1], 1, 1, e[4], e[5])
    projects = [(i, n, d, s, e) for i, (n, d, s, e) in enumerate([
        ("Apollo", 2, "2022-02-01", "2023-06-30"), ("Beacon", 2, "2023-04-01", None), ("Cobalt", 3, "2021-09-01", None),
        ("Delta", 3, "2022-11-15", "2024-03-01"), ("Ember", 4, "2023-01-10", None), ("Falcon", 4, "2024-05-01", None),
        ("Garnet", 5, "2022-06-01", "2022-12-31"), ("Harbor", 6, "2023-08-01", None), ("Iris", 2, "2024-02-01", None),
        ("Juniper", 3, "2024-07-01", None)], 1)]
    assignments = []
    for eid in range(2, 31):  # employees 31-36 have no project
        for p in r.sample(range(1, 11), r.randint(1, 3)):
            assignments.append((eid, p, r.randrange(10, 400, 5)))
    return {"departments": departments, "employees": employees, "projects": projects, "assignments": assignments}


ROWS = {"shop": shop_rows, "school": school_rows, "company": company_rows}

# Each task: (id, level, schema, question, reference SQL, ordered)
TASKS = [
    # ---------------- calm ----------------
    ("sql-c01", "calm", "shop", "List the names of all products in the 'games' category.",
     "SELECT name FROM products WHERE category = 'games'", False),
    ("sql-c02", "calm", "shop", "How many customers live in Denver?",
     "SELECT COUNT(*) FROM customers WHERE city = 'Denver'", False),
    ("sql-c03", "calm", "shop", "List the name and price of every product that costs more than 40, most expensive first.",
     "SELECT name, price FROM products WHERE price > 40 ORDER BY price DESC", True),
    ("sql-c04", "calm", "shop", "What is the average price of all products?",
     "SELECT AVG(price) FROM products", False),
    ("sql-c05", "calm", "shop", "List the ids of the orders that were cancelled.",
     "SELECT id FROM orders WHERE status = 'cancelled'", False),
    ("sql-c06", "calm", "shop", "List the distinct cities our customers live in, in alphabetical order.",
     "SELECT DISTINCT city FROM customers ORDER BY city", True),
    ("sql-c07", "calm", "school", "List the names of the students in year 4.",
     "SELECT name FROM students WHERE year = 4", False),
    ("sql-c08", "calm", "school", "How many courses does the Math department offer?",
     "SELECT COUNT(*) FROM courses WHERE department = 'Math'", False),
    ("sql-c09", "calm", "school", "What is the highest grade recorded in any enrollment?",
     "SELECT MAX(grade) FROM enrollments", False),
    ("sql-c10", "calm", "school", "List the titles of the courses worth at least 4 credits, in alphabetical order.",
     "SELECT title FROM courses WHERE credits >= 4 ORDER BY title", True),
    ("sql-c11", "calm", "company", "List the names of the employees hired in 2020 or later.",
     "SELECT name FROM employees WHERE hire_date >= '2020-01-01'", False),
    ("sql-c12", "calm", "company", "What is the total budget of all departments together?",
     "SELECT SUM(budget) FROM departments", False),
    ("sql-c13", "calm", "company", "List the name and salary of the 5 highest-paid employees, highest salary first.",
     "SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 5", True),
    ("sql-c14", "calm", "company", "How many projects are still ongoing?",
     "SELECT COUNT(*) FROM projects WHERE end_date IS NULL", False),
    ("sql-c15", "calm", "school", "List the names of the students who haven't declared a major.",
     "SELECT name FROM students WHERE major IS NULL", False),
    # ---------------- alert ----------------
    ("sql-a01", "alert", "shop", "For each product category, how many products are in it? Return the category and the count.",
     "SELECT category, COUNT(*) FROM products GROUP BY category", False),
    ("sql-a02", "alert", "shop", "List the names of the customers who placed at least one order in 2024, each name once.",
     "SELECT DISTINCT c.name FROM customers c JOIN orders o ON o.customer_id = c.id WHERE o.order_date LIKE '2024-%'", False),
    ("sql-a03", "alert", "shop", "How many orders have each status? Return the status and the number of orders.",
     "SELECT status, COUNT(*) FROM orders GROUP BY status", False),
    ("sql-a04", "alert", "shop", "For the orders placed in December 2024, list each order's id and the name of the customer who placed it.",
     "SELECT o.id, c.name FROM orders o JOIN customers c ON c.id = o.customer_id WHERE o.order_date LIKE '2024-12-%'", False),
    ("sql-a05", "alert", "shop", "What total quantity of each product has been ordered? Return the product name and the total quantity, for products ordered at least once.",
     "SELECT p.name, SUM(i.quantity) FROM order_items i JOIN products p ON p.id = i.product_id GROUP BY p.id", False),
    ("sql-a06", "alert", "school", "What is the average number of credits of each department's courses? Return the department and the average.",
     "SELECT department, AVG(credits) FROM courses GROUP BY department", False),
    ("sql-a07", "alert", "school", "List every course's title together with the name of the teacher who teaches it.",
     "SELECT c.title, t.name FROM courses c JOIN teachers t ON t.id = c.teacher_id", False),
    ("sql-a08", "alert", "school", "How many enrollments are there in each term? Return the term and the number of enrollments.",
     "SELECT term, COUNT(*) FROM enrollments GROUP BY term", False),
    ("sql-a09", "alert", "school", "List the names of the students enrolled in Linear Algebra in term 2024F.",
     "SELECT s.name FROM students s JOIN enrollments e ON e.student_id = s.id JOIN courses c ON c.id = e.course_id "
     "WHERE c.title = 'Linear Algebra' AND e.term = '2024F'", False),
    ("sql-a10", "alert", "school", "How many students are there in each year? Return the year and the number of students.",
     "SELECT year, COUNT(*) FROM students GROUP BY year", False),
    ("sql-a11", "alert", "company", "List each employee's name together with the name of their department.",
     "SELECT e.name, d.name FROM employees e JOIN departments d ON d.id = e.department_id", False),
    ("sql-a12", "alert", "company", "What is the average salary in each department? Return the department name and the average salary.",
     "SELECT d.name, AVG(e.salary) FROM employees e JOIN departments d ON d.id = e.department_id GROUP BY d.id", False),
    ("sql-a13", "alert", "company", "List the names of the projects that belong to the Research department.",
     "SELECT p.name FROM projects p JOIN departments d ON d.id = p.department_id WHERE d.name = 'Research'", False),
    ("sql-a14", "alert", "company", "How many hours in total are assigned to each project? Return the project name and the total hours.",
     "SELECT p.name, SUM(a.hours) FROM assignments a JOIN projects p ON p.id = a.project_id GROUP BY p.id", False),
    ("sql-a15", "alert", "company", "How many employees report directly to each manager? Return the manager's id and the number of direct reports.",
     "SELECT manager_id, COUNT(*) FROM employees WHERE manager_id IS NOT NULL GROUP BY manager_id", False),
    # ---------------- intensive ----------------
    ("sql-i01", "intensive", "shop", "List the names of the customers who have never placed an order.",
     "SELECT name FROM customers WHERE id NOT IN (SELECT customer_id FROM orders)", False),
    ("sql-i02", "intensive", "shop", "What is the revenue (quantity times price) of shipped orders from customers in each city? Return the city and the revenue rounded to 2 decimals.",
     "SELECT c.city, ROUND(SUM(i.quantity * p.price), 2) FROM orders o JOIN customers c ON c.id = o.customer_id "
     "JOIN order_items i ON i.order_id = o.id JOIN products p ON p.id = i.product_id WHERE o.status = 'shipped' GROUP BY c.city", False),
    ("sql-i03", "intensive", "shop", "Which customer has spent the most on shipped orders, counting quantity times price? Return their name and the amount, rounded to 2 decimals.",
     "SELECT c.name, ROUND(SUM(i.quantity * p.price), 2) AS spent FROM orders o JOIN customers c ON c.id = o.customer_id "
     "JOIN order_items i ON i.order_id = o.id JOIN products p ON p.id = i.product_id WHERE o.status = 'shipped' "
     "GROUP BY c.id ORDER BY spent DESC LIMIT 1", False),
    ("sql-i04", "intensive", "shop", "List the names of the products that have never been ordered.",
     "SELECT name FROM products WHERE id NOT IN (SELECT product_id FROM order_items)", False),
    ("sql-i05", "intensive", "shop", "For each category, which is its most expensive product? Return the category and the product's name.",
     "SELECT category, name FROM products p WHERE price = (SELECT MAX(price) FROM products q WHERE q.category = p.category)", False),
    ("sql-i06", "intensive", "shop", "An order's value is the sum of quantity times price over its items. List the ids of the orders whose value is above the average order value.",
     "WITH v AS (SELECT i.order_id, SUM(i.quantity * p.price) AS value FROM order_items i JOIN products p ON p.id = i.product_id "
     "GROUP BY i.order_id) SELECT order_id FROM v WHERE value > (SELECT AVG(value) FROM v)", False),
    ("sql-i07", "intensive", "school", "For each course with at least 5 graded enrollments, what is its average grade, ignoring enrollments still in progress? Return the course title and the average rounded to 1 decimal.",
     "SELECT c.title, ROUND(AVG(e.grade), 1) FROM enrollments e JOIN courses c ON c.id = e.course_id WHERE e.grade IS NOT NULL "
     "GROUP BY c.id HAVING COUNT(e.grade) >= 5", False),
    ("sql-i08", "intensive", "school", "List the names of the students whose average grade is higher than the average of all recorded grades.",
     "SELECT s.name FROM students s JOIN enrollments e ON e.student_id = s.id WHERE e.grade IS NOT NULL GROUP BY s.id "
     "HAVING AVG(e.grade) > (SELECT AVG(grade) FROM enrollments)", False),
    ("sql-i09", "intensive", "school", "Which teacher's courses have the most enrollments in total? Return the teacher's name and the number of enrollments.",
     "SELECT t.name, COUNT(*) AS n FROM enrollments e JOIN courses c ON c.id = e.course_id JOIN teachers t ON t.id = c.teacher_id "
     "GROUP BY t.id ORDER BY n DESC LIMIT 1", False),
    ("sql-i10", "intensive", "school", "List the names of the students who have taken both a Math course and a History course, each name once.",
     "SELECT s.name FROM students s WHERE s.id IN (SELECT e.student_id FROM enrollments e JOIN courses c ON c.id = e.course_id "
     "WHERE c.department = 'Math') AND s.id IN (SELECT e.student_id FROM enrollments e JOIN courses c ON c.id = e.course_id "
     "WHERE c.department = 'History')", False),
    ("sql-i11", "intensive", "company", "List the names of the employees who earn more than their manager.",
     "SELECT e.name FROM employees e JOIN employees m ON m.id = e.manager_id WHERE e.salary > m.salary", False),
    ("sql-i12", "intensive", "company", "Who is the highest-paid employee in each department? Return the department name and the employee's name.",
     "SELECT d.name, e.name FROM employees e JOIN departments d ON d.id = e.department_id "
     "WHERE e.salary = (SELECT MAX(salary) FROM employees x WHERE x.department_id = e.department_id)", False),
    ("sql-i13", "intensive", "company", "List the names of the employees who are not assigned to any project.",
     "SELECT name FROM employees WHERE id NOT IN (SELECT employee_id FROM assignments)", False),
    ("sql-i14", "intensive", "company", "Which departments pay more in total salaries than their budget? Return the department name, the total salary and the budget.",
     "SELECT d.name, SUM(e.salary), d.budget FROM departments d JOIN employees e ON e.department_id = d.id GROUP BY d.id "
     "HAVING SUM(e.salary) > d.budget", False),
    ("sql-i15", "intensive", "company", "Rank the employees by salary within their department, 1 being the highest paid, with equal salaries sharing a rank. Return the employee's name, the department name and the rank.",
     "SELECT e.name, d.name, RANK() OVER (PARTITION BY e.department_id ORDER BY e.salary DESC) FROM employees e "
     "JOIN departments d ON d.id = e.department_id", False),
]

# How the question is put after the schema, cycled so the router sees more than one phrasing.
LEADS = ["Write a SQL query to answer this: {q}", "Using these tables, write a query: {q}", "{q} Write the SQLite query.",
         "Given the schema above. {q}"]

# Level holdout: questions on a fourth schema, labeled before the level cues were written; no keys,
# used only by evals/eval_levels.py and the router test.
LIBRARY = """CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL, genre TEXT, published INTEGER);
CREATE TABLE members (id INTEGER PRIMARY KEY, name TEXT NOT NULL, joined TEXT NOT NULL);
CREATE TABLE loans (book_id INTEGER REFERENCES books(id), member_id INTEGER REFERENCES members(id), loaned TEXT NOT NULL, returned TEXT);"""
HOLDOUT = [
    ("sqo-c1", "calm", "List the titles of all books published before 1950."),
    ("sqo-c2", "calm", "How many members joined in 2023?"),
    ("sqo-c3", "calm", "List every book's title and author, sorted by title."),
    ("sqo-c4", "calm", "What is the earliest publication year in the collection?"),
    ("sqo-c5", "calm", "How many loans have not been returned yet?"),
    ("sqo-c6", "calm", "List the distinct genres in the collection."),
    ("sqo-c7", "calm", "Show the names of members whose name starts with 'A'."),
    ("sqo-c8", "calm", "What are the ten most recently published books? Return title and year."),
    ("sqo-a1", "alert", "How many books are there in each genre? Return the genre and the count."),
    ("sqo-a2", "alert", "List each loan's book title and member name."),
    ("sqo-a3", "alert", "How many loans has each member taken? Return the member id and the number of loans."),
    ("sqo-a4", "alert", "List the titles of the books borrowed by the member named 'Ann Lee'."),
    ("sqo-a5", "alert", "For each author, how many books do we hold? Return author and count."),
    ("sqo-a6", "alert", "List the names of the members who currently have a book out, each name once."),
    ("sqo-a7", "alert", "What is the average publication year of each genre's books?"),
    ("sqo-a8", "alert", "Show the titles of the books loaned in March 2024 together with the loan date."),
    ("sqo-i1", "intensive", "List the titles of the books that have never been borrowed."),
    ("sqo-i2", "intensive", "Which member has borrowed the most books? Return their name and the number of loans."),
    ("sqo-i3", "intensive", "For each genre, which book has been borrowed most often? Return the genre and the title."),
    ("sqo-i4", "intensive", "List the members who have borrowed more books than the average member."),
    ("sqo-i5", "intensive", "Rank the authors by number of loans of their books, with ties sharing a rank."),
    ("sqo-i6", "intensive", "List the names of members who borrowed both a 'mystery' book and a 'history' book."),
    ("sqo-i7", "intensive", "For each member, show each loan date and the date of their previous loan."),
    ("sqo-i8", "intensive", "Which books were borrowed by every member who joined in 2022?"),
]


# ---------------- fresh set ----------------
# Written on 2026-10-23 after the SQL sweep and before any model answered it, to confirm the shipped
# policy (evals/run_sql.py FRESH_RULE): new schemas and data (own seed), and harder on purpose, since
# the coder alone got 44/45 on the eval set. -> fresh.jsonl
FRESH_SEED = 20261024
FRESH_SCHEMAS = {
    "clinic": """CREATE TABLE patients (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    birth_year INTEGER NOT NULL,
    city TEXT NOT NULL
);
CREATE TABLE doctors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    specialty TEXT NOT NULL CHECK (specialty IN ('cardiology', 'dermatology', 'pediatrics', 'neurology'))
);
CREATE TABLE appointments (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    doctor_id INTEGER NOT NULL REFERENCES doctors(id),
    day TEXT NOT NULL,  -- date, YYYY-MM-DD
    status TEXT NOT NULL CHECK (status IN ('booked', 'done', 'missed')),
    fee REAL NOT NULL  -- charged when the appointment is done
);""",
    "transit": """CREATE TABLE stations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    line TEXT NOT NULL CHECK (line IN ('red', 'blue', 'green'))
);
CREATE TABLE cards (
    id INTEGER PRIMARY KEY,
    owner TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('adult', 'student', 'senior'))
);
CREATE TABLE trips (
    id INTEGER PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cards(id),
    from_station INTEGER NOT NULL REFERENCES stations(id),
    to_station INTEGER NOT NULL REFERENCES stations(id),
    started TEXT NOT NULL,  -- YYYY-MM-DD HH:MM
    fare REAL NOT NULL
);""",
    "warehouse": """CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT NOT NULL
);
CREATE TABLE parts (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    unit_cost REAL NOT NULL
);
CREATE TABLE stock (
    part_id INTEGER NOT NULL REFERENCES parts(id),
    warehouse TEXT NOT NULL CHECK (warehouse IN ('north', 'south', 'east')),
    qty INTEGER NOT NULL,
    PRIMARY KEY (part_id, warehouse)
);
CREATE TABLE shipments (
    id INTEGER PRIMARY KEY,
    part_id INTEGER NOT NULL REFERENCES parts(id),
    warehouse TEXT NOT NULL CHECK (warehouse IN ('north', 'south', 'east')),
    shipped_on TEXT NOT NULL,  -- date, YYYY-MM-DD
    qty INTEGER NOT NULL
);""",
}


def clinic_rows(r):
    patients = [(i, n, r.randint(1940, 2015), r.choice(["Leeds", "York", "Hull", "Bath"])) for i, n in enumerate(people(r, 30), 1)]
    specialties = ["cardiology", "dermatology", "pediatrics", "neurology", "cardiology", "neurology"]
    doctors = [(i, f"Dr. {n.split()[1]}", specialties[i - 1]) for i, n in enumerate(people(r, 6), 1)]
    appointments = []
    for aid in range(1, 151):
        status = r.choices(["done", "missed", "booked"], [7, 2, 1])[0]
        # patients 29-30 have no appointments
        appointments.append((aid, r.randint(1, 28), r.randint(1, 6), date(r, 2023, 2024), status,
                             float(r.choice([40, 55, 60, 75, 90, 120]))))
    return {"patients": patients, "doctors": doctors, "appointments": appointments}


def transit_rows(r):
    names = ["Abbey", "Bridge", "Castle", "Dock", "Elm", "Forge", "Gate", "Harbor", "Inn", "Junction", "Keep", "Lantern"]
    stations = [(i, n, ["red", "blue", "green"][(i - 1) % 3]) for i, n in enumerate(names, 1)]
    cards = [(i, n, r.choice(["adult", "adult", "student", "senior"])) for i, n in enumerate(people(r, 20), 1)]
    trips = []
    for tid in range(1, 201):
        a, b = r.sample(range(1, 11), 2)  # stations 11-12 are never used
        started = f"2024-03-{r.randint(1, 10):02d} {r.randint(6, 22):02d}:{r.randint(0, 59):02d}"
        trips.append((tid, r.randint(1, 20), a, b, started, round(r.uniform(1.2, 4.8), 2)))
    return {"stations": stations, "cards": cards, "trips": trips}


def warehouse_rows(r):
    suppliers = [(1, "Acme", "Germany"), (2, "Borel", "France"), (3, "Cortez", "Spain"), (4, "Dahl", "Germany"),
                 (5, "Ekberg", "Sweden"), (6, "Fiore", "Italy")]
    names = ["bolt", "nut", "washer", "gear", "spring", "bearing", "valve", "hinge", "pulley", "clamp", "rivet",
             "sprocket", "bracket", "piston", "gasket", "shaft"]
    parts = [(i, n, r.randint(1, 5), round(r.uniform(0.5, 120), 2)) for i, n in enumerate(names, 1)]
    stock = []
    for pid in range(1, 17):
        for w in r.sample(["north", "south", "east"], r.randint(1, 3)):
            stock.append((pid, w, r.choice([0, r.randint(1, 900)])))
    shipments = [(i, r.randint(1, 16), r.choice(["north", "south", "east"]), date(r, 2023, 2024), r.randint(5, 400))
                 for i in range(1, 91)]
    return {"suppliers": suppliers, "parts": parts, "stock": stock, "shipments": shipments}


FRESH_ROWS = {"clinic": clinic_rows, "transit": transit_rows, "warehouse": warehouse_rows}

FRESH = [
    # ---------------- calm ----------------
    ("sqf-c01", "calm", "clinic", "List the names of the doctors whose specialty is cardiology.",
     "SELECT name FROM doctors WHERE specialty = 'cardiology'", False),
    ("sqf-c02", "calm", "clinic", "How many appointments were missed?",
     "SELECT COUNT(*) FROM appointments WHERE status = 'missed'", False),
    ("sqf-c03", "calm", "transit", "List the names of the stations on the blue line, in alphabetical order.",
     "SELECT name FROM stations WHERE line = 'blue' ORDER BY name", True),
    ("sqf-c04", "calm", "transit", "What is the highest fare paid for any trip?",
     "SELECT MAX(fare) FROM trips", False),
    ("sqf-c05", "calm", "warehouse", "List the names of the parts that cost more than 50 per unit.",
     "SELECT name FROM parts WHERE unit_cost > 50", False),
    ("sqf-c06", "calm", "warehouse", "How many suppliers are based in Germany?",
     "SELECT COUNT(*) FROM suppliers WHERE country = 'Germany'", False),
    # ---------------- alert ----------------
    ("sqf-a01", "alert", "clinic", "How many appointments has each doctor had, whatever their status? Return the doctor's name and the count.",
     "SELECT d.name, COUNT(*) FROM appointments a JOIN doctors d ON d.id = a.doctor_id GROUP BY d.id", False),
    ("sqf-a02", "alert", "clinic", "What is the total fee from done appointments for each specialty? Return the specialty and the total.",
     "SELECT d.specialty, SUM(a.fee) FROM appointments a JOIN doctors d ON d.id = a.doctor_id WHERE a.status = 'done' "
     "GROUP BY d.specialty", False),
    ("sqf-a03", "alert", "transit", "How many trips were taken with each kind of card? Return the card kind and the number of trips.",
     "SELECT c.kind, COUNT(*) FROM trips t JOIN cards c ON c.id = t.card_id GROUP BY c.kind", False),
    ("sqf-a04", "alert", "transit", "List the names of the stations where at least one trip started, each name once.",
     "SELECT DISTINCT s.name FROM trips t JOIN stations s ON s.id = t.from_station", False),
    ("sqf-a05", "alert", "transit", "What was the average fare on each day? Return the date (YYYY-MM-DD) and the average fare, in date order.",
     "SELECT substr(started, 1, 10) AS d, AVG(fare) FROM trips GROUP BY d ORDER BY d", True),
    ("sqf-a06", "alert", "warehouse", "What is the total quantity in stock in each warehouse? Return the warehouse and the total.",
     "SELECT warehouse, SUM(qty) FROM stock GROUP BY warehouse", False),
    ("sqf-a07", "alert", "warehouse", "List every part's name together with the name of its supplier.",
     "SELECT p.name, s.name FROM parts p JOIN suppliers s ON s.id = p.supplier_id", False),
    ("sqf-a08", "alert", "warehouse", "What is the value of the stock (quantity times unit cost) in each warehouse? Return the warehouse and the value rounded to 2 decimals.",
     "SELECT st.warehouse, ROUND(SUM(st.qty * p.unit_cost), 2) FROM stock st JOIN parts p ON p.id = st.part_id "
     "GROUP BY st.warehouse", False),
    # ---------------- intensive ----------------
    ("sqf-i01", "intensive", "clinic", "List the names of the patients who have had at least one appointment and have never missed one.",
     "SELECT p.name FROM patients p WHERE EXISTS (SELECT 1 FROM appointments a WHERE a.patient_id = p.id) "
     "AND NOT EXISTS (SELECT 1 FROM appointments a WHERE a.patient_id = p.id AND a.status = 'missed')", False),
    ("sqf-i02", "intensive", "clinic", "For each patient with more than one done appointment, how many days passed between their first and their last done appointment? Return the patient's name and the number of days.",
     "SELECT p.name, julianday(MAX(a.day)) - julianday(MIN(a.day)) FROM appointments a JOIN patients p ON p.id = a.patient_id "
     "WHERE a.status = 'done' GROUP BY p.id HAVING COUNT(*) > 1", False),
    ("sqf-i03", "intensive", "clinic", "Which doctor has the highest share of missed appointments among all their appointments? Return the doctor's name and that share as a fraction between 0 and 1.",
     "SELECT d.name, AVG(a.status = 'missed') AS share FROM appointments a JOIN doctors d ON d.id = a.doctor_id "
     "GROUP BY d.id ORDER BY share DESC LIMIT 1", False),
    ("sqf-i04", "intensive", "clinic", "For the patient with id 3, list each appointment's day in date order, with the number of days since that patient's previous appointment (NULL for the first).",
     "SELECT day, julianday(day) - julianday(LAG(day) OVER (ORDER BY day)) FROM appointments WHERE patient_id = 3 ORDER BY day", True),
    ("sqf-i05", "intensive", "transit", "List each trip's id together with the names of its start station and its end station.",
     "SELECT t.id, a.name, b.name FROM trips t JOIN stations a ON a.id = t.from_station JOIN stations b ON b.id = t.to_station", False),
    ("sqf-i06", "intensive", "transit", "Which start and end station pairs were travelled more than twice? Return the start station's name, the end station's name and the number of trips.",
     "SELECT a.name, b.name, COUNT(*) FROM trips t JOIN stations a ON a.id = t.from_station JOIN stations b ON b.id = t.to_station "
     "GROUP BY t.from_station, t.to_station HAVING COUNT(*) > 2", False),
    ("sqf-i07", "intensive", "transit", "For card 7, list each trip's start time and the running total of its fares up to and including that trip, in time order.",
     "SELECT started, SUM(fare) OVER (ORDER BY started) FROM trips WHERE card_id = 7 ORDER BY started", True),
    ("sqf-i08", "intensive", "warehouse", "List the names of the suppliers that have no part in stock anywhere, counting only stock rows with a quantity above 0.",
     "SELECT s.name FROM suppliers s WHERE NOT EXISTS (SELECT 1 FROM parts p JOIN stock st ON st.part_id = p.id "
     "WHERE p.supplier_id = s.id AND st.qty > 0)", False),
    ("sqf-i09", "intensive", "warehouse", "For each warehouse, which part has the largest quantity in stock there? Return the warehouse and the part's name.",
     "SELECT st.warehouse, p.name FROM stock st JOIN parts p ON p.id = st.part_id "
     "WHERE st.qty = (SELECT MAX(qty) FROM stock x WHERE x.warehouse = st.warehouse)", False),
    ("sqf-i10", "intensive", "warehouse", "Which parts were shipped in a larger total quantity during 2024 than they now have in stock across all warehouses? Return the part's name, the quantity shipped in 2024 and the quantity in stock.",
     "WITH shipped AS (SELECT part_id, SUM(qty) AS q FROM shipments WHERE shipped_on LIKE '2024-%' GROUP BY part_id), "
     "held AS (SELECT part_id, SUM(qty) AS q FROM stock GROUP BY part_id) "
     "SELECT p.name, s.q, h.q FROM shipped s JOIN held h ON h.part_id = s.part_id JOIN parts p ON p.id = s.part_id WHERE s.q > h.q", False),
]


# ---------------- second fresh set ----------------
# Written on 2026-10-23 after the first fresh set failed to confirm the shipped policy, and before any
# model answered it, to judge that set's candidate (evals/run_sql.py FRESH2_RULE). New schemas and
# data (own seed), as hard as the first fresh set. -> fresh2.jsonl
FRESH2_SEED = 20261025
FRESH2_SCHEMAS = {
    "airline": """CREATE TABLE airports (
    code TEXT PRIMARY KEY,
    city TEXT NOT NULL,
    country TEXT NOT NULL
);
CREATE TABLE flights (
    id INTEGER PRIMARY KEY,
    flight_no TEXT NOT NULL UNIQUE,
    origin TEXT NOT NULL REFERENCES airports(code),
    dest TEXT NOT NULL REFERENCES airports(code),
    departs TEXT NOT NULL,  -- YYYY-MM-DD HH:MM
    seats INTEGER NOT NULL
);
CREATE TABLE passengers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    loyalty TEXT NOT NULL CHECK (loyalty IN ('none', 'silver', 'gold'))
);
CREATE TABLE bookings (
    id INTEGER PRIMARY KEY,
    flight_id INTEGER NOT NULL REFERENCES flights(id),
    passenger_id INTEGER NOT NULL REFERENCES passengers(id),
    price REAL NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('confirmed', 'cancelled'))
);""",
    "streaming": """CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT NOT NULL,
    plan TEXT NOT NULL CHECK (plan IN ('basic', 'premium'))
);
CREATE TABLE shows (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    genre TEXT NOT NULL CHECK (genre IN ('drama', 'comedy', 'documentary'))
);
CREATE TABLE episodes (
    id INTEGER PRIMARY KEY,
    show_id INTEGER NOT NULL REFERENCES shows(id),
    season INTEGER NOT NULL,
    number INTEGER NOT NULL,
    minutes INTEGER NOT NULL  -- running time
);
CREATE TABLE views (
    user_id INTEGER NOT NULL REFERENCES users(id),
    episode_id INTEGER NOT NULL REFERENCES episodes(id),
    watched_on TEXT NOT NULL,  -- date, YYYY-MM-DD
    minutes_watched INTEGER NOT NULL
);""",
    "bank": """CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL
);
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    kind TEXT NOT NULL CHECK (kind IN ('checking', 'savings')),
    opened TEXT NOT NULL  -- date, YYYY-MM-DD
);
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    posted TEXT NOT NULL,  -- date, YYYY-MM-DD
    amount REAL NOT NULL  -- positive: deposit; negative: withdrawal
);""",
}


def airline_rows(r):
    airports = [("CDG", "Paris", "France"), ("NCE", "Nice", "France"), ("LYS", "Lyon", "France"),
                ("FRA", "Frankfurt", "Germany"), ("MUC", "Munich", "Germany"), ("MAD", "Madrid", "Spain"),
                ("LIS", "Lisbon", "Portugal"), ("DUB", "Dublin", "Ireland")]
    codes = [a[0] for a in airports]
    flights = []
    for fid in range(1, 25):
        o, d = r.sample(codes, 2)
        flights.append((fid, f"PL{100 + fid * 7}", o, d, f"2024-0{r.randint(4, 6)}-{r.randint(1, 28):02d} "
                        f"{r.randint(5, 22):02d}:{r.choice(['00', '15', '30', '45'])}", r.choice([12, 16, 150, 180, 200, 220])))
    passengers = [(i, n, r.choice(["none", "none", "silver", "gold"])) for i, n in enumerate(people(r, 40), 1)]
    bookings = [(i, r.randint(1, 24), r.randint(1, 40), round(r.uniform(39, 420), 2),
                 r.choices(["confirmed", "cancelled"], [5, 1])[0]) for i in range(1, 421)]
    for fid in (3, 9):  # two small flights overbooked, so "overbooked" has rows
        flights[fid - 1] = flights[fid - 1][:5] + (12,)
        for _ in range(14):
            bookings.append((len(bookings) + 1, fid, r.randint(1, 40), round(r.uniform(39, 420), 2), "confirmed"))
    return {"airports": airports, "flights": flights, "passengers": passengers, "bookings": bookings}


def streaming_rows(r):
    users = [(i, n, r.choice(["UK", "US", "Canada", "India"]), r.choice(["basic", "premium"])) for i, n in enumerate(people(r, 30), 1)]
    titles = [("Harbor Lights", "drama"), ("Low Tide", "drama"), ("Crown Street", "drama"), ("Office Hours", "comedy"),
              ("Two Left Feet", "comedy"), ("Deep Blue", "documentary"), ("Night Sky", "documentary"), ("Salt Roads", "documentary")]
    shows = [(i, ti, g) for i, (ti, g) in enumerate(titles, 1)]
    episodes, eid = [], 0
    for sid in range(1, 9):
        for season in range(1, r.randint(1, 3) + 1):
            for number in range(1, r.randint(3, 6) + 1):
                eid += 1
                episodes.append((eid, sid, season, number, r.choice([22, 25, 30, 45, 50, 55])))
    watchable = [e for e in episodes if e[1] != 8]  # Salt Roads is never watched
    views = []
    for _ in range(260):
        e = r.choice(watchable)
        views.append((r.randint(1, 30), e[0], date(r, 2024, 2024), r.randint(5, e[4])))
    comedy = [e for e in episodes if e[1] in (4, 5)]
    for uid in (3, 11, 19):  # a few users watch both comedies, so "every comedy show" has rows
        for sid in (4, 5):
            e = next(x for x in comedy if x[1] == sid)
            views.append((uid, e[0], date(r, 2024, 2024), e[4]))
    return {"users": users, "shows": shows, "episodes": episodes, "views": views}


def bank_rows(r):
    customers = [(i, n, r.choice(["Oslo", "Bergen", "Tromso"])) for i, n in enumerate(people(r, 18), 1)]
    accounts, aid = [], 0
    for cid in range(1, 19):
        for _ in range(r.randint(1, 3)):
            aid += 1
            accounts.append((aid, cid, r.choice(["checking", "savings"]), date(r, 2019, 2023)))
    transactions, tid = [], 0
    for a in accounts:
        days = sorted(r.sample(range(1, 366), r.randint(4, 12)))  # distinct days, so date order is total
        for d in days:
            tid += 1
            month, day = divmod(d - 1, 28)
            amount = round(r.uniform(20, 900), 2) if r.random() < 0.55 else -round(r.uniform(20, 1200), 2)
            transactions.append((tid, a[0], f"2024-{min(month + 1, 12):02d}-{day + 1:02d}", amount))
    return {"customers": customers, "accounts": accounts, "transactions": transactions}


FRESH2_ROWS = {"airline": airline_rows, "streaming": streaming_rows, "bank": bank_rows}

FRESH2 = [
    # ---------------- calm ----------------
    ("sq2-c01", "calm", "airline", "List the codes of the airports in France.",
     "SELECT code FROM airports WHERE country = 'France'", False),
    ("sq2-c02", "calm", "airline", "How many flights have more than 180 seats?",
     "SELECT COUNT(*) FROM flights WHERE seats > 180", False),
    ("sq2-c03", "calm", "streaming", "List the titles of the documentary shows, in alphabetical order.",
     "SELECT title FROM shows WHERE genre = 'documentary' ORDER BY title", True),
    ("sq2-c04", "calm", "streaming", "What is the total running time of all episodes, in minutes?",
     "SELECT SUM(minutes) FROM episodes", False),
    ("sq2-c05", "calm", "bank", "How many savings accounts were opened in 2022?",
     "SELECT COUNT(*) FROM accounts WHERE kind = 'savings' AND opened LIKE '2022-%'", False),
    ("sq2-c06", "calm", "bank", "What is the largest single withdrawal? Return it as a positive amount.",
     "SELECT -MIN(amount) FROM transactions", False),
    # ---------------- alert ----------------
    ("sq2-a01", "alert", "airline", "How many confirmed bookings does each flight have? Return the flight number and the count, for flights with at least one confirmed booking.",
     "SELECT f.flight_no, COUNT(*) FROM bookings b JOIN flights f ON f.id = b.flight_id WHERE b.status = 'confirmed' GROUP BY f.id", False),
    ("sq2-a02", "alert", "airline", "List the names of the passengers who have a cancelled booking, each name once.",
     "SELECT DISTINCT p.name FROM passengers p JOIN bookings b ON b.passenger_id = p.id WHERE b.status = 'cancelled'", False),
    ("sq2-a03", "alert", "airline", "What is the average price of confirmed bookings for each loyalty level? Return the loyalty level and the average price.",
     "SELECT p.loyalty, AVG(b.price) FROM bookings b JOIN passengers p ON p.id = b.passenger_id WHERE b.status = 'confirmed' GROUP BY p.loyalty", False),
    ("sq2-a04", "alert", "streaming", "How many episodes does each show have? Return the show's title and the number of episodes.",
     "SELECT s.title, COUNT(*) FROM episodes e JOIN shows s ON s.id = e.show_id GROUP BY s.id", False),
    ("sq2-a05", "alert", "streaming", "How many minutes did the users in each country watch in total? Return the country and the total minutes watched.",
     "SELECT u.country, SUM(v.minutes_watched) FROM views v JOIN users u ON u.id = v.user_id GROUP BY u.country", False),
    ("sq2-a06", "alert", "bank", "How many accounts does each customer have? Return the customer's name and the count.",
     "SELECT c.name, COUNT(*) FROM accounts a JOIN customers c ON c.id = a.customer_id GROUP BY c.id", False),
    ("sq2-a07", "alert", "bank", "What is the balance of each account, summing all its transactions? Return the account id and the balance rounded to 2 decimals.",
     "SELECT account_id, ROUND(SUM(amount), 2) FROM transactions GROUP BY account_id", False),
    ("sq2-a08", "alert", "bank", "How much was deposited in each month of 2024? Return the month as YYYY-MM and the total deposits rounded to 2 decimals, in month order.",
     "SELECT substr(posted, 1, 7) AS m, ROUND(SUM(amount), 2) FROM transactions WHERE amount > 0 AND posted LIKE '2024-%' GROUP BY m ORDER BY m", True),
    # ---------------- intensive ----------------
    ("sq2-i01", "intensive", "airline", "Which flights are overbooked, with more confirmed bookings than seats? Return the flight number, the number of seats and the number of confirmed bookings.",
     "SELECT f.flight_no, f.seats, COUNT(*) FROM flights f JOIN bookings b ON b.flight_id = f.id WHERE b.status = 'confirmed' "
     "GROUP BY f.id HAVING COUNT(*) > f.seats", False),
    ("sq2-i02", "intensive", "airline", "Which routes, as origin and destination airport codes, have more than one flight? Return the origin, the destination and the number of flights.",
     "SELECT origin, dest, COUNT(*) FROM flights GROUP BY origin, dest HAVING COUNT(*) > 1", False),
    ("sq2-i03", "intensive", "airline", "List the names of the passengers with confirmed bookings on flights from at least six different origin airports.",
     "SELECT p.name FROM passengers p JOIN bookings b ON b.passenger_id = p.id JOIN flights f ON f.id = b.flight_id "
     "WHERE b.status = 'confirmed' GROUP BY p.id HAVING COUNT(DISTINCT f.origin) >= 6", False),
    ("sq2-i04", "intensive", "airline", "For each passenger with a confirmed booking, what is their most expensive confirmed booking? Return the passenger's name, the flight number and the price.",
     "SELECT p.name, f.flight_no, b.price FROM bookings b JOIN passengers p ON p.id = b.passenger_id JOIN flights f ON f.id = b.flight_id "
     "WHERE b.status = 'confirmed' AND b.price = (SELECT MAX(price) FROM bookings x WHERE x.passenger_id = b.passenger_id AND x.status = 'confirmed')", False),
    ("sq2-i05", "intensive", "streaming", "Which users have watched at least one episode of every comedy show? Return their names.",
     "SELECT u.name FROM users u WHERE NOT EXISTS (SELECT 1 FROM shows s WHERE s.genre = 'comedy' AND NOT EXISTS ("
     "SELECT 1 FROM views v JOIN episodes e ON e.id = v.episode_id WHERE v.user_id = u.id AND e.show_id = s.id))", False),
    ("sq2-i06", "intensive", "streaming", "For each show that has been watched, what share of its views were by premium users? Return the title and the share as a fraction between 0 and 1.",
     "SELECT s.title, AVG(u.plan = 'premium') FROM views v JOIN users u ON u.id = v.user_id JOIN episodes e ON e.id = v.episode_id "
     "JOIN shows s ON s.id = e.show_id GROUP BY s.id", False),
    ("sq2-i07", "intensive", "streaming", "List the titles of the shows that no user has watched.",
     "SELECT title FROM shows WHERE id NOT IN (SELECT e.show_id FROM views v JOIN episodes e ON e.id = v.episode_id)", False),
    ("sq2-i08", "intensive", "bank", "For account 4, list each transaction's date and amount with the account's balance after it, in date order, starting from a balance of 0.",
     "SELECT posted, amount, SUM(amount) OVER (ORDER BY posted) FROM transactions WHERE account_id = 4 ORDER BY posted", True),
    ("sq2-i09", "intensive", "bank", "Which customers have a negative total balance across all their accounts? Return the customer's name and that total rounded to 2 decimals.",
     "SELECT c.name, ROUND(SUM(t.amount), 2) FROM customers c JOIN accounts a ON a.customer_id = c.id JOIN transactions t ON t.account_id = a.id "
     "GROUP BY c.id HAVING SUM(t.amount) < 0", False),
    ("sq2-i10", "intensive", "bank", "For each customer with more than one account, how many days passed between the opening of their first account and their most recent one? Return the customer's name and the number of days.",
     "SELECT c.name, julianday(MAX(a.opened)) - julianday(MIN(a.opened)) FROM accounts a JOIN customers c ON c.id = a.customer_id "
     "GROUP BY c.id HAVING COUNT(*) > 1", False),
]


def build(schema, rows):
    db = sqlite3.connect(":memory:")
    db.executescript({**SCHEMAS, **FRESH_SCHEMAS, **FRESH2_SCHEMAS}[schema])
    for table, data in rows.items():
        db.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * len(data[0]))})", data)
    return db


def databases():
    """schema name -> (rows by table), for the eval set's schemas then the fresh set's; fixed by the seeds."""
    r, fresh, fresh2 = random.Random(SEED), random.Random(FRESH_SEED), random.Random(FRESH2_SEED)
    return ({name: ROWS[name](r) for name in SCHEMAS} | {name: FRESH_ROWS[name](fresh) for name in FRESH_SCHEMAS}
            | {name: FRESH2_ROWS[name](fresh2) for name in FRESH2_SCHEMAS})


def write_set(tasks, data, name):
    """Check every reference on the data (forward and reversed), then write the tasks to `name`."""
    forward = {s: build(s, rows) for s, rows in data.items()}
    reverse = {s: build(s, {t: list(reversed(v)) for t, v in rows.items()}) for s, rows in data.items()}
    schemas = {**SCHEMAS, **FRESH_SCHEMAS, **FRESH2_SCHEMAS}
    out = []
    for n, (tid, level, schema, question, ref, ordered) in enumerate(tasks):
        a = forward[schema].execute(ref).fetchall()
        b = reverse[schema].execute(ref).fetchall()
        if not a:
            raise SystemExit(f"refusing: {tid} returns no rows")
        if (a if ordered else sorted(a, key=repr)) != (b if ordered else sorted(b, key=repr)):
            raise SystemExit(f"refusing: {tid} depends on row order (a tie or an unfixed order)")
        prompt = f"{schemas[schema]}\n\n{LEADS[n % len(LEADS)].format(q=question)}"
        out.append({"id": tid, "level": level, "schema": schema, "question": question, "prompt": prompt,
                    "reference": ref, "ordered": ordered, "rows": len(a)})
    with (OUT / name).open("w") as f:
        for t in out:
            f.write(json.dumps(t) + "\n")
    counts = {lv: sum(t["level"] == lv for t in out) for lv in ("calm", "alert", "intensive")}
    print(f"wrote {len(out)} tasks {counts} to {name}; rows per reference: "
          + ", ".join(f"{t['id'][4:]}={t['rows']}" for t in out))


def main():
    ids = [t[0] for t in TASKS + FRESH + FRESH2]
    assert len(ids) == len(set(ids)), "duplicate task id"
    data = databases()
    write_set(TASKS, data, "tasks.jsonl")
    write_set(FRESH, data, "fresh.jsonl")
    write_set(FRESH2, data, "fresh2.jsonl")
    with (OUT / "holdout_levels.jsonl").open("w") as f:
        for hid, level, q in HOLDOUT:
            f.write(json.dumps({"id": hid, "level": level, "prompt": f"{LIBRARY}\n\nWrite a SQL query: {q}"}) + "\n")
    print(f"wrote {len(HOLDOUT)} holdout texts")


if __name__ == "__main__":
    main()
