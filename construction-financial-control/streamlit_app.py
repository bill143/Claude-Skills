"""Construction Financial Control System — Streamlit UI.

Run:  streamlit run streamlit_app.py
Talks to the FastAPI backend (API_BASE_URL env var, default http://localhost:8000).
"""
import os

import pandas as pd
import requests
import streamlit as st

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/") + "/api/v1"

st.set_page_config(page_title="Construction Financial Control", page_icon="🏗️", layout="wide")


# ----------------------------------------------------------------- API helpers
def _headers() -> dict:
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_get(path: str, **params):
    resp = requests.get(f"{API_BASE}{path}", headers=_headers(), params=params, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"{resp.status_code}: {resp.text}")
    return resp.json()


def api_post(path: str, json=None, data=None, **params):
    resp = requests.post(
        f"{API_BASE}{path}", headers=_headers(), json=json, data=data, params=params, timeout=30
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"{resp.status_code}: {resp.text}")
    return resp.json()


def show_error(exc: Exception):
    st.error(str(exc))


# ----------------------------------------------------------------------- Login
with st.sidebar:
    st.title("🏗️ CFCS")
    if "token" not in st.session_state:
        st.subheader("Sign in")
        with st.form("login"):
            email = st.text_input("Email", value="pm@example.com")
            password = st.text_input("Password", type="password", value="ChangeMe123!")
            if st.form_submit_button("Login", use_container_width=True):
                try:
                    resp = requests.post(
                        f"{API_BASE}/auth/login",
                        data={"username": email, "password": password},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    st.session_state["token"] = resp.json()["access_token"]
                    st.session_state["user"] = api_get("/auth/me")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Login failed: {exc}")
        st.stop()

    user = st.session_state["user"]
    st.success(f"{user['full_name']}\n\n`{user['role']}`")
    if st.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    try:
        projects = api_get("/projects")
    except Exception as exc:  # noqa: BLE001
        show_error(exc)
        st.stop()
    if not projects:
        st.warning("No projects yet. Run scripts/seed.py or create one via the API docs.")
        st.stop()
    project = st.selectbox(
        "Project", projects, format_func=lambda p: f"{p['code']} — {p['name']}"
    )
    PROJECT_ID = project["id"]


tabs = st.tabs(
    ["📊 Dashboard", "🔀 Change Orders", "📦 Purchase Orders", "✅ Approvals",
     "💰 Budget & Costs", "🏢 Vendors", "🧾 Audit"]
)


# ------------------------------------------------------------------- Dashboard
with tabs[0]:
    st.header(f"{project['code']} — {project['name']}")
    method = st.radio("Forecast method", ["REMAINING_BUDGET", "CPI"], horizontal=True)
    pct = None
    if method == "CPI":
        pct = st.slider("Percent complete (for earned value)", 0.0, 1.0, 0.5, 0.05)
    try:
        kpis = api_get(f"/projects/{PROJECT_ID}/kpis", method=method,
                       **({"percent_complete": pct} if pct is not None else {}))
        row1 = st.columns(4)
        row1[0].metric("Contract Value", f"${kpis['contract_value']:,.0f}")
        row1[1].metric("Current Budget", f"${kpis['current_budget']:,.0f}",
                       delta=f"{kpis['approved_changes']:+,.0f} changes")
        row1[2].metric("Committed", f"${kpis['committed']:,.0f}")
        row1[3].metric("Actual to Date", f"${kpis['actual_to_date']:,.0f}")
        row2 = st.columns(4)
        row2[0].metric("EAC (Forecast at Completion)", f"${kpis['eac']:,.0f}")
        row2[1].metric("ETC (Cost to Complete)", f"${kpis['etc']:,.0f}")
        row2[2].metric("VAC (Variance at Completion)", f"${kpis['vac']:,.0f}",
                       delta_color="inverse" if kpis["vac"] < 0 else "normal",
                       delta=f"{kpis['vac']:,.0f}")
        row2[3].metric("Projected Margin", f"${kpis['projected_margin']:,.0f}")
        row3 = st.columns(4)
        row3[0].metric("Burn Rate (30d)", f"${kpis['burn_rate_30d']:,.0f}")
        row3[1].metric("% Complete (cost basis)", f"{kpis['percent_complete'] * 100:.1f}%")
        row3[2].metric("Open PCOs", kpis["open_pcos"])
        row3[3].metric("Pending Approvals", kpis["pending_approvals"])

        forecast = api_get(f"/projects/{PROJECT_ID}/forecast", method=method,
                           **({"percent_complete": pct} if pct is not None else {}))
        st.subheader("Budget lines")
        df = pd.DataFrame(forecast["lines"])
        if not df.empty:
            df = df[["cost_code", "description", "category", "original_budget",
                     "approved_changes", "current_budget", "committed", "actual",
                     "etc", "eac", "vac"]]
            st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as exc:  # noqa: BLE001
        show_error(exc)


# --------------------------------------------------------------- Change Orders
with tabs[1]:
    st.header("Change Orders (PCO → OCO / SCO)")
    try:
        budget_lines = api_get(f"/projects/{PROJECT_ID}/budget-lines")
        vendors = api_get("/vendors")
    except Exception as exc:  # noqa: BLE001
        show_error(exc)
        budget_lines, vendors = [], []
    bl_label = {bl["id"]: f"{bl['cost_code']} — {bl['description']}" for bl in budget_lines}

    with st.expander("➕ Create a PCO"):
        with st.form("create_pco"):
            title = st.text_input("Title")
            description = st.text_area("Description", height=68)
            days = st.number_input("Schedule impact (days)", value=0, step=1)
            st.caption("Lines (leave a line's amount fields at 0 to skip it)")
            line_inputs = []
            for i in range(3):
                cols = st.columns([3, 3, 1, 2])
                bl = cols[0].selectbox(f"Budget line {i + 1}", options=[None] + list(bl_label),
                                       format_func=lambda x: "—" if x is None else bl_label[x],
                                       key=f"pco_bl_{i}")
                desc = cols[1].text_input("Line description", key=f"pco_desc_{i}")
                qty = cols[2].number_input("Qty", min_value=0.0, value=1.0, key=f"pco_qty_{i}")
                cost = cols[3].number_input("Unit cost $", min_value=0.0, value=0.0,
                                            key=f"pco_cost_{i}")
                line_inputs.append((bl, desc, qty, cost))
            if st.form_submit_button("Create PCO"):
                lines = [
                    {"budget_line_id": bl, "description": desc or "Line", "quantity": qty,
                     "unit_cost": cost}
                    for bl, desc, qty, cost in line_inputs
                    if bl is not None and qty > 0 and cost > 0
                ]
                if not title or not lines:
                    st.warning("Provide a title and at least one line with qty and cost.")
                else:
                    try:
                        co = api_post(f"/projects/{PROJECT_ID}/change-orders",
                                      json={"co_type": "PCO", "title": title,
                                            "description": description,
                                            "schedule_impact_days": int(days), "lines": lines})
                        st.success(f"Created {co['number']} — ${co['total_amount']:,.2f}")
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        show_error(exc)

    try:
        cos = api_get(f"/projects/{PROJECT_ID}/change-orders")
    except Exception as exc:  # noqa: BLE001
        show_error(exc)
        cos = []
    if cos:
        st.dataframe(
            pd.DataFrame([
                {"Number": c["number"], "Type": c["co_type"], "Status": c["status"],
                 "Title": c["title"], "Amount": c["total_amount"],
                 "Days": c["schedule_impact_days"],
                 "From PCO": c["origin_pco_id"] or ""}
                for c in cos
            ]),
            use_container_width=True, hide_index=True,
        )
        selected = st.selectbox(
            "Work on document", cos,
            format_func=lambda c: f"{c['number']} [{c['status']}] {c['title']} "
                                  f"(${c['total_amount']:,.0f})",
        )
        actions = selected["allowed_actions"]
        st.write(f"**{selected['number']}** — status `{selected['status']}` — "
                 f"allowed actions: `{', '.join(actions) or 'none'}`")
        action_cols = st.columns(max(len(actions), 1) + 1)
        for i, action in enumerate(a for a in actions if a != "convert"):
            if action_cols[i].button(action.replace("_", " ").title(),
                                     key=f"co_act_{selected['id']}_{action}"):
                try:
                    api_post(f"/change-orders/{selected['id']}/transition",
                             json={"action": action})
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    show_error(exc)

        if "convert" in actions:
            st.subheader("Convert PCO")
            with st.form(f"convert_{selected['id']}"):
                targets = st.multiselect("Create documents", ["OCO", "SCO"],
                                         default=["OCO", "SCO"])
                vendor = st.selectbox("Subcontractor (for SCO)", vendors,
                                      format_func=lambda v: v["name"]) if vendors else None
                markup = st.number_input("OCO markup % over cost", min_value=0.0,
                                         max_value=100.0, value=10.0) / 100.0
                if st.form_submit_button("Convert"):
                    try:
                        created = api_post(
                            f"/change-orders/{selected['id']}/convert",
                            json={"targets": targets,
                                  "vendor_id": vendor["id"] if vendor else None,
                                  "oco_markup_pct": markup},
                        )
                        st.success("Created: " + ", ".join(
                            f"{d['number']} (${d['total_amount']:,.2f})" for d in created))
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        show_error(exc)

        approvals = api_get(f"/change-orders/{selected['id']}/approvals")
        if approvals:
            st.caption("Approval chain")
            st.dataframe(pd.DataFrame([
                {"Step": a["sequence"], "Role": a["required_role"], "Status": a["status"],
                 "Comment": a["comment"] or ""}
                for a in approvals
            ]), use_container_width=True, hide_index=True)
    else:
        st.info("No change orders yet — create a PCO above.")


# ------------------------------------------------------------- Purchase Orders
with tabs[2]:
    st.header("Purchase Orders & Commitments")
    try:
        budget_lines = api_get(f"/projects/{PROJECT_ID}/budget-lines")
        vendors = api_get("/vendors")
        approved_scos = api_get(f"/projects/{PROJECT_ID}/change-orders",
                                co_type="SCO", status="APPROVED")
    except Exception as exc:  # noqa: BLE001
        show_error(exc)
        budget_lines, vendors, approved_scos = [], [], []
    bl_label = {bl["id"]: f"{bl['cost_code']} — {bl['description']}" for bl in budget_lines}

    with st.expander("➕ Create a PO"):
        source = st.radio("Source", ["Manual lines", "From approved SCO"], horizontal=True)
        with st.form("create_po"):
            if source == "From approved SCO" and approved_scos:
                sco = st.selectbox("Approved SCO", approved_scos,
                                   format_func=lambda c: f"{c['number']} {c['title']} "
                                                         f"(${c['total_amount']:,.0f})")
                payload = {"vendor_id": sco["vendor_id"],
                           "source_change_order_id": sco["id"], "lines": []}
            else:
                vendor = st.selectbox("Vendor", vendors,
                                      format_func=lambda v: v["name"]) if vendors else None
                bl = st.selectbox("Budget line", options=list(bl_label),
                                  format_func=lambda x: bl_label[x]) if bl_label else None
                desc = st.text_input("Line description", value="Materials")
                qty = st.number_input("Qty", min_value=0.0, value=1.0)
                cost = st.number_input("Unit cost $", min_value=0.0, value=0.0)
                payload = {"vendor_id": vendor["id"] if vendor else None,
                           "lines": [{"budget_line_id": bl, "description": desc,
                                      "quantity": qty, "unit_cost": cost}] if bl else []}
            if st.form_submit_button("Create PO"):
                try:
                    po = api_post(f"/projects/{PROJECT_ID}/purchase-orders", json=payload)
                    st.success(f"Created {po['number']} — ${po['total_amount']:,.2f}")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    show_error(exc)

    try:
        pos = api_get(f"/projects/{PROJECT_ID}/purchase-orders")
    except Exception as exc:  # noqa: BLE001
        show_error(exc)
        pos = []
    if pos:
        st.dataframe(pd.DataFrame([
            {"Number": p["number"], "Status": p["status"], "Vendor": p["vendor_id"],
             "Amount": p["total_amount"], "From SCO": p["source_change_order_id"] or ""}
            for p in pos
        ]), use_container_width=True, hide_index=True)
        selected_po = st.selectbox("Work on PO", pos,
                                   format_func=lambda p: f"{p['number']} [{p['status']}] "
                                                         f"${p['total_amount']:,.0f}")
        cols = st.columns(4)
        if selected_po["status"] == "DRAFT" and cols[0].button("Submit for approval"):
            try:
                result = api_post(f"/purchase-orders/{selected_po['id']}/submit")
                if result["budget_warnings"]:
                    st.warning(f"Budget warnings: {result['budget_warnings']}")
                st.success(f"PO status: {result['status']}")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                show_error(exc)
        if selected_po["status"] == "APPROVED" and cols[1].button("Close PO"):
            try:
                api_post(f"/purchase-orders/{selected_po['id']}/transition",
                         json={"action": "close"})
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                show_error(exc)
    else:
        st.info("No purchase orders yet.")


# ------------------------------------------------------------------- Approvals
with tabs[3]:
    st.header("My Pending Approvals")
    try:
        pending = api_get("/approvals/pending")
    except Exception as exc:  # noqa: BLE001
        show_error(exc)
        pending = []
    if not pending:
        st.info("Nothing waiting on you. 🎉")
    for req in pending:
        with st.container(border=True):
            st.write(f"**{req['entity_type']}** #{req['entity_id']} — step {req['sequence']} "
                     f"requires `{req['required_role']}`")
            comment = st.text_input("Comment", key=f"cmt_{req['id']}")
            col_a, col_b = st.columns(2)
            if col_a.button("✅ Approve", key=f"ap_{req['id']}"):
                try:
                    result = api_post(f"/approvals/{req['id']}/decide",
                                      json={"approve": True, "comment": comment})
                    st.success(f"Entity status: {result['entity_status']}")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    show_error(exc)
            if col_b.button("❌ Reject", key=f"rj_{req['id']}"):
                try:
                    result = api_post(f"/approvals/{req['id']}/decide",
                                      json={"approve": False, "comment": comment})
                    st.warning(f"Entity status: {result['entity_status']}")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    show_error(exc)


# -------------------------------------------------------------- Budget & Costs
with tabs[4]:
    st.header("Budget Lines & Actual Costs")
    try:
        budget_lines = api_get(f"/projects/{PROJECT_ID}/budget-lines")
    except Exception as exc:  # noqa: BLE001
        show_error(exc)
        budget_lines = []
    with st.expander("➕ Add budget line"):
        with st.form("add_bl"):
            code = st.text_input("Cost code (e.g. 03-300)")
            desc = st.text_input("Description")
            category = st.selectbox("Category", ["LABOR", "MATERIAL", "EQUIPMENT",
                                                 "SUBCONTRACT", "GENERAL_CONDITIONS"])
            amount = st.number_input("Original budget $", min_value=0.0, value=0.0)
            if st.form_submit_button("Add"):
                try:
                    api_post(f"/projects/{PROJECT_ID}/budget-lines",
                             json={"cost_code": code, "description": desc,
                                   "category": category, "original_budget": amount})
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    show_error(exc)
    if budget_lines:
        st.dataframe(pd.DataFrame(budget_lines)[
            ["cost_code", "description", "category", "original_budget"]
        ], use_container_width=True, hide_index=True)
        with st.expander("💵 Post actual cost"):
            with st.form("post_cost"):
                bl_map = {bl["id"]: f"{bl['cost_code']} — {bl['description']}"
                          for bl in budget_lines}
                bl = st.selectbox("Budget line", options=list(bl_map),
                                  format_func=lambda x: bl_map[x])
                cost_date = st.date_input("Date")
                amount = st.number_input("Amount $", min_value=0.0, value=0.0)
                desc = st.text_input("Description", value="Invoice")
                if st.form_submit_button("Post cost"):
                    try:
                        api_post(f"/budget-lines/{bl}/costs",
                                 json={"entry_date": str(cost_date), "amount": amount,
                                       "description": desc})
                        st.success("Posted.")
                    except Exception as exc:  # noqa: BLE001
                        show_error(exc)


# --------------------------------------------------------------------- Vendors
with tabs[5]:
    st.header("Vendors & Subcontractors")
    with st.expander("➕ Add vendor"):
        with st.form("add_vendor"):
            name = st.text_input("Name")
            vtype = st.selectbox("Type", ["SUBCONTRACTOR", "SUPPLIER"])
            trade = st.text_input("Trade")
            email = st.text_input("Contact email")
            if st.form_submit_button("Add"):
                try:
                    api_post("/vendors", json={"name": name, "vendor_type": vtype,
                                               "trade": trade, "contact_email": email})
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    show_error(exc)
    try:
        vendors = api_get("/vendors")
        if vendors:
            st.dataframe(pd.DataFrame(vendors)[
                ["name", "vendor_type", "trade", "contact_email", "is_active"]
            ], use_container_width=True, hide_index=True)
    except Exception as exc:  # noqa: BLE001
        show_error(exc)


# ----------------------------------------------------------------------- Audit
with tabs[6]:
    st.header("Audit Ledger")
    col_a, col_b = st.columns([1, 3])
    if col_a.button("🔐 Verify hash chain"):
        try:
            result = api_get("/audit/verify")
            if result["valid"]:
                col_b.success(f"Chain valid — {result['events']} events.")
            else:
                col_b.error(f"CHAIN BROKEN at event {result['first_broken_event_id']}: "
                            f"{result['reason']}")
        except Exception as exc:  # noqa: BLE001
            show_error(exc)
    try:
        events = api_get("/audit", limit=200)
        if events:
            st.dataframe(pd.DataFrame([
                {"When": e["created_at"], "Entity": f"{e['entity_type']}#{e['entity_id']}",
                 "Action": e["action"], "Actor": e["actor_id"],
                 "Payload": str(e["payload"])[:120]}
                for e in events
            ]), use_container_width=True, hide_index=True)
    except Exception as exc:  # noqa: BLE001
        show_error(exc)
