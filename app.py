import sqlite3
from datetime import date, datetime, timedelta
from typing import Tuple

import pandas as pd
import streamlit as st

DB_PATH = "job_search_tracker.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            weekly_hours REAL NOT NULL DEFAULT 30,
            target_actions_per_day INTEGER NOT NULL DEFAULT 5
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT,
            role TEXT,
            stage TEXT DEFAULT 'Prospecting',   -- Prospecting / Applied / Screen / Interview / Offer / Closed
            notes TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_date TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,  -- Networking / Planning / Applying
            channel TEXT NOT NULL,   -- Network / Online Postings / New Connections / Search Firms
            hours REAL NOT NULL DEFAULT 0,
            jobs_applied INTEGER NOT NULL DEFAULT 0,
            followup_calls INTEGER NOT NULL DEFAULT 0,
            outreach_msgs INTEGER NOT NULL DEFAULT 0,
            new_linkedin_contacts INTEGER NOT NULL DEFAULT 0,
            staffing_firms INTEGER NOT NULL DEFAULT 0,
            networking_meetings INTEGER NOT NULL DEFAULT 0,
            networking_events INTEGER NOT NULL DEFAULT 0,
            phone_screens INTEGER NOT NULL DEFAULT 0,
            onsite_interviews INTEGER NOT NULL DEFAULT 0,
            notes TEXT
        );
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO settings (id, weekly_hours, target_actions_per_day) VALUES (1, 30, 5);"
    )
    conn.commit()


def load_settings(conn: sqlite3.Connection) -> Tuple[float, int]:
    row = conn.execute(
        "SELECT weekly_hours, target_actions_per_day FROM settings WHERE id = 1;"
    ).fetchone()
    return float(row[0]), int(row[1])


def save_settings(conn: sqlite3.Connection, weekly_hours: float, target_actions_per_day: int) -> None:
    conn.execute(
        "UPDATE settings SET weekly_hours = ?, target_actions_per_day = ? WHERE id = 1;",
        (float(weekly_hours), int(target_actions_per_day)),
    )
    conn.commit()


def add_target(
    conn: sqlite3.Connection,
    name: str,
    company: str,
    role: str,
    stage: str,
    notes: str,
    is_active: bool,
) -> None:
    conn.execute(
        """
        INSERT INTO targets (name, company, role, stage, notes, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (
            name,
            company,
            role,
            stage,
            notes,
            1 if is_active else 0,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()


def update_target(conn: sqlite3.Connection, target_id: int, stage: str, is_active: bool, notes: str) -> None:
    conn.execute(
        "UPDATE targets SET stage = ?, is_active = ?, notes = ? WHERE id = ?;",
        (stage, 1 if is_active else 0, notes, target_id),
    )
    conn.commit()


def get_targets_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT id, name, company, role, stage, is_active, created_at, notes
        FROM targets
        ORDER BY is_active DESC, created_at DESC;
        """,
        conn,
    )
    if not df.empty:
        df["is_active"] = df["is_active"].astype(int)
    return df


def add_activity(conn: sqlite3.Connection, row: dict) -> None:
    cols = ",".join(row.keys())
    placeholders = ",".join(["?"] * len(row))
    conn.execute(f"INSERT INTO activity_log ({cols}) VALUES ({placeholders});", list(row.values()))
    conn.commit()

def delete_activity(conn: sqlite3.Connection, activity_id: int) -> None:
    conn.execute("DELETE FROM activity_log WHERE id = ?;", (int(activity_id),))
    conn.commit()


