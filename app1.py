import os
import re

import pandas as pd
import psycopg2
import streamlit as st


# =========================================================
# TITANIC INSIGHTS STUDIO
# Customized PostgreSQL + Streamlit learning application
# =========================================================

st.set_page_config(
    page_title="Titanic Insights Studio",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom visual identity (no extra packages required)
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #101b2b 0%, #14283a 55%, #172f40 100%);
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    .hero {
        padding: 1.35rem 1.6rem;
        border: 1px solid rgba(130, 190, 210, 0.25);
        border-radius: 18px;
        background: linear-gradient(110deg, rgba(18, 52, 70, .96), rgba(30, 65, 78, .82));
        margin-bottom: 1.1rem;
    }
    .hero-kicker {
        color: #8ed5dc;
        letter-spacing: .14em;
        text-transform: uppercase;
        font-size: .76rem;
        font-weight: 700;
    }
    .hero h1 {
        color: #f4f7f8;
        margin: .35rem 0 .25rem 0;
        font-size: 2.2rem;
    }
    .hero p {
        color: #c5d7df;
        margin: 0;
    }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,.055);
        border: 1px solid rgba(160,205,215,.16);
        padding: 14px 16px;
        border-radius: 14px;
    }
    div[data-testid="stTabs"] button {
        font-weight: 650;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <div class="hero-kicker">A passenger data investigation</div>
        <h1>🚢 Titanic Insights Studio</h1>
        <p>Explore passenger patterns, survival outcomes and PostgreSQL data through an interactive workspace.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_config():
    """Read credentials from Streamlit secrets, or environment variables."""
    try:
        db = st.secrets["db"]
        config = {
            "host": db["host"],
            "port": int(db.get("port", 5432)),
            "dbname": db["dbname"],
            "user": db["user"],
            "password": db["password"],
        }
        if "sslmode" in db:
            config["sslmode"] = db["sslmode"]
        return config
    except Exception:
        config = {
            "host": os.getenv("PGHOST", "localhost"),
            "port": int(os.getenv("PGPORT", "5432")),
            "dbname": os.getenv("PGDATABASE", "titanic_db"),
            "user": os.getenv("PGUSER", "titanic_app"),
            "password": os.getenv("PGPASSWORD", ""),
        }
        sslmode = os.getenv("PGSSLMODE")
        if sslmode:
            config["sslmode"] = sslmode
        return config


def get_connection():
    """Create a PostgreSQL connection using the read-only app account."""
    config = get_db_config()
    if not config.get("password"):
        raise ValueError(
            "Database password is missing. Check .streamlit/secrets.toml."
        )
    return psycopg2.connect(**config, connect_timeout=5)


def read_query(sql, params=None):
    """Execute a read-only SQL statement and return its rows as a DataFrame."""
    conn = get_connection()
    try:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            if cursor.description is None:
                raise ValueError("The SQL statement did not return a result set.")
            columns = [item[0] for item in cursor.description]
            records = cursor.fetchall()
        return pd.DataFrame(records, columns=columns)
    finally:
        conn.rollback()
        conn.close()


@st.cache_data(ttl=30)
def get_database_status():
    status = read_query(
        """
        SELECT current_database() AS database_name,
               current_schema() AS current_schema,
               version() AS postgres_version
        """
    )
    return status.iloc[0].to_dict()


try:
    db_status = get_database_status()
    st.sidebar.success(f"Connected: {db_status['database_name']}")
    st.sidebar.caption("Schema: titanic_project")
    if st.sidebar.button("Refresh database connection"):
        get_database_status.clear()
        st.rerun()
except Exception as error:
    st.error("PostgreSQL connection failed. Check your database settings.")
    with st.expander("Connection details"):
        st.code(str(error))
    st.stop()

st.sidebar.markdown("---")
st.sidebar.markdown("**Workspace guide**")
st.sidebar.caption("Dashboard · Explorer · SQL Lab · Knowledge Check")
st.sidebar.markdown("---")
st.sidebar.caption("Data source: Titanic passenger CSV imported into PostgreSQL")


# =========================================================
# SHARED DATA HELPERS
# =========================================================

@st.cache_data(ttl=60)
def get_passenger_totals():
    return read_query(
        """
        SELECT
            COUNT(*) AS total_passengers,
            COUNT(*) FILTER (WHERE survived = 1) AS survivors,
            COUNT(*) FILTER (WHERE survived = 0) AS non_survivors,
            ROUND(100.0 * COUNT(*) FILTER (WHERE survived = 1)
                  / NULLIF(COUNT(*), 0), 2) AS survival_rate
        FROM titanic_project.passengers
        """
    ).iloc[0].to_dict()


# =========================================================
# FOUR REQUIRED PROJECT SECTIONS
# =========================================================

dashboard_tab, explorer_tab, sql_tab, test_tab = st.tabs(
    ["📊 Overview", "🔎 Passenger Explorer", "⌨️ SQL Workshop", "🧠 Knowledge Check"]
)


# =========================================================
# TAB 1 — DASHBOARD / OVERVIEW
# =========================================================

with dashboard_tab:
    st.header("Voyage Overview")
    st.caption("A high-level view of passenger outcomes from the Titanic dataset.")

    totals = get_passenger_totals()
    total = int(totals["total_passengers"])
    survivors = int(totals["survivors"])
    non_survivors = int(totals["non_survivors"])
    survival_rate = float(totals["survival_rate"] or 0)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Passengers on board", f"{total:,}")
    k2.metric("Survived", f"{survivors:,}")
    k3.metric("Did not survive", f"{non_survivors:,}")
    k4.metric("Overall survival", f"{survival_rate:.2f}%")

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("Outcome by passenger class")
        class_data = read_query(
            """
            SELECT pclass,
                   COUNT(*) FILTER (WHERE survived = 1) AS survived,
                   COUNT(*) FILTER (WHERE survived = 0) AS not_survived
            FROM titanic_project.passengers
            GROUP BY pclass
            ORDER BY pclass
            """
        )
        class_data = class_data.set_index("pclass")
        class_data.index = [f"Class {x}" for x in class_data.index]
        st.bar_chart(class_data)
        st.caption("Compare survivor and non-survivor counts across the three classes.")

    with right:
        st.subheader("Survival rate by sex")
        sex_data = read_query(
            """
            SELECT sex,
                   ROUND(100.0 * AVG(survived), 2) AS survival_percentage
            FROM titanic_project.passengers
            GROUP BY sex
            ORDER BY sex
            """
        )
        st.bar_chart(
            sex_data.set_index("sex"),
            y="survival_percentage",
        )
        st.caption("Percentage of passengers who survived, grouped by sex.")

    st.divider()
    left2, right2 = st.columns(2)

    with left2:
        st.subheader("Survival by age group")
        age_data = read_query(
            """
            WITH age_summary AS (
                SELECT
                    CASE
                        WHEN age IS NULL THEN 'Unknown'
                        WHEN age < 18 THEN 'Under 18'
                        WHEN age < 40 THEN '18–39'
                        WHEN age < 60 THEN '40–59'
                        ELSE '60+'
                    END AS age_group,
                    COUNT(*) AS passengers,
                    COUNT(*) FILTER (WHERE survived = 1) AS survivors
                FROM titanic_project.passengers
                GROUP BY 1
            )
            SELECT *
            FROM age_summary
            ORDER BY CASE age_group
                WHEN 'Under 18' THEN 1
                WHEN '18–39' THEN 2
                WHEN '40–59' THEN 3
                WHEN '60+' THEN 4
                ELSE 5
            END
            """
        )
        st.bar_chart(age_data.set_index("age_group")[["passengers", "survivors"]])

    with right2:
        st.subheader("Embarkation port breakdown")
        port_data = read_query(
            """
            SELECT
                COALESCE(embarked, 'Unknown') AS embarkation_port,
                COUNT(*) AS passenger_count
            FROM titanic_project.passengers
            GROUP BY COALESCE(embarked, 'Unknown')
            ORDER BY passenger_count DESC
            """
        )
        st.bar_chart(port_data.set_index("embarkation_port"))

    st.divider()
    st.subheader("Data quality snapshot")
    missing_data = read_query(
        """
        SELECT
            COUNT(*) - COUNT(age) AS missing_age,
            COUNT(*) - COUNT(embarked) AS missing_embarked,
            COUNT(*) - COUNT(cabin) AS missing_cabin
        FROM titanic_project.passengers
        """
    ).iloc[0]
    m1, m2, m3 = st.columns(3)
    m1.metric("Missing ages", int(missing_data["missing_age"]))
    m2.metric("Missing embarkation", int(missing_data["missing_embarked"]))
    m3.metric("Missing cabin values", int(missing_data["missing_cabin"]))

    st.info(
        "Quick insight: the dataset contains 891 passenger records. "
        "Use the charts above to compare outcomes by class, sex, age group and port."
    )


# =========================================================
# TAB 2 — DATA EXPLORER
# =========================================================

with explorer_tab:
    st.header("Passenger Explorer")
    st.caption("Search and filter the passenger table. Results are read directly from PostgreSQL.")

    f1, f2 = st.columns(2)
    with f1:
        selected_classes = st.multiselect(
            "Passenger class",
            [1, 2, 3],
            default=[1, 2, 3],
        )
        selected_sexes = st.multiselect(
            "Sex",
            ["female", "male"],
            default=["female", "male"],
        )
    with f2:
        selected_outcomes = st.multiselect(
            "Survival outcome",
            [0, 1],
            default=[0, 1],
            format_func=lambda value: "Survived" if value == 1 else "Did not survive",
        )
        name_search = st.text_input(
            "Search passenger name",
            placeholder="e.g. Brown, Allen, Johnson...",
        )

    use_age_filter = st.checkbox("Filter by age range")
    age_range = st.slider(
        "Age range",
        min_value=0,
        max_value=80,
        value=(0, 80),
        disabled=not use_age_filter,
    )
    record_limit = st.slider(
        "Maximum rows to display",
        min_value=10,
        max_value=891,
        value=100,
        step=10,
    )

    if st.button("Apply filters", type="primary"):
        if not selected_classes or not selected_sexes or not selected_outcomes:
            st.warning("Select at least one option in each filter before searching.")
        else:
            sql = """
                SELECT passengerid, name, sex, age, sibsp, parch,
                       embarked, ticket, fare, cabin, pclass, survived
                FROM titanic_project.passengers
                WHERE pclass = ANY(%s)
                  AND sex = ANY(%s)
                  AND survived = ANY(%s)
                  AND name ILIKE %s
            """
            params = [
                selected_classes,
                selected_sexes,
                selected_outcomes,
                f"%{name_search}%",
            ]
            if use_age_filter:
                sql += " AND age BETWEEN %s AND %s"
                params.extend([age_range[0], age_range[1]])
            sql += " ORDER BY passengerid LIMIT %s"
            params.append(record_limit)

            try:
                result = read_query(sql, tuple(params))
                st.session_state["explorer_result"] = result
                st.success(f"{len(result)} passenger record(s) found.")
            except Exception as error:
                st.error("Could not retrieve passenger records.")
                st.code(str(error))

    if "explorer_result" in st.session_state:
        result = st.session_state["explorer_result"]
        st.dataframe(result, use_container_width=True, hide_index=True)
        st.download_button(
            "Download filtered passengers (CSV)",
            data=result.to_csv(index=False),
            file_name="titanic_passenger_search.csv",
            mime="text/csv",
        )

    with st.expander("Preview the raw staging table"):
        if st.button("Show first 20 staging records"):
            preview = read_query(
                """
                SELECT *
                FROM titanic_project.titanic_staging
                ORDER BY passengerid
                LIMIT 20
                """
            )
            st.dataframe(preview, use_container_width=True, hide_index=True)


# =========================================================
# TAB 3 — SQL WORKSHOP
# =========================================================

with sql_tab:
    st.header("SQL Workshop")
    st.caption("Choose a sample query, inspect it, and run it against the read-only database account.")
    st.warning("Only SELECT and WITH queries are intended for this learning tool.")

    sample_queries = {
        "Passenger sample": """
SELECT passengerid, name, sex, age, pclass, survived
FROM titanic_project.passengers
ORDER BY passengerid
LIMIT 20
""",
        "Passenger count by class": """
SELECT pclass, COUNT(*) AS passenger_count
FROM titanic_project.passengers
GROUP BY pclass
ORDER BY pclass
""",
        "Survival rate by sex": """
SELECT sex,
       COUNT(*) AS total_passengers,
       SUM(survived) AS survivors,
       ROUND(100.0 * AVG(survived), 2) AS survival_percentage
FROM titanic_project.passengers
GROUP BY sex
ORDER BY sex
""",
        "Average fare by class": """
SELECT pclass,
       ROUND(AVG(fare)::numeric, 2) AS average_fare
FROM titanic_project.passengers
GROUP BY pclass
ORDER BY pclass
""",
        "Missing age records": """
SELECT passengerid, name, pclass
FROM titanic_project.passengers
WHERE age IS NULL
ORDER BY passengerid
LIMIT 50
""",
        "Survival by embarkation port": """
SELECT COALESCE(embarked, 'Unknown') AS port,
       COUNT(*) AS passengers,
       SUM(survived) AS survivors
FROM titanic_project.passengers
GROUP BY COALESCE(embarked, 'Unknown')
ORDER BY passengers DESC
""",
        "Highest fare in each class": """
SELECT pclass, MAX(fare) AS highest_fare
FROM titanic_project.passengers
GROUP BY pclass
ORDER BY pclass
""",
        "Age group summary": """
SELECT
    CASE
        WHEN age IS NULL THEN 'Unknown'
        WHEN age < 18 THEN 'Under 18'
        WHEN age < 40 THEN '18–39'
        WHEN age < 60 THEN '40–59'
        ELSE '60+'
    END AS age_group,
    COUNT(*) AS passengers,
    SUM(survived) AS survivors
FROM titanic_project.passengers
GROUP BY age_group
ORDER BY age_group
""",
    }

    query_choice = st.selectbox("Select a query example", list(sample_queries.keys()))
    sql_input = st.text_area(
        "SQL statement",
        value=sample_queries[query_choice],
        height=230,
    )

    def validate_read_only_query(sql):
        cleaned = sql.strip().rstrip(";").strip()
        if not cleaned:
            return False, "Please enter a query."
        if ";" in cleaned:
            return False, "Run one SQL statement at a time."
        if not re.match(r"^(SELECT|WITH)\b", cleaned, flags=re.IGNORECASE):
            return False, "Only SELECT or WITH statements are accepted."
        blocked = [
            r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b",
            r"\bALTER\b", r"\bCREATE\b", r"\bTRUNCATE\b", r"\bGRANT\b",
            r"\bREVOKE\b", r"\bCOPY\b", r"\bCALL\b", r"\bDO\b",
            r"\bSET\b", r"\bRESET\b", r"\bPG_SLEEP\b",
        ]
        if any(re.search(pattern, cleaned, flags=re.IGNORECASE) for pattern in blocked):
            return False, "The query contains a restricted keyword."
        return True, cleaned

    if st.button("Execute SQL", type="primary"):
        is_valid, query_or_message = validate_read_only_query(sql_input)
        if not is_valid:
            st.error(query_or_message)
        else:
            try:
                query_result = read_query(query_or_message)
                st.success(f"Query completed · {len(query_result)} row(s) returned")
                st.dataframe(query_result, use_container_width=True, hide_index=True)
                st.download_button(
                    "Export query result",
                    data=query_result.to_csv(index=False),
                    file_name="titanic_sql_output.csv",
                    mime="text/csv",
                )
            except Exception as error:
                st.error("The SQL query could not be completed.")
                with st.expander("Technical details"):
                    st.code(str(error))

    with st.expander("SQL practice tasks"):
        st.markdown(
            """
            1. Display the first 20 passengers.
            2. Count passengers in each class.
            3. Calculate the average fare.
            4. Find passengers whose age is missing.
            5. Compare survival rates by sex.
            6. Count passengers by embarkation port.
            7. Find the highest fare in each class.
            8. Compare survival outcomes across age groups.
            """
        )


# =========================================================
# TAB 4 — INTERACTIVE KNOWLEDGE CHECK (15 QUESTIONS)
# =========================================================

with test_tab:
    st.header("PostgreSQL & Streamlit Knowledge Check")
    st.caption("15 multiple-choice questions. Submit all answers to see your score and explanations.")

    questions = [
        {
            "question": "1. What is a database used for?",
            "options": ["Storing and managing data", "Designing slides", "Replacing an operating system", "Compiling Python code"],
            "answer": 0,
            "explanation": "A database stores and organizes information for retrieval and management.",
        },
        {
            "question": "2. What is a PostgreSQL schema?",
            "options": ["A CSV file", "A namespace for database objects", "A Python variable", "A password"],
            "answer": 1,
            "explanation": "A schema organizes tables and other database objects.",
        },
        {
            "question": "3. Which command creates a schema?",
            "options": ["MAKE SCHEMA", "NEW SCHEMA", "CREATE SCHEMA", "INSERT SCHEMA"],
            "answer": 2,
            "explanation": "CREATE SCHEMA creates a schema in PostgreSQL.",
        },
        {
            "question": r"4. What does psql \copy do?",
            "options": ["Deletes a table", "Imports or exports data through the client", "Creates a database", "Changes a password"],
            "answer": 1,
            "explanation": r"\copy transfers file data through the psql client process.",
        },
        {
            "question": "5. What does HEADER TRUE mean?",
            "options": ["The first CSV row contains column names", "The first data row is deleted", "Every column is a primary key", "NULL values are forbidden"],
            "answer": 0,
            "explanation": "HEADER TRUE tells PostgreSQL that the CSV's first row contains column names.",
        },
        {
            "question": "6. How many original records are in this Titanic dataset?",
            "options": ["714", "889", "891", "204"],
            "answer": 2,
            "explanation": "The imported Titanic dataset contains 891 passenger records.",
        },
        {
            "question": "7. How many age values are missing?",
            "options": ["177", "204", "687", "2"],
            "answer": 0,
            "explanation": "There are 891 rows and 714 non-NULL age values, so 177 ages are missing.",
        },
        {
            "question": "8. What does a primary key enforce?",
            "options": ["All rows have the same value", "Unique, non-NULL key values", "Every column stores text", "Every passenger has an age"],
            "answer": 1,
            "explanation": "A primary key uniquely identifies each row and cannot be NULL.",
        },
        {
            "question": "9. Which SQL function counts rows?",
            "options": ["TOTAL()", "NUMBER()", "COUNT(*)", "ROWS()"],
            "answer": 2,
            "explanation": "COUNT(*) counts all rows in a query result.",
        },
        {
            "question": "10. What does GROUP BY do?",
            "options": ["Groups rows with matching values", "Deletes duplicate rows", "Creates a database", "Imports a CSV file"],
            "answer": 0,
            "explanation": "GROUP BY groups rows so aggregate calculations can be performed for each group.",
        },
        {
            "question": "11. Which SQL command retrieves data?",
            "options": ["SHOW ROWS", "SELECT", "DISPLAY", "FETCH TABLE"],
            "answer": 1,
            "explanation": "SELECT retrieves data from database tables and query results.",
        },
        {
            "question": "12. What is Streamlit used for?",
            "options": ["Building interactive Python web applications", "Replacing PostgreSQL", "Automatically creating schemas", "Replacing the operating system"],
            "answer": 0,
            "explanation": "Streamlit helps build interactive web applications using Python.",
        },
        {
            "question": "13. Which library connects Python to PostgreSQL in this project?",
            "options": ["matplotlib", "psycopg2", "turtle", "random"],
            "answer": 1,
            "explanation": "psycopg2 is the PostgreSQL adapter used by this application.",
        },
        {
            "question": "14. What does COUNT(age) count?",
            "options": ["All rows including NULL ages", "Only NULL ages", "Non-NULL age values", "Only ages equal to zero"],
            "answer": 2,
            "explanation": "COUNT(column) counts non-NULL values in that column.",
        },
        {
            "question": "15. What does survived = 1 mean?",
            "options": ["The passenger survived", "The passenger did not survive", "The age is missing", "The passenger travelled first class"],
            "answer": 0,
            "explanation": "In this dataset, 1 represents a passenger who survived.",
        },
    ]

    with st.form("custom_titanic_knowledge_check"):
        responses = []
        for index, item in enumerate(questions):
            selected = st.radio(
                item["question"],
                options=range(len(item["options"])),
                format_func=lambda option, q=item: q["options"][option],
                index=None,
                key=f"custom_quiz_{index}",
            )
            responses.append(selected)
            st.divider()
        submitted = st.form_submit_button("Submit knowledge check", type="primary")

    if submitted:
        missing = [i + 1 for i, value in enumerate(responses) if value is None]
        if missing:
            st.warning("Please answer every question. Unanswered: " + ", ".join(map(str, missing)))
        else:
            score = sum(
                1 for index, value in enumerate(responses)
                if value == questions[index]["answer"]
            )
            st.session_state["custom_quiz_result"] = {
                "score": score,
                "percentage": score / len(questions) * 100,
                "responses": responses,
            }

    if "custom_quiz_result" in st.session_state:
        result = st.session_state["custom_quiz_result"]
        score_col, percent_col, feedback_col = st.columns(3)
        score_col.metric("Correct answers", f"{result['score']} / 15")
        percent_col.metric("Score", f"{result['percentage']:.1f}%")
        feedback = (
            "Excellent work!" if result["percentage"] >= 80
            else "Good progress!" if result["percentage"] >= 60
            else "Keep practising!"
        )
        feedback_col.metric("Feedback", feedback)
        st.progress(result["percentage"] / 100)

        st.subheader("Review your answers")
        for index, item in enumerate(questions):
            chosen = result["responses"][index]
            correct = item["answer"]
            if chosen == correct:
                st.success(f"Question {index + 1}: Correct")
            else:
                st.error(f"Question {index + 1}: Incorrect")
            st.write("Your answer: " + item["options"][chosen])
            st.write("Correct answer: " + item["options"][correct])
            st.info(item["explanation"])

        if st.button("Try the knowledge check again"):
            del st.session_state["custom_quiz_result"]
            st.rerun()


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")
st.caption(
    "Titanic Insights Studio · Built with Python, Streamlit, pandas and PostgreSQL"
)
