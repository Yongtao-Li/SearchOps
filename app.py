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
        """
        CREATE TABLE IF NOT EXISTS networking_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT,
            title TEXT,
            relationship_type TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'New',
            tags TEXT,
            notes TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS networking_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id INTEGER NOT NULL,
            interaction_date TEXT NOT NULL,
            mode TEXT NOT NULL,
            interaction_type TEXT NOT NULL,
            outcome TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL DEFAULT 0,
            summary TEXT,
            next_step TEXT,
            follow_up_date TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (contact_id) REFERENCES networking_contacts(id) ON DELETE CASCADE
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS networking_scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            char_limit INTEGER,
            is_default INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO settings (id, weekly_hours, target_actions_per_day) VALUES (1, 30, 5);"
    )
    conn.commit()
    seed_networking_scripts(conn)


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


def seed_networking_scripts(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(1) FROM networking_scripts;").fetchone()[0]
    if int(existing) > 0:
        return
    seeds = [
        (
            "Ask - Unknown",
            "Intro + 20-min ask",
            "Hi [Name], I came across your profile while researching [Company/Topic]. I appreciate your work on [specific]. I am exploring [goal] and would value 2-3 quick questions about your experience. Would you be open to a 15-20 minute call next week?",
            None,
            1,
        ),
        (
            "Ask - Warm Referral",
            "Referral ask",
            "Hi [Name], [Referrer] suggested I reach out. I am exploring [industry/role] and would appreciate your perspective on [Company/Topic]. If you are open to it, could we connect for 15-20 minutes? Happy to work around your schedule.",
            None,
            1,
        ),
        (
            "Ask - Recent Contact",
            "Event follow-up ask",
            "Hi [Name], it was great meeting you at [Event]. I enjoyed our conversation about [topic]. If you are open to it, I would love to ask 2-3 questions about your role at [Company]. Would you be available for a brief coffee or call next week?",
            None,
            1,
        ),
        (
            "LinkedIn Invite",
            "Connection request (300 chars)",
            "Hi [Name], enjoyed your insights on [topic] and noticed we share [commonality]. I would love to connect and stay in touch. Thanks, [Your Name]",
            300,
            1,
        ),
        (
            "Follow-up",
            "Thank you + recap",
            "Hi [Name], thank you again for your time today. I appreciated your advice on [topic]. As promised, I am sending [resource]. If helpful, I can keep you posted as I progress. Thanks again.",
            None,
            1,
        ),
    ]
    conn.executemany(
        "INSERT INTO networking_scripts (category, title, body, char_limit, is_default) VALUES (?, ?, ?, ?, ?);",
        seeds,
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


def add_contact(conn: sqlite3.Connection, row: dict) -> None:
    cols = ",".join(row.keys())
    placeholders = ",".join(["?"] * len(row))
    conn.execute(f"INSERT INTO networking_contacts ({cols}) VALUES ({placeholders});", list(row.values()))
    conn.commit()


def update_contact(conn: sqlite3.Connection, contact_id: int, row: dict) -> None:
    assignments = ",".join([f"{k} = ?" for k in row.keys()])
    conn.execute(
        f"UPDATE networking_contacts SET {assignments} WHERE id = ?;",
        list(row.values()) + [int(contact_id)],
    )
    conn.commit()


def get_contacts_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT id, name, company, title, relationship_type, source, status, tags, notes, created_at
        FROM networking_contacts
        ORDER BY status ASC, created_at DESC;
        """,
        conn,
    )
    return df


def get_contact_row(conn: sqlite3.Connection, contact_id: int) -> pd.Series | None:
    df = pd.read_sql_query(
        """
        SELECT id, name, company, title, relationship_type, source, status, tags, notes
        FROM networking_contacts
        WHERE id = ?;
        """,
        conn,
        params=(int(contact_id),),
    )
    if df.empty:
        return None
    return df.iloc[0]


def add_interaction(conn: sqlite3.Connection, row: dict) -> None:
    cols = ",".join(row.keys())
    placeholders = ",".join(["?"] * len(row))
    conn.execute(f"INSERT INTO networking_interactions ({cols}) VALUES ({placeholders});", list(row.values()))
    conn.commit()


def update_interaction(conn: sqlite3.Connection, interaction_id: int, row: dict) -> None:
    assignments = ",".join([f"{k} = ?" for k in row.keys()])
    conn.execute(
        f"UPDATE networking_interactions SET {assignments} WHERE id = ?;",
        list(row.values()) + [int(interaction_id)],
    )
    conn.commit()