def get_activity_df(conn: sqlite3.Connection, start: date, end: date) -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT *
        FROM activity_log
        WHERE activity_date >= ? AND activity_date <= ?
        ORDER BY activity_date DESC, id DESC;
        """,
        conn,
        params=(start.isoformat(), end.isoformat()),
    )
    return df


def week_bounds(d: date) -> Tuple[date, date]:
    # Monday-Sunday
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def safe_sum(df: pd.DataFrame, col: str) -> float:
    if df.empty or col not in df.columns:
        return 0.0
    return float(df[col].fillna(0).sum())


def main() -> None:
    st.set_page_config(page_title="SearchOps", layout="wide")
    st.title("SearchOps")
    st.caption("Job search tracker implementing 70/20/10 allocation, 4 channels, 5×5×7, and weekly KPI scoreboard.")

    conn = get_conn()
    init_db(conn)

    today = date.today()
    selected_day = st.sidebar.date_input("Pick a day (week view)", value=today)
    wk_start, wk_end = week_bounds(selected_day)

    weekly_hours, target_actions_per_day = load_settings(conn)

    st.sidebar.markdown("---")
    st.sidebar.subheader("Settings")
    new_weekly_hours = st.sidebar.number_input("Weekly search hours", min_value=0.0, value=float(weekly_hours), step=1.0)
    new_actions_per_day = st.sidebar.number_input("Target SMART actions/day", min_value=1, value=int(target_actions_per_day), step=1)
    if st.sidebar.button("Save settings"):
        save_settings(conn, new_weekly_hours, int(new_actions_per_day))
        weekly_hours, target_actions_per_day = load_settings(conn)
        st.sidebar.success("Saved.")

    # Derived hour targets (70/20/10)
    target_networking = weekly_hours * 0.70
    target_planning = weekly_hours * 0.20
    target_applying = weekly_hours * 0.10

    tabs = st.tabs(["Log Activity", "Targets (5×5×7)", "Dashboard", "Export / Import"])

    # --- Log Activity
    with tabs[0]:
        st.subheader("Log an activity")
        c1, c2, c3, c4 = st.columns([1, 1, 1, 2])

        with c1:
            activity_date = st.date_input("Date", value=today, key="activity_date")
            hours = st.number_input("Hours", min_value=0.0, value=0.5, step=0.25)

        with c2:
            category = st.selectbox("Category (70/20/10)", ["Networking", "Planning", "Applying"])
            channel = st.selectbox("Channel (4 channels)", ["Network", "Online Postings", "New Connections", "Search Firms"])

        with c3:
            title = st.text_input("Title", value="")

        with c4:
            notes = st.text_area("Notes (optional)", value="", height=80)

        st.markdown("**Progress counts (optional)**")
        k1, k2, k3, k4, k5 = st.columns(5)
        jobs_applied = k1.number_input("# jobs applied", min_value=0, value=0, step=1)
        followup_calls = k2.number_input("# follow-up calls", min_value=0, value=0, step=1)
        outreach_msgs = k3.number_input("# outreach calls/emails", min_value=0, value=0, step=1)
        new_linkedin_contacts = k4.number_input("# new LinkedIn contacts", min_value=0, value=0, step=1)
        staffing_firms = k5.number_input("# staffing firms", min_value=0, value=0, step=1)

        k6, k7, k8, k9, k10 = st.columns(5)
        networking_meetings = k6.number_input("# networking meetings", min_value=0, value=0, step=1)
        networking_events = k7.number_input("# networking/career events", min_value=0, value=0, step=1)
        phone_screens = k8.number_input("# phone screens", min_value=0, value=0, step=1)
        onsite_interviews = k9.number_input("# onsite interviews", min_value=0, value=0, step=1)

        if st.button("Add activity"):
            if not title.strip():
                st.error("Please enter a Title.")
            else:
                add_activity(
                    conn,
                    {
                        "activity_date": activity_date.isoformat(),
                        "title": title.strip(),
                        "category": category,
                        "channel": channel,
                        "hours": float(hours),
                        "jobs_applied": int(jobs_applied),
                        "followup_calls": int(followup_calls),
                        "outreach_msgs": int(outreach_msgs),
                        "new_linkedin_contacts": int(new_linkedin_contacts),
                        "staffing_firms": int(staffing_firms),
                        "networking_meetings": int(networking_meetings),
                        "networking_events": int(networking_events),
                        "phone_screens": int(phone_screens),
                        "onsite_interviews": int(onsite_interviews),
                        "notes": notes.strip(),
                    },
                )
                st.success("Activity added.")

        st.markdown("---")
        st.subheader(f"This week’s log ({wk_start} → {wk_end})")
        df_week = get_activity_df(conn, wk_start, wk_end)
        if df_week.empty:
            st.info("No activities logged yet for this week.")
        else:
            st.dataframe(
                df_week[
                    [
                        "id",
                        "activity_date",
                        "title",
                        "category",
                        "channel",
                        "hours",
                        "jobs_applied",
                        "followup_calls",
                        "outreach_msgs",
                        "new_linkedin_contacts",
                        "networking_meetings",
                        "phone_screens",
                        "onsite_interviews",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("### Delete an activity")
        if not df_week.empty:
            delete_id = st.number_input("Activity ID to delete", min_value=1, step=1)
            if st.button("Delete selected activity"):
                delete_activity(conn, int(delete_id))
                st.success(f"Deleted activity id={delete_id}. Refreshing list...")
                st.rerun()

    # --- Targets
    with tabs[1]:
        st.subheader("Targets / Opportunities (aim to maintain 7 active)")
        left, right = st.columns([1, 2])

        with left:
            st.markdown("**Add a target**")
            t_name = st.text_input("Target name (e.g., Company / Opportunity)", key="t_name")
            t_company = st.text_input("Company", key="t_company")
            t_role = st.text_input("Role", key="t_role")
            t_stage = st.selectbox("Stage", ["Prospecting", "Applied", "Screen", "Interview", "Offer", "Closed"], key="t_stage")
            t_active = st.checkbox("Active", value=True, key="t_active")
            t_notes = st.text_area("Notes", key="t_notes", height=80)

            if st.button("Add target"):
                if not t_name.strip():
                    st.error("Please enter a Target name.")
                else:
                    add_target(conn, t_name.strip(), t_company.strip(), t_role.strip(), t_stage, t_notes.strip(), t_active)
                    st.success("Target added.")

        with right:
            df_targets = get_targets_df(conn)
            if df_targets.empty:
                st.info("No targets yet. Add a few to reach 7 active opportunities.")
            else:
                active_count = int((df_targets["is_active"] == 1).sum())
                st.metric("Active targets", active_count, delta=f"{active_count - 7} vs goal of 7")

                st.dataframe(
                    df_targets[["id", "name", "company", "role", "stage", "is_active", "created_at"]],
                    use_container_width=True,
                    hide_index=True,
                )

                st.markdown("**Update a target**")
                target_ids = df_targets["id"].tolist()
                chosen_id = st.selectbox("Target ID", target_ids)
                row = df_targets[df_targets["id"] == chosen_id].iloc[0]
                stages = ["Prospecting", "Applied", "Screen", "Interview", "Offer", "Closed"]
                new_stage = st.selectbox("New stage", stages, index=stages.index(row["stage"]))
                new_active = st.checkbox("Active", value=bool(row["is_active"]))
                new_notes = st.text_area("Notes", value=row.get("notes", "") or "", height=80)

                if st.button("Save target update"):
                    update_target(conn, int(chosen_id), new_stage, bool(new_active), new_notes.strip())
                    st.success("Updated target. (Refresh tab if needed.)")

    # --- Dashboard
    with tabs[2]:
        st.subheader(f"Dashboard ({wk_start} → {wk_end})")
        df_week = get_activity_df(conn, wk_start, wk_end)

        if df_week.empty:
            st.info("Log some activity to see your dashboard.")
        else:
            hours_by_cat = (
                df_week.groupby("category")["hours"]
                .sum()
                .reindex(["Networking", "Planning", "Applying"])
                .fillna(0.0)
            )
            total_hours = float(hours_by_cat.sum())

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total hours (week)", f"{total_hours:.2f}")
            m2.metric("Networking hours", f"{hours_by_cat['Networking']:.2f}", delta=f"{hours_by_cat['Networking'] - target_networking:.2f} vs target")
            m3.metric("Planning hours", f"{hours_by_cat['Planning']:.2f}", delta=f"{hours_by_cat['Planning'] - target_planning:.2f} vs target")
            m4.metric("Applying hours", f"{hours_by_cat['Applying']:.2f}", delta=f"{hours_by_cat['Applying'] - target_applying:.2f} vs target")

            st.markdown("**70/20/10 target hours**")
            st.write(
                {
                    "Weekly hours": weekly_hours,
                    "Networking (70%) target": round(target_networking, 2),
                    "Planning (20%) target": round(target_planning, 2),
                    "Applying (10%) target": round(target_applying, 2),
                }
            )

            st.markdown("---")
            st.markdown("**5×5 execution check**")
            df_week2 = df_week.copy()
            df_week2["activity_date"] = pd.to_datetime(df_week2["activity_date"]).dt.date
            actions_by_day = df_week2.groupby("activity_date")["id"].count()

            days_with_actions = int((actions_by_day > 0).sum())
            days_meeting_5 = int((actions_by_day >= target_actions_per_day).sum())

            a1, a2, a3 = st.columns(3)
            a1.metric("Days with activity (goal: 5)", days_with_actions, delta=days_with_actions - 5)
            a2.metric(f"Days ≥ {target_actions_per_day} actions", days_meeting_5)

            df_targets = get_targets_df(conn)
            active_targets = int((df_targets["is_active"] == 1).sum()) if not df_targets.empty else 0
            a3.metric("Active targets (goal: 7)", active_targets, delta=active_targets - 7)

            st.markdown("---")
            st.markdown("**Progress scoreboard (weekly totals)**")
            kpis = {
                "Hours spent on search": round(total_hours, 2),
                "Jobs applied": int(safe_sum(df_week, "jobs_applied")),
                "Follow-up calls": int(safe_sum(df_week, "followup_calls")),
                "Outreach calls/emails": int(safe_sum(df_week, "outreach_msgs")),
                "New LinkedIn contacts": int(safe_sum(df_week, "new_linkedin_contacts")),
                "Staffing firms": int(safe_sum(df_week, "staffing_firms")),
                "Networking meetings": int(safe_sum(df_week, "networking_meetings")),
                "Networking/career events": int(safe_sum(df_week, "networking_events")),
                "Phone screens": int(safe_sum(df_week, "phone_screens")),
                "Onsite interviews": int(safe_sum(df_week, "onsite_interviews")),
            }
            st.dataframe(pd.DataFrame([kpis]).T.rename(columns={0: "Total"}), use_container_width=True)

            st.markdown("---")
            st.markdown("**Channel mix (hours by channel)**")
            ch = df_week.groupby("channel")["hours"].sum().sort_values(ascending=False)
            st.dataframe(ch.reset_index().rename(columns={"hours": "hours"}), use_container_width=True, hide_index=True)

    # --- Export / Import
    with tabs[3]:
        st.subheader("Export / Import")
        df_targets = get_targets_df(conn)
        df_week = get_activity_df(conn, wk_start, wk_end)

        colA, colB = st.columns(2)
        with colA:
            st.markdown("**Export this week’s activities (CSV)**")
            if df_week.empty:
                st.info("No data to export for this week.")
            else:
                csv = df_week.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download activities CSV",
                    data=csv,
                    file_name=f"activities_{wk_start}_{wk_end}.csv",
                    mime="text/csv",
                )

        with colB:
            st.markdown("**Export targets/opportunities (CSV)**")
            if df_targets.empty:
                st.info("No targets to export.")
            else:
                csv2 = df_targets.to_csv(index=False).encode("utf-8")
                st.download_button("Download targets CSV", data=csv2, file_name="targets.csv", mime="text/csv")

        st.markdown("---")
        st.subheader("Import activities (append)")
        uploaded = st.file_uploader("Upload activities CSV (exported from this app)", type=["csv"])
        if uploaded is not None:
            try:
                df_in = pd.read_csv(uploaded)
                required_cols = {
                    "activity_date","title","category","channel","hours",
                    "jobs_applied","followup_calls","outreach_msgs","new_linkedin_contacts","staffing_firms",
                    "networking_meetings","networking_events","phone_screens","onsite_interviews","notes"
                }
                missing = required_cols - set(df_in.columns)
                if missing:
                    st.error(f"CSV missing required columns: {sorted(missing)}")
                else:
                    st.dataframe(df_in.head(20), use_container_width=True)
                    if st.button("Import (append)"):
                        for _, r in df_in.iterrows():
                            add_activity(conn, {k: r[k] for k in required_cols})
                        st.success("Imported activities.")
            except Exception as e:
                st.error(f"Failed to read CSV: {e}")


if __name__ == "__main__":
    main()
