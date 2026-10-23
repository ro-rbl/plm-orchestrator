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


def build(schema, rows):
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMAS[schema])
    for table, data in rows.items():
        db.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * len(data[0]))})", data)
    return db


def databases():
    """schema name -> (rows by table); fixed by SEED."""
    r = random.Random(SEED)
    return {name: ROWS[name](r) for name in SCHEMAS}


def main():
    data = databases()
    forward = {s: build(s, rows) for s, rows in data.items()}
    reverse = {s: build(s, {t: list(reversed(v)) for t, v in rows.items()}) for s, rows in data.items()}
    ids = [t[0] for t in TASKS]
    assert len(ids) == len(set(ids)), "duplicate task id"
    out = []
    for n, (tid, level, schema, question, ref, ordered) in enumerate(TASKS):
        a = forward[schema].execute(ref).fetchall()
        b = reverse[schema].execute(ref).fetchall()
        if not a:
            raise SystemExit(f"refusing: {tid} returns no rows")
        if (a if ordered else sorted(a, key=repr)) != (b if ordered else sorted(b, key=repr)):
            raise SystemExit(f"refusing: {tid} depends on row order (a tie or an unfixed order)")
        prompt = f"{SCHEMAS[schema]}\n\n{LEADS[n % len(LEADS)].format(q=question)}"
        out.append({"id": tid, "level": level, "schema": schema, "question": question, "prompt": prompt,
                    "reference": ref, "ordered": ordered, "rows": len(a)})
    with (OUT / "tasks.jsonl").open("w") as f:
        for t in out:
            f.write(json.dumps(t) + "\n")
    with (OUT / "holdout_levels.jsonl").open("w") as f:
        for hid, level, q in HOLDOUT:
            f.write(json.dumps({"id": hid, "level": level, "prompt": f"{LIBRARY}\n\nWrite a SQL query: {q}"}) + "\n")
    counts = {lv: sum(t["level"] == lv for t in out) for lv in ("calm", "alert", "intensive")}
    print(f"wrote {len(out)} tasks {counts} and {len(HOLDOUT)} holdout texts; rows per reference: "
          + ", ".join(f"{t['id'][4:]}={t['rows']}" for t in out))


if __name__ == "__main__":
    main()