def get_interactions_df(
    conn: sqlite3.Connection,
    start: date | None = None,
    end: date | None = None,
    contact_id: int | None = None,
) -> pd.DataFrame:
    where = []
    params = []
    if start is not None and end is not None:
        where.append("interaction_date >= ? AND interaction_date <= ?")
        params.extend([start.isoformat(), end.isoformat()])
    if contact_id is not None:
        where.append("contact_id = ?")
        params.append(int(contact_id))
    clause = " WHERE " + " AND ".join(where) if where else ""
    df = pd.read_sql_query(
        f"""
        SELECT i.id, i.contact_id, c.name, c.company, i.interaction_date, i.mode,
               i.interaction_type, i.outcome, i.duration_minutes, i.follow_up_date, i.next_step
        FROM networking_interactions i
        JOIN networking_contacts c ON c.id = i.contact_id
        {clause}
        ORDER BY i.interaction_date DESC, i.id DESC;
        """,
        conn,
        params=params,
    )
    return df


def get_interaction_row(conn: sqlite3.Connection, interaction_id: int) -> pd.Series | None:
    df = pd.read_sql_query(
        """
        SELECT id, contact_id, interaction_date, mode, interaction_type, outcome,
               duration_minutes, summary, next_step, follow_up_date
        FROM networking_interactions
        WHERE id = ?;
        """,
        conn,
        params=(int(interaction_id),),
    )
    if df.empty:
        return None
    return df.iloc[0]


def get_followups_df(conn: sqlite3.Connection, on_or_before: date) -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT i.id, i.contact_id, c.name, c.company, i.interaction_date,
               i.follow_up_date, i.next_step, i.outcome
        FROM networking_interactions i
        JOIN networking_contacts c ON c.id = i.contact_id
        WHERE i.follow_up_date IS NOT NULL AND i.follow_up_date <= ?
        ORDER BY i.follow_up_date ASC, i.id DESC;
        """,
        conn,
        params=(on_or_before.isoformat(),),
    )
    return df


def get_scripts_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(
        "SELECT id, category, title, body, char_limit FROM networking_scripts ORDER BY category, title;",
        conn,
    )
    return df

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

    tabs = st.tabs(["Log Activity", "Targets (5×5×7)", "Dashboard", "Networking", "Export / Import"])

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
            st.markdown("**Networking CRM (weekly)**")
            df_net_week = get_interactions_df(conn, wk_start, wk_end)
            if df_net_week.empty:
                st.info("No networking interactions logged this week.")
            else:
                outreach_count = int((df_net_week["interaction_type"] == "Outreach").sum())
                meetings_count = int((df_net_week["interaction_type"] == "Meeting").sum())
                referrals = int((df_net_week["interaction_type"] == "Referral Received").sum())
                n1, n2, n3 = st.columns(3)
                n1.metric("Outreach", outreach_count)
                n2.metric("Meetings", meetings_count)
                n3.metric("Referrals received", referrals)

            st.markdown("---")
            st.markdown("**Channel mix (hours by channel)**")
            ch = df_week.groupby("channel")["hours"].sum().sort_values(ascending=False)
            st.dataframe(ch.reset_index().rename(columns={"hours": "hours"}), use_container_width=True, hide_index=True)

    # --- Networking
    with tabs[3]:
        st.subheader("Networking CRM")
        contact_types = [
            "Referrer",
            "Target Company",
            "Alumni",
            "Recruiter",
            "Hiring Manager",
            "Peer",
            "Mentor",
            "Event Organizer",
            "Consultant",
            "Reporter",
            "Other",
        ]
        sources = ["LinkedIn", "Event", "Referral", "Email", "Cold Outreach", "Internal", "Other"]
        statuses = ["New", "Active", "Dormant", "Closed"]
        modes = ["Email", "LinkedIn", "Phone", "Video", "In-person", "Chat"]
        interaction_types = [
            "Outreach",
            "Meeting",
            "Follow-up",
            "Referral Request",
            "Referral Received",
            "Thank You",
            "Other",
        ]
        outcomes = ["No Response", "Replied", "Meeting Scheduled", "Met", "Referral Made", "Declined", "Other"]

        st.markdown("**Add contact**")
        add_left, add_right = st.columns(2)
        with add_left:
            nc_name = st.text_input("Name", key="nc_name")
            nc_company = st.text_input("Company", key="nc_company")
            nc_type = st.selectbox("Relationship type", contact_types, key="nc_type")
            nc_status = st.selectbox("Status", statuses, index=0, key="nc_status")
        with add_right:
            nc_title = st.text_input("Title", key="nc_title")
            nc_source = st.selectbox("Source", sources, key="nc_source")
            nc_tags = st.text_input("Tags (comma-separated)", key="nc_tags")
        nc_notes = st.text_area("Notes", key="nc_notes", height=80)
        if st.button("Add contact"):
            if not nc_name.strip():
                st.error("Please enter a contact name.")
            else:
                add_contact(
                    conn,
                    {
                        "name": nc_name.strip(),
                        "company": nc_company.strip(),
                        "title": nc_title.strip(),
                        "relationship_type": nc_type,
                        "source": nc_source,
                        "status": nc_status,
                        "tags": nc_tags.strip(),
                        "notes": nc_notes.strip(),
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                    },
                )
                st.success("Contact added.")

        df_contacts = get_contacts_df(conn)

        st.markdown("---")
        st.markdown("**Review contacts**")
        if df_contacts.empty:
            st.info("No contacts yet. Add a few to start tracking.")
            filtered_contacts = df_contacts
        else:
            f1, f2, f3, f4 = st.columns([1, 1, 1, 2])
            with f1:
                status_filter = st.selectbox("Status", ["All"] + statuses, key="nc_filter_status")
            with f2:
                type_filter = st.selectbox("Type", ["All"] + contact_types, key="nc_filter_type")
            with f3:
                source_filter = st.selectbox("Source", ["All"] + sources, key="nc_filter_source")
            with f4:
                search_filter = st.text_input("Search name/company", key="nc_filter_search")

            filtered_contacts = df_contacts.copy()
            if status_filter != "All":
                filtered_contacts = filtered_contacts[filtered_contacts["status"] == status_filter]
            if type_filter != "All":
                filtered_contacts = filtered_contacts[filtered_contacts["relationship_type"] == type_filter]
            if source_filter != "All":
                filtered_contacts = filtered_contacts[filtered_contacts["source"] == source_filter]
            if search_filter.strip():
                pattern = search_filter.strip().lower()
                filtered_contacts = filtered_contacts[
                    filtered_contacts.apply(
                        lambda r: pattern in (r["name"] or "").lower()
                        or pattern in (r["company"] or "").lower(),
                        axis=1,
                    )
                ]

            if filtered_contacts.empty:
                st.info("No contacts match these filters.")
            else:
                st.dataframe(
                    filtered_contacts[
                        ["id", "name", "company", "title", "relationship_type", "source", "status"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

        st.markdown("---")
        st.markdown("**Update contact**")
        if df_contacts.empty:
            st.info("No contacts to update yet.")
        else:
            update_contacts = filtered_contacts if not filtered_contacts.empty else df_contacts
            contact_ids = update_contacts["id"].tolist()
            chosen_contact = st.selectbox("Contact ID", contact_ids, key="nc_update_contact_id")
            crow = get_contact_row(conn, int(chosen_contact))
            if crow is None:
                st.error("Contact not found.")
            else:
                if st.session_state.get("nc_update_last_id") != chosen_contact:
                    st.session_state["nc_update_last_id"] = chosen_contact
                    st.session_state["nc_update_name"] = crow["name"]
                    st.session_state["nc_update_company"] = crow.get("company", "") or ""
                    st.session_state["nc_update_title"] = crow.get("title", "") or ""
                    st.session_state["nc_update_type"] = crow["relationship_type"]
                    st.session_state["nc_update_source"] = crow["source"]
                    st.session_state["nc_update_status"] = crow["status"]
                    st.session_state["nc_update_tags"] = crow.get("tags", "") or ""
                    st.session_state["nc_update_notes"] = crow.get("notes", "") or ""

                update_left, update_right = st.columns(2)
                with update_left:
                    uc_name = st.text_input("Name", key="nc_update_name")
                    uc_company = st.text_input("Company", key="nc_update_company")
                    uc_type = st.selectbox(
                        "Relationship type",
                        contact_types,
                        index=contact_types.index(st.session_state["nc_update_type"]),
                        key="nc_update_type",
                    )
                    uc_status = st.selectbox(
                        "Status",
                        statuses,
                        index=statuses.index(st.session_state["nc_update_status"]),
                        key="nc_update_status",
                    )
                with update_right:
                    uc_title = st.text_input("Title", key="nc_update_title")
                    uc_source = st.selectbox(
                        "Source",
                        sources,
                        index=sources.index(st.session_state["nc_update_source"]),
                        key="nc_update_source",
                    )
                    uc_tags = st.text_input("Tags (comma-separated)", key="nc_update_tags")
                uc_notes = st.text_area("Notes", key="nc_update_notes", height=80)

                if st.button("Save contact update"):
                    if not uc_name.strip():
                        st.error("Please enter a contact name.")
                    else:
                        update_contact(
                            conn,
                            int(chosen_contact),
                            {
                                "name": uc_name.strip(),
                                "company": uc_company.strip(),
                                "title": uc_title.strip(),
                                "relationship_type": uc_type,
                                "source": uc_source,
                                "status": uc_status,
                                "tags": uc_tags.strip(),
                                "notes": uc_notes.strip(),
                            },
                        )
                        st.success("Contact updated.")

        contact_label = []
        contact_map = {}
        if not df_contacts.empty:
            contact_label = df_contacts.apply(
                lambda r: f"{r['name']} ({r['company'] or 'N/A'})", axis=1
            ).tolist()
            contact_map = dict(zip(contact_label, df_contacts["id"].tolist()))

        st.markdown("---")
        st.markdown("**Log interaction**")
        if df_contacts.empty:
            st.info("Add a contact before logging interactions.")
        else:
            ic1, ic2, ic3, ic4 = st.columns([1, 1, 1, 2])
            with ic1:
                interaction_date = st.date_input("Date", value=today, key="ni_date")
                duration_minutes = st.number_input("Duration (minutes)", min_value=0, value=15, step=5)
            with ic2:
                chosen_label = st.selectbox("Contact", contact_label)
                mode = st.selectbox("Mode", modes)
            with ic3:
                interaction_type = st.selectbox("Type", interaction_types)
                outcome = st.selectbox("Outcome", outcomes)
            with ic4:
                summary = st.text_area("Summary", height=80)
                next_step = st.text_input("Next step")
                follow_up_date = st.date_input("Follow-up date", value=today, key="ni_followup")
                no_followup = st.checkbox("No follow-up needed", value=False)

            if st.button("Add interaction"):
                add_interaction(
                    conn,
                    {
                        "contact_id": int(contact_map[chosen_label]),
                        "interaction_date": interaction_date.isoformat(),
                        "mode": mode,
                        "interaction_type": interaction_type,
                        "outcome": outcome,
                        "duration_minutes": int(duration_minutes),
                        "summary": summary.strip(),
                        "next_step": next_step.strip(),
                        "follow_up_date": None if no_followup else follow_up_date.isoformat(),
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                    },
                )
                st.success("Interaction logged.")

        st.markdown("---")
        st.markdown("**Review/update interactions**")
        if df_contacts.empty:
            st.info("Add a contact before reviewing interactions.")
        else:
            r1, r2, r3 = st.columns([1, 1, 2])
            with r1:
                review_start = st.date_input("From", value=wk_start, key="ni_review_start")
            with r2:
                review_end = st.date_input("To", value=wk_end, key="ni_review_end")
            with r3:
                contact_filter = st.selectbox(
                    "Filter by contact (optional)",
                    ["All"] + contact_label,
                    key="ni_contact_filter",
                )

            filter_contact_id = None
            if contact_filter != "All":
                filter_contact_id = int(contact_map[contact_filter])

            df_interactions = get_interactions_df(conn, review_start, review_end, filter_contact_id)
            if df_interactions.empty:
                st.info("No interactions found for this range.")
            else:
                st.dataframe(
                    df_interactions[
                        [
                            "id",
                            "name",
                            "company",
                            "interaction_date",
                            "mode",
                            "interaction_type",
                            "outcome",
                            "duration_minutes",
                            "follow_up_date",
                            "next_step",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

                st.markdown("**Update an interaction**")
                interaction_ids = df_interactions["id"].tolist()
                chosen_interaction = st.selectbox("Interaction ID", interaction_ids, key="ni_update_interaction_id")
                irow = get_interaction_row(conn, int(chosen_interaction))
                if irow is None:
                    st.error("Interaction not found.")
                else:
                    has_followup = irow.get("follow_up_date") is not None
                    followup_value = (
                        pd.to_datetime(irow["follow_up_date"]).date() if has_followup else today
                    )
                    contact_id = int(irow["contact_id"])
                    contact_index = df_contacts.index[df_contacts["id"] == contact_id][0]
                    update_contact_label = contact_label[contact_index]

                    if st.session_state.get("ni_update_last_id") != chosen_interaction:
                        st.session_state["ni_update_last_id"] = chosen_interaction
                        st.session_state["ni_update_date"] = pd.to_datetime(irow["interaction_date"]).date()
                        st.session_state["ni_update_duration"] = int(irow["duration_minutes"])
                        st.session_state["ni_update_contact"] = update_contact_label
                        st.session_state["ni_update_mode"] = irow["mode"]
                        st.session_state["ni_update_type"] = irow["interaction_type"]
                        st.session_state["ni_update_outcome"] = irow["outcome"]
                        st.session_state["ni_update_summary"] = irow.get("summary", "") or ""
                        st.session_state["ni_update_next_step"] = irow.get("next_step", "") or ""
                        st.session_state["ni_update_followup"] = followup_value
                        st.session_state["ni_update_no_followup"] = not has_followup

                    u1, u2, u3, u4 = st.columns([1, 1, 1, 2])
                    with u1:
                        ui_date = st.date_input(
                            "Date",
                            key="ni_update_date",
                        )
                        ui_duration = st.number_input(
                            "Duration (minutes)",
                            min_value=0,
                            step=5,
                            key="ni_update_duration",
                        )
                    with u2:
                        update_contact_choice = st.selectbox(
                            "Contact",
                            contact_label,
                            index=contact_label.index(update_contact_label),
                            key="ni_update_contact",
                        )
                        ui_mode = st.selectbox(
                            "Mode",
                            modes,
                            index=modes.index(st.session_state["ni_update_mode"]),
                            key="ni_update_mode",
                        )
                    with u3:
                        ui_type = st.selectbox(
                            "Type",
                            interaction_types,
                            index=interaction_types.index(st.session_state["ni_update_type"]),
                            key="ni_update_type",
                        )
                        ui_outcome = st.selectbox(
                            "Outcome",
                            outcomes,
                            index=outcomes.index(st.session_state["ni_update_outcome"]),
                            key="ni_update_outcome",
                        )
                    with u4:
                        ui_summary = st.text_area(
                            "Summary",
                            height=80,
                            key="ni_update_summary",
                        )
                        ui_next_step = st.text_input(
                            "Next step",
                            key="ni_update_next_step",
                        )
                        ui_followup_date = st.date_input(
                            "Follow-up date",
                            key="ni_update_followup",
                        )
                        ui_no_followup = st.checkbox(
                            "No follow-up needed",
                            key="ni_update_no_followup",
                        )

                    if st.button("Save interaction update"):
                        update_interaction(
                            conn,
                            int(chosen_interaction),
                            {
                                "contact_id": int(contact_map[update_contact_choice]),
                                "interaction_date": ui_date.isoformat(),
                                "mode": ui_mode,
                                "interaction_type": ui_type,
                                "outcome": ui_outcome,
                                "duration_minutes": int(ui_duration),
                                "summary": ui_summary.strip(),
                                "next_step": ui_next_step.strip(),
                                "follow_up_date": None if ui_no_followup else ui_followup_date.isoformat(),
                            },
                        )
                        st.success("Interaction updated.")

        st.markdown("---")
        st.markdown("**Follow-ups due**")
        followup_cutoff = st.date_input("Show follow-ups due on or before", value=today, key="followup_cutoff")
        df_followups = get_followups_df(conn, followup_cutoff)
        if df_followups.empty:
            st.info("No follow-ups due.")
        else:
            st.dataframe(
                df_followups[["id", "name", "company", "interaction_date", "follow_up_date", "next_step"]],
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("---")
        st.markdown("**Networking scripts library**")
        df_scripts = get_scripts_df(conn)
        if df_scripts.empty:
            st.info("No scripts available.")
        else:
            script_labels = df_scripts.apply(lambda r: f"{r['category']} - {r['title']}", axis=1).tolist()
            script_map = dict(zip(script_labels, df_scripts.index.tolist()))
            chosen_script = st.selectbox("Script", script_labels)
            srow = df_scripts.loc[script_map[chosen_script]]
            st.text_area("Template", value=srow["body"], height=160)
            if pd.notna(srow.get("char_limit")):
                st.caption(f"Character limit: {int(srow['char_limit'])}")

    # --- Export / Import
    with tabs[4]:
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
        st.markdown("**Export networking contacts & interactions (CSV)**")
        df_contacts = get_contacts_df(conn)
        df_interactions = get_interactions_df(conn)
        c1, c2 = st.columns(2)
        with c1:
            if df_contacts.empty:
                st.info("No contacts to export.")
            else:
                csvc = df_contacts.to_csv(index=False).encode("utf-8")
                st.download_button("Download contacts CSV", data=csvc, file_name="networking_contacts.csv", mime="text/csv")
        with c2:
            if df_interactions.empty:
                st.info("No interactions to export.")
            else:
                csvi = df_interactions.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download interactions CSV",
                    data=csvi,
                    file_name="networking_interactions.csv",
                    mime="text/csv",
                )

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
