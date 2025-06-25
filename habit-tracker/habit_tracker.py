import streamlit as st
import sqlite3
from datetime import date
import pandas as pd
import matplotlib.pyplot as plt
import os

# --- Habit List ---
HABITS = [
    "💡 Brainstorming",
    "💻 Coding",
    "🏃‍♂️ Exercise/Walking",
    "📓 Journaling",
    "💧 Hydration",
    "🧘 Meditation",
    "🗣️ Networking (in-person/online)",
    "📝 Posting",
    "📚 Reading",
    "✍️ Writing/Planning"
]

def get_connection():
    return sqlite3.connect("habits.db", check_same_thread=False)

def get_existing_columns():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='habits'")
        if not c.fetchone():
            return None
        c.execute("PRAGMA table_info(habits)")
        return [row[1] for row in c.fetchall()]

def create_table(force=False):
    habit_columns = ", ".join([f'[{h.lower().replace(" ", "_")}] INTEGER' for h in HABITS])
    with get_connection() as conn:
        c = conn.cursor()
        if force:
            c.execute("DROP TABLE IF EXISTS habits")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                {habit_columns},
                notes TEXT
            )
        """)
        conn.commit()

# --- Ensure DB schema matches habits ---
existing_cols = get_existing_columns()
expected_cols = ['id', 'date'] + [h.lower().replace(' ', '_') for h in HABITS] + ['notes']
if existing_cols is None or set(existing_cols) != set(expected_cols):
    create_table(force=True)

# --- Streamlit UI ---
st.sidebar.markdown("---")
dashboard = st.sidebar.selectbox(
    "Choose Dashboard",
    ("Daily Tracker", "Statistics")
)

if dashboard == "Daily Tracker":
    st.title("🗓️ Habit Tracker Dashboard")
    st.sidebar.header("Track your daily habits!")
    selected_date = st.sidebar.date_input("Select Date", value=date.today())

    def get_entry_for_date(selected_date):
        with get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM habits WHERE date = ?", (str(selected_date),))
            return c.fetchone()

    entry = get_entry_for_date(selected_date)

    st.subheader(f"Habits for {selected_date}")
    habit_states = {}

    col1, col2 = st.columns([2, 2])
    with col1:
        if entry:
            for i, habit in enumerate(HABITS):
                habit_states[habit] = st.checkbox(habit, value=bool(entry[i+2]))
            notes = st.text_area("Notes", value=entry[-1] or "")
        else:
            for habit in HABITS:
                habit_states[habit] = st.checkbox(habit, value=False)
            notes = st.text_area("Notes")

    completed = sum(habit_states.values())
    percent = int((completed / len(HABITS)) * 100)

    with col2:
        if completed == len(HABITS):
            st.markdown("""
                <div style='display: flex; flex-direction: column; align-items: center; justify-content: center; margin: 30px 0;'>
                    <h1 style='color: #4CAF50; font-size: 2.2em; text-align: center;'>Congratulations! 🎉<br>You completed all your habits today!</h1>
                </div>
            """, unsafe_allow_html=True)
            st.balloons()

    st.progress(percent / 100, text=f"Today's Progress: {percent}% ({completed}/{len(HABITS)})")

    if st.button("Save/Update"):
        with get_connection() as conn:
            c = conn.cursor()
            values = [str(selected_date)] + [int(habit_states[h]) for h in HABITS] + [notes]
            if entry:
                set_clause = ', '.join([f"[{h.lower().replace(' ', '_')}] = ?" for h in HABITS])
                c.execute(f"UPDATE habits SET {set_clause}, notes = ? WHERE date = ?", values[1:] + [str(selected_date)])
            else:
                columns = ', '.join(['date'] + [f"[{h.lower().replace(' ', '_')}]" for h in HABITS] + ['notes'])
                placeholders = ', '.join(['?'] * (len(HABITS) + 2))
                c.execute(f"INSERT INTO habits ({columns}) VALUES ({placeholders})", values)
            conn.commit()
        st.success("Saved!")

    st.subheader("Habit History")
    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM habits ORDER BY date DESC", conn)
        if not df.empty:
            df_display = df[['date'] + [h.lower().replace(' ', '_') for h in HABITS] + ['notes']]
            df_display.columns = ['Date'] + HABITS + ['Notes']
            st.dataframe(df_display)
        else:
            st.info("No habit data yet. Start tracking!")

elif dashboard == "Statistics":
    st.title("📊 Habit Statistics Dashboard")
    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM habits ORDER BY date ASC", conn)
    if df.empty:
        st.info("No data to show statistics yet.")
    else:
        st.subheader("Total Completions per Habit")
        habit_cols = [h.lower().replace(' ', '_') for h in HABITS]
        total_completions = df[habit_cols].sum()
        st.bar_chart(total_completions)

        st.subheader("Total Habits Completed Per Day")
        df['total_completed'] = df[habit_cols].sum(axis=1)
        st.line_chart(df.set_index('date')['total_completed'])

        st.subheader("Daily Progress (Stacked Column Chart)")
        stacked_df = df[['date'] + habit_cols].copy()
        stacked_df['date'] = pd.to_datetime(stacked_df['date'])
        stacked_df = stacked_df.set_index('date')
        st.bar_chart(stacked_df)

        st.subheader("Best Streak (All Habits Done)")
        df['all_done'] = df[habit_cols].sum(axis=1) == len(HABITS)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        streak = 0
        best_streak = 0
        last_date = None
        for _, row in df.iterrows():
            if row['all_done']:
                if last_date is not None and (row['date'] - last_date).days == 1:
                    streak += 1
                else:
                    streak = 1
                best_streak = max(best_streak, streak)
            else:
                streak = 0
            last_date = row['date']
        st.metric("Longest Streak (days)", best_streak) 