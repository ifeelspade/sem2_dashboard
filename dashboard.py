import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ======================================================
# PAGE CONFIG
# ======================================================

st.set_page_config(page_title="MBA Result Analytics Dashboard", layout="wide")

st.title("MBA Result Analytics Dashboard")
st.markdown("Comprehensive analysis of all MBA divisions")

# ======================================================
# LOAD DATA
# ======================================================

FILE_PATH = "MBA_All_Divisions_Result.xlsx"

@st.cache_data
def load_data():
    df = pd.read_excel(FILE_PATH)
    return df

df = load_data()

# ======================================================
# CONSTANTS
# ======================================================

OPTIONAL_SUBJECTS = {
    "Beheco", "CDMNE", "DMUSQL", "MrktngIn", "FECO", "GnrtcAi"
}

# A student FAILS a subject if CA < 25 OR ETE < 25
PASS_CA  = 25
PASS_ETE = 25

# ======================================================
# CLEAN MARKS  (handles XX, 17@8, NaN)
# Returns None = "not taken / absent"
# ======================================================

def convert_marks(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    if value.upper() == "XX":
        return None
    if "@" in value:
        try:
            main, grace = value.split("@")
            return int(main) + int(grace)
        except:
            return None
    try:
        return int(float(value))
    except:
        return None

# ======================================================
# PREP
# ======================================================

if "GPA" in df.columns:
    df["GPA"] = pd.to_numeric(df["GPA"], errors="coerce")

subject_columns = [c for c in df.columns if c.endswith("_CA") or c.endswith("_ETE")]

for col in subject_columns:
    df[col] = df[col].apply(convert_marks)

# ======================================================
# PAGE NAVIGATION
# ======================================================

page = st.sidebar.radio(
    "Select Page",
    [
        "Dashboard Analytics",
        "Student Analytics"
    ]
)

# ======================================================
# SIDEBAR FILTERS
# ======================================================

st.sidebar.header("Filters")

selected_division = st.sidebar.multiselect(
    "Select Division",
    options=sorted(df["Division"].dropna().unique()),
    default=sorted(df["Division"].dropna().unique())
)

filtered_df = df[df["Division"].isin(selected_division)].copy()

# ======================================================
# FAIL CHECK HELPER
# Fail = CA < 25 OR ETE < 25
# Optional + both None = not enrolled → return None (skip)
# ======================================================

def subject_failed(ca, ete, subject_name):
    is_optional = subject_name in OPTIONAL_SUBJECTS
    ca_missing  = pd.isna(ca)
    ete_missing = pd.isna(ete)

    # Optional and not enrolled at all → skip
    if is_optional and ca_missing and ete_missing:
        return None

    ca_val  = float(ca)  if not ca_missing  else None
    ete_val = float(ete) if not ete_missing else None

    # Fail if CA present and < 25
    if ca_val is not None and ca_val < PASS_CA:
        return True

    # Fail if ETE present and < 25
    if ete_val is not None and ete_val < PASS_ETE:
        return True

    return False

if page == "Dashboard Analytics":

        # ======================================================
        # KPI METRICS
        # ======================================================

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Students", len(filtered_df))

        with col2:
            avg_gpa = round(filtered_df["GPA"].mean(), 2)
            st.metric("Average GPA", avg_gpa)

        with col3:
            pass_count   = filtered_df[filtered_df["Result"] == "Yes"].shape[0]
            pass_percent = round((pass_count / len(filtered_df)) * 100, 2) if len(filtered_df) else 0
            st.metric("Pass Percentage", f"{pass_percent}%")

        with col4:
            topper_gpa = filtered_df["GPA"].max()
            st.metric("Highest GPA", topper_gpa)

        st.divider()

        # ======================================================
        # DIVISION GPA ANALYSIS
        # ======================================================

        st.subheader("Division-wise Average GPA")

        division_gpa = (
            filtered_df.groupby("Division")["GPA"]
            .mean()
            .reset_index()
            .sort_values(by="GPA", ascending=False)
        )

        fig_division_gpa = px.bar(
            division_gpa, x="Division", y="GPA",
            text_auto=True, title="Average GPA by Division"
        )
        st.plotly_chart(fig_division_gpa, use_container_width=True)

        st.subheader("Best Performing Division")
        best_division = division_gpa.iloc[0]
        st.success(
            f"Division {best_division['Division']} has the highest average GPA of {round(best_division['GPA'], 2)}"
        )

        # ======================================================
        # SUBJECT-WISE AVERAGE
        # ======================================================

        st.subheader("Subject-wise Average Marks by Division")

        def subject_avg_by_division(df_in, subject_col):
            subject_name = subject_col.replace("_CA", "").replace("_ETE", "")
            if subject_name in OPTIONAL_SUBJECTS:
                valid = df_in[df_in[subject_col].notna()]
            else:
                valid = df_in.copy()
                valid[subject_col] = valid[subject_col].fillna(0)
            return valid.groupby("Division")[subject_col].mean().reset_index()

        selected_subject = st.selectbox("Select Subject", subject_columns)
        sub_avg = subject_avg_by_division(filtered_df, selected_subject)

        fig_subject = px.bar(
            sub_avg, x="Division", y=selected_subject,
            text_auto=True,
            title=f"{selected_subject} — Average Marks by Division (enrolled students only)"
        )
        st.plotly_chart(fig_subject, use_container_width=True)

        # ======================================================
        # TOPPERS TABLE
        # ======================================================

        st.subheader("Top 80 Students")

        rank_df = filtered_df.sort_values(by="GPA", ascending=False)
        st.dataframe(
            rank_df[["Roll No.","Name", "Division", "Batch", "GPA"]].head(80),
            use_container_width=True
        )

        # ======================================================
        # PASS VS FAIL
        # ======================================================

        st.subheader("Pass vs Fail Analysis")

        pass_fail = filtered_df["Result"].value_counts().reset_index()
        pass_fail.columns = ["Result", "Count"]

        fig_pass_fail = px.pie(
            pass_fail, names="Result", values="Count",
            title="Pass vs Fail Distribution"
        )
        st.plotly_chart(fig_pass_fail, use_container_width=True)

        # ======================================================
        # HIGHEST SCORING DIVISION PER SUBJECT
        # Mandatory and Optional shown in SEPARATE tables
        # ======================================================

        mandatory_summary = []
        optional_summary  = []
        processed = set()

        for col in subject_columns:
            subject_name = col.replace("_CA", "").replace("_ETE", "")
            if subject_name in processed:
                continue
            processed.add(subject_name)

            ca_col  = f"{subject_name}_CA"
            ete_col = f"{subject_name}_ETE"
            is_opt  = subject_name in OPTIONAL_SUBJECTS

            if is_opt:
                mask     = filtered_df[ca_col].notna() | filtered_df[ete_col].notna()
                valid_df = filtered_df[mask]
            else:
                valid_df = filtered_df

            if valid_df.empty:
                continue

            temp = valid_df.copy()
            temp["_total"] = temp[ca_col].fillna(0) + temp[ete_col].fillna(0)
            div_avg = temp.groupby("Division")["_total"].mean().reset_index()

            if div_avg.empty:
                continue

            top_row = div_avg.sort_values(by="_total", ascending=False).iloc[0]

            row_data = {
                "Subject":        subject_name,
                "Top Division":   top_row["Division"],
                "Average Marks":  round(top_row["_total"], 2),
                "Enrolled Count": len(valid_df)
            }

            if is_opt:
                optional_summary.append(row_data)
            else:
                mandatory_summary.append(row_data)

        st.subheader("Highest Scoring Division per Subject (Mandatory)")
        st.dataframe(pd.DataFrame(mandatory_summary), use_container_width=True)

        st.subheader("Highest Scoring Division per Subject (Optional / Elective)")
        st.dataframe(pd.DataFrame(optional_summary), use_container_width=True)

        # ======================================================
        # FAILURE ANALYTICS
        # ======================================================

        st.subheader("Failure Analytics")

        # ── Per-student: count subjects where CA < 25 OR ETE < 25 ──
        student_fail_counts = []

        for _, row in filtered_df.iterrows():
            fail_count = 0
            counted    = set()

            for col in subject_columns:
                subject_name = col.replace("_CA", "").replace("_ETE", "")
                if subject_name in counted:
                    continue
                counted.add(subject_name)

                ca  = row.get(f"{subject_name}_CA",  None)
                ete = row.get(f"{subject_name}_ETE", None)

                result = subject_failed(ca, ete, subject_name)
                if result is None:
                    continue        # optional, not enrolled → skip
                if result:
                    fail_count += 1

            student_fail_counts.append(fail_count)

        filtered_df["Failed_Subjects"] = student_fail_counts

        # ── Division bar: count of students with GPA = 0 ──
        division_gpa_zero = (
            filtered_df[filtered_df["GPA"] == 0]
            .groupby("Division")
            .size()
            .reset_index(name="Students with GPA 0")
            .sort_values(by="Students with GPA 0", ascending=False)
        )

        fig_fail_division = px.bar(
            division_gpa_zero,
            x="Division",
            y="Students with GPA 0",
            text_auto=True,
            title="Number of Unsuccessful Students (GPA = 0) by Division"
        )
        st.plotly_chart(fig_fail_division, use_container_width=True)

        # ── Students with most failed subjects ──
        st.subheader("Students with Highest Failed Subjects")

        top_failed = (
            filtered_df[["Name", "Division", "Failed_Subjects", "GPA"]]
            .sort_values(by="Failed_Subjects", ascending=False)
            .head(20)
        )
        st.dataframe(top_failed, use_container_width=True)

        # ── Subject-level failure rate ──
        subject_fail_data = []
        processed = set()

        for col in subject_columns:
            subject_name = col.replace("_CA", "").replace("_ETE", "")
            if subject_name in processed:
                continue
            processed.add(subject_name)

            ca_col  = f"{subject_name}_CA"
            ete_col = f"{subject_name}_ETE"

            fail_count     = 0
            total_students = 0

            for _, row in filtered_df.iterrows():
                ca  = row.get(ca_col,  None)
                ete = row.get(ete_col, None)

                result = subject_failed(ca, ete, subject_name)
                if result is None:
                    continue    # not enrolled
                total_students += 1
                if result:
                    fail_count += 1

            fail_pct = (fail_count / total_students * 100) if total_students > 0 else 0

            subject_fail_data.append({
                "Subject":           subject_name,
                "Enrolled Students": total_students,
                "Failed Students":   fail_count,
                "Failure %":         round(fail_pct, 2)
            })

        subject_fail_df = pd.DataFrame(subject_fail_data)

        fig_subject_fail = px.bar(
            subject_fail_df.sort_values(by="Failure %", ascending=False),
            x="Subject", y="Failure %",
            text_auto=True,
            title="Subject Failure %"
        )
        st.plotly_chart(fig_subject_fail, use_container_width=True)

        worst = subject_fail_df.sort_values(by="Failure %", ascending=False).iloc[0]
        st.error(
            f"Most difficult subject: **{worst['Subject']}** "
            f"with {worst['Failure %']}% failure rate "
            f"({worst['Failed Students']} of {worst['Enrolled Students']} students)."
        )

        # ======================================================
        # GPA DISTRIBUTION
        # ======================================================

        st.subheader("GPA Distribution")

        fig_hist = px.histogram(
            filtered_df, x="GPA", nbins=20, title="Distribution of GPA"
        )
        st.plotly_chart(fig_hist, use_container_width=True)

        # ======================================================
        # RECOMMENDATIONS ENGINE
        # ======================================================

        st.subheader("AI-style Academic Recommendations")

        subject_means = {}
        for col in subject_columns:
            subject_name = col.replace("_CA", "").replace("_ETE", "")
            if subject_name in OPTIONAL_SUBJECTS:
                valid_vals = filtered_df[col].dropna()
            else:
                valid_vals = filtered_df[col].fillna(0)
            if len(valid_vals) > 0:
                subject_means[col] = valid_vals.mean()

        if subject_means:
            sorted_means    = sorted(subject_means.items(), key=lambda x: x[1])
            lowest_subject  = sorted_means[0][0]
            highest_subject = sorted_means[-1][0]
        else:
            lowest_subject  = "N/A"
            highest_subject = "N/A"

        recommendations = [
            f"Students are weakest in **{lowest_subject}**. Additional academic support is recommended.",
            f"Strongest overall performance observed in **{highest_subject}**.",
            f"Division **{division_gpa.sort_values('GPA').iloc[0]['Division']}** requires mentoring — lowest average GPA.",
        ]

        if pass_percent < 75:
            recommendations.append("Overall pass percentage is below 75%. Faculty intervention is recommended.")
        else:
            recommendations.append("Overall academic performance is healthy across divisions.")

        for rec in recommendations:
            st.info(rec)

        # ======================================================
        # DOWNLOAD
        # ======================================================

        st.subheader("Download Filtered Dataset")

        csv = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="filtered_mba_results.csv",
            mime="text/csv",
        )

        st.divider()
        st.caption("MBA Result Analytics Dashboard")

# ======================================================
# STUDENT ANALYTICS PAGE
# ======================================================

elif page == "Student Analytics":

    st.title("Student Analytics Portal")

    # --------------------------------------------------
    # DIVISION SELECT
    # --------------------------------------------------

    student_division = st.selectbox(
        "Select Division",
        sorted(filtered_df["Division"].dropna().unique())
    )

    division_students = filtered_df[
        filtered_df["Division"] == student_division
    ].copy()

    # --------------------------------------------------
    # STUDENT SELECT
    # --------------------------------------------------

    student_name = st.selectbox(
        "Select Student",
        sorted(division_students["Name"].dropna().unique())
    )

    student_df = division_students[
        division_students["Name"] == student_name
    ]

    # --------------------------------------------------
    # STUDENT DATA
    # --------------------------------------------------

    if not student_df.empty:

        student = student_df.iloc[0]

        failed_subjects = student.get("Failed_Subjects", 0)

        st.subheader(f"Student Report : {student_name}")

        # --------------------------------------------------
        # KPI
        # --------------------------------------------------

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric("GPA", student["GPA"])

        with c2:
            st.metric("Division", student["Division"])

        with c3:
            st.metric("Result", student["Result"])

        with c4:
            st.metric("Failed Subjects", failed_subjects)

        # --------------------------------------------------
        # SUBJECT PERFORMANCE
        # --------------------------------------------------

        st.subheader("Subject-wise Performance")

        subject_data = []

        processed = set()

        for col in subject_columns:

            subject_name = col.replace("_CA", "").replace("_ETE", "")

            if subject_name in processed:
                continue

            processed.add(subject_name)

            ca_col = f"{subject_name}_CA"
            ete_col = f"{subject_name}_ETE"

            ca = student.get(ca_col, None)
            ete = student.get(ete_col, None)

            # OPTIONAL SUBJECTS
            if subject_name in OPTIONAL_SUBJECTS:

                if pd.isna(ca) and pd.isna(ete):
                    continue

            ca = 0 if pd.isna(ca) else ca
            ete = 0 if pd.isna(ete) else ete

            total = ca + ete

            result = "PASS"

            if ca < PASS_CA or ete < PASS_ETE:
                result = "FAIL"

            subject_data.append({
                "Subject": subject_name,
                "CA": ca,
                "ETE": ete,
                "Total": total,
                "Result": result
            })

        subject_df = pd.DataFrame(subject_data)

        st.dataframe(subject_df, use_container_width=True)

        # --------------------------------------------------
        # SUBJECT BAR CHART
        # --------------------------------------------------

        fig_student_marks = px.bar(
            subject_df,
            x="Subject",
            y="Total",
            text_auto=True,
            title="Student Subject-wise Total Marks"
        )

        st.plotly_chart(fig_student_marks, use_container_width=True)

        # --------------------------------------------------
        # DIVISION COMPARISON
        # --------------------------------------------------

        st.subheader("Comparison with Division Average")

        comparison_data = []

        for _, row in subject_df.iterrows():

            subject_name = row["Subject"]

            ca_col = f"{subject_name}_CA"
            ete_col = f"{subject_name}_ETE"

            division_avg = (
                division_students[ca_col].fillna(0)
                + division_students[ete_col].fillna(0)
            ).mean()

            comparison_data.append({
                "Subject": subject_name,
                "Student Marks": row["Total"],
                "Division Average": round(division_avg, 2)
            })

        comparison_df = pd.DataFrame(comparison_data)

        import plotly.graph_objects as go

        fig_compare = go.Figure()

        fig_compare.add_trace(
            go.Bar(
                x=comparison_df["Subject"],
                y=comparison_df["Student Marks"],
                name="Student"
            )
        )

        fig_compare.add_trace(
            go.Bar(
                x=comparison_df["Subject"],
                y=comparison_df["Division Average"],
                name="Division Average"
            )
        )

        fig_compare.update_layout(
            barmode="group",
            title="Student vs Division Average"
        )

        st.plotly_chart(fig_compare, use_container_width=True)

        # --------------------------------------------------
        # STUDENT RANK
        # --------------------------------------------------

        st.subheader("Student Rank")

        rank_df = division_students.sort_values(
            by="GPA",
            ascending=False
        ).reset_index(drop=True)

        rank_df["Rank"] = rank_df.index + 1

        student_rank = rank_df[
            rank_df["Name"] == student_name
        ]["Rank"].values[0]

        st.success(
            f"{student_name} is ranked #{student_rank} "
            f"in Division {student_division}"
        )

        # --------------------------------------------------
        # STRENGTHS & WEAKNESSES
        # --------------------------------------------------

        st.subheader("Strengths & Weaknesses")

        best_subject = subject_df.sort_values(
            by="Total",
            ascending=False
        ).iloc[0]

        weak_subject = subject_df.sort_values(
            by="Total",
            ascending=True
        ).iloc[0]

        st.info(
            f"Strongest Subject: {best_subject['Subject']} "
            f"({best_subject['Total']} marks)"
        )

        st.warning(
            f"Weakest Subject: {weak_subject['Subject']} "
            f"({weak_subject['Total']} marks)"
        )

        # --------------------------------------------------
        # FAIL SUBJECTS
        # --------------------------------------------------

        failed_df = subject_df[
            subject_df["Result"] == "FAIL"
        ]

        st.subheader("Failed Subjects")

        if failed_df.empty:

            st.success("No failed subjects")

        else:

            st.dataframe(
                failed_df,
                use_container_width=True
            )

        # --------------------------------------------------
        # AI RECOMMENDATIONS
        # --------------------------------------------------

        st.subheader("AI Recommendations")

        recommendations = []

        gpa = student["GPA"]

        if gpa >= 8:

            recommendations.append(
                "Excellent academic performance."
            )

        elif gpa >= 6:

            recommendations.append(
                "Good performance with improvement scope."
            )

        else:

            recommendations.append(
                "Student requires academic mentoring."
            )

        if failed_subjects > 0:

            recommendations.append(
                f"Student has failed in "
                f"{failed_subjects} subjects."
            )

        recommendations.append(
            f"Focus more on {weak_subject['Subject']}."
        )

        recommendations.append(
            f"Maintain strong performance in "
            f"{best_subject['Subject']}."
        )

        for rec in recommendations:

            st.info(rec)
