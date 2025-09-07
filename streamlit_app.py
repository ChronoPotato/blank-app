import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime, timedelta
from uuid import uuid4

# ----------------------------
# App Config
# ----------------------------
st.set_page_config(page_title="Team Boards (In-Memory)", layout="wide")

STATUS_CHOICES = ["Not started", "In progress", "Blocked", "Done"]

# ----------------------------
# In-memory "DB" in session
# ----------------------------
def ss_init():
    ss = st.session_state
    ss.setdefault("team_members", {})        # id -> {id, name, email}
    ss.setdefault("boards", {})              # id -> {id, name, description}
    ss.setdefault("groups", {})              # id -> {id, board_id, name, position}
    ss.setdefault("items", {})               # id -> {id, board_id, group_id, title, description, status, start_date, due_date, timeline_start, timeline_end, created_by}
    ss.setdefault("item_assignments", set()) # {(item_id, user_id)}
    ss.setdefault("item_dependencies", set())# {(item_id, depends_on_id)}
    ss.setdefault("current_user_id", None)
    ss.setdefault("current_board_id", None)
    if not ss["boards"]:
        seed_demo_data()

def seed_demo_data():
    """Create a sample board with a couple of groups/items/people."""
    me = add_member("Alice", "alice@team.local")
    bob = add_member("Bob", "bob@team.local")
    ch = add_member("Charlie", "charlie@team.local")
    st.session_state["current_user_id"] = me

    b = add_board("Sample Project", "Internal demo project")
    st.session_state["current_board_id"] = b

    g1 = add_group(b, "Backlog", 0)
    g2 = add_group(b, "In Progress", 1)
    g3 = add_group(b, "Review", 2)

    i1 = add_item(b, g1, "Define requirements", "Kickoff with stakeholders",
                  status="Not started", start=None, due=None, tstart=None, tend=None, created_by=me)
    i2 = add_item(b, g1, "Wireframes", "UX wireframes for core flows",
                  status="Not started", start=None, due=None, tstart=None, tend=None, created_by=me)
    i3 = add_item(b, g2, "API skeleton", "Set up endpoints",
                  status="In progress", start=date.today(), due=date.today()+timedelta(days=7),
                  tstart=date.today(), tend=date.today()+timedelta(days=7), created_by=bob)
    i4 = add_item(b, g3, "Review architecture", "Tech review",
                  status="Blocked", start=None, due=None, tstart=None, tend=None, created_by=ch)

    assign(i1, me); assign(i2, me); assign(i3, bob); assign(i4, ch)
    # dependencies: architecture review depends on API skeleton
    dep_add(i4, i3)

# ----------------------------
# Helpers for in-memory ops
# ----------------------------
def add_member(name, email):
    uid = str(uuid4())
    st.session_state["team_members"][uid] = {"id": uid, "name": name, "email": email}
    return uid

def add_board(name, description=""):
    bid = str(uuid4())
    st.session_state["boards"][bid] = {"id": bid, "name": name, "description": description}
    return bid

def add_group(board_id, name, position=0):
    gid = str(uuid4())
    st.session_state["groups"][gid] = {"id": gid, "board_id": board_id, "name": name, "position": int(position)}
    return gid

def add_item(board_id, group_id, title, description="", status="Not started",
             start=None, due=None, tstart=None, tend=None, created_by=None):
    iid = str(uuid4())
    st.session_state["items"][iid] = {
        "id": iid, "board_id": board_id, "group_id": group_id,
        "title": title, "description": description, "status": status,
        "start_date": start, "due_date": due,
        "timeline_start": tstart, "timeline_end": tend,
        "created_by": created_by
    }
    return iid

def assign(item_id, user_id):
    st.session_state["item_assignments"].add((item_id, user_id))

def unassign(item_id, user_id):
    st.session_state["item_assignments"].discard((item_id, user_id))

def dep_add(item_id, depends_on_id):
    if item_id != depends_on_id:
        st.session_state["item_dependencies"].add((item_id, depends_on_id))

def dep_clear_for_item(item_id):
    st.session_state["item_dependencies"] = {(i, d) for (i, d) in st.session_state["item_dependencies"] if i != item_id}

def item_is_blocked(item_id):
    items = st.session_state["items"]
    deps = [d for (i, d) in st.session_state["item_dependencies"] if i == item_id]
    if not deps:
        return False
    # all dependencies must be Done
    for dep_id in deps:
        dep_item = items.get(dep_id)
        if not dep_item or dep_item["status"] != "Done":
            return True
    return False

def next_status(status):
    idx = STATUS_CHOICES.index(status)
    return STATUS_CHOICES[(idx + 1) % len(STATUS_CHOICES)]

def members_for_item(item_id):
    members = []
    for (iid, uid) in st.session_state["item_assignments"]:
        if iid == item_id:
            members.append(st.session_state["team_members"].get(uid))
    return [m for m in members if m]

def item_effort_days(item):
    start = item["timeline_start"] or item["start_date"] or item["due_date"]
    end = item["timeline_end"] or item["due_date"] or item["start_date"]
    if not start and not end:
        return 1
    if start and not end:
        end = start
    if end and not start:
        start = end
    return max(1, (end - start).days + 1)

def ensure_date(v):
    if isinstance(v, date):
        return v
    if isinstance(v, datetime):
        return v.date()
    return None

# ----------------------------
# UI: Sidebar (team & session)
# ----------------------------
ss_init()
tm = st.session_state["team_members"]

with st.sidebar:
    st.title("Team Boards")
    # current user
    member_names = [m["name"] for m in tm.values()]
    id_by_name = {m["name"]: m["id"] for m in tm.values()}
    sel_name = st.selectbox("You are", member_names, index=0 if member_names else None)
    if sel_name:
        st.session_state["current_user_id"] = id_by_name[sel_name]

    with st.expander("➕ Add teammate"):
        name = st.text_input("Name")
        email = st.text_input("Email")
        if st.button("Add member", use_container_width=True, type="secondary") and name and email:
            add_member(name, email)
            st.experimental_rerun()

    st.markdown("---")
    # Import / Export
    colx, coly = st.columns(2)
    with colx:
        data_blob = {
            "team_members": st.session_state["team_members"],
            "boards": st.session_state["boards"],
            "groups": st.session_state["groups"],
            "items": st.session_state["items"],
            "item_assignments": list(map(list, st.session_state["item_assignments"])),
            "item_dependencies": list(map(list, st.session_state["item_dependencies"])),
        }
        st.download_button("⬇️ Export JSON", data=pd.Series(data_blob).to_json(), file_name="boards_export.json", mime="application/json")
    with coly:
        up = st.file_uploader("⬆️ Import JSON", type=["json"])
        if up is not None:
            try:
                raw = up.read().decode("utf-8")
                blob = pd.read_json(raw, typ="series").to_dict()
                st.session_state["team_members"] = {k: dict(v) for k, v in blob["team_members"].items()}
                st.session_state["boards"] = {k: dict(v) for k, v in blob["boards"].items()}
                st.session_state["groups"] = {k: dict(v) for k, v in blob["groups"].items()}
                # date fields need parsing back to date
                items = {}
                for iid, v in blob["items"].items():
                    v = dict(v)
                    for key in ["start_date", "due_date", "timeline_start", "timeline_end"]:
                        if v.get(key):
                            v[key] = pd.to_datetime(v[key]).date()
                        else:
                            v[key] = None
                    items[iid] = v
                st.session_state["items"] = items
                st.session_state["item_assignments"] = set(map(tuple, blob["item_assignments"]))
                st.session_state["item_dependencies"] = set(map(tuple, blob["item_dependencies"]))
                st.success("Imported!")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Import failed: {e}")

# ----------------------------
# Board select / create
# ----------------------------
boards = st.session_state["boards"]
board_names = [b["name"] for b in boards.values()]
id_by_boardname = {b["name"]: b["id"] for b in boards.values()}

hdr = st.columns([3, 1, 1])
with hdr[0]:
    sel_board_name = st.selectbox("Board", board_names, index=0 if board_names else None, placeholder="Pick a board")
    current_board_id = id_by_boardname.get(sel_board_name)
    st.session_state["current_board_id"] = current_board_id
with hdr[1]:
    with st.popover("➕ New board"):
        nb = st.text_input("Board name")
        bd = st.text_area("Description")
        if st.button("Create board", use_container_width=True) and nb:
            bid = add_board(nb, bd)
            # default groups
            add_group(bid, "Backlog", 0)
            add_group(bid, "In Progress", 1)
            add_group(bid, "Done", 2)
            st.session_state["current_board_id"] = bid
            st.experimental_rerun()
with hdr[2]:
    if current_board_id and st.button("🧹Clear board items", use_container_width=True):
        # remove items & related edges
        to_del = [iid for iid, it in st.session_state["items"].items() if it["board_id"] == current_board_id]
        for iid in to_del:
            st.session_state["items"].pop(iid, None)
        st.session_state["item_assignments"] = {(i, u) for (i, u) in st.session_state["item_assignments"] if i not in to_del}
        st.session_state["item_dependencies"] = {(i, d) for (i, d) in st.session_state["item_dependencies"] if i not in to_del and d not in to_del}
        st.success("Board cleared.")

if not current_board_id:
    st.info("Create or pick a board to continue.")
    st.stop()

# Prefetch board-scoped data
groups = [g for g in st.session_state["groups"].values() if g["board_id"] == current_board_id]
groups = sorted(groups, key=lambda g: g["position"])
group_id_to_name = {g["id"]: g["name"] for g in groups}
items = [it for it in st.session_state["items"].values() if it["board_id"] == current_board_id]

# ----------------------------
# Tabs
# ----------------------------
tabs = st.tabs(["Table", "Kanban", "Timeline", "Workload", "My Work", "Admin"])

# ----------------------------
# TABLE TAB
# ----------------------------
with tabs[0]:
    st.subheader("Items")
    c1, c2 = st.columns([2, 3])

    # Create new item
    with c1:
        with st.form("new_item_form", border=True):
            t = st.text_input("Title")
            gname = st.selectbox("Group", [g["name"] for g in groups])
            s = st.selectbox("Status", STATUS_CHOICES, index=0)
            d1, d2 = st.columns(2)
            start = d1.date_input("Start date", value=None)
            due = d2.date_input("Due date", value=None)
            d3, d4 = st.columns(2)
            tstart = d3.date_input("Timeline start", value=None)
            tend = d4.date_input("Timeline end", value=None)
            owners = st.multiselect("Owners", [m["name"] for m in st.session_state["team_members"].values()])
            desc = st.text_area("Description", placeholder="Optional")
            if st.form_submit_button("Add item", type="primary") and t:
                gid = next(g["id"] for g in groups if g["name"] == gname)
                iid = add_item(current_board_id, gid, t, desc, s, ensure_date(start), ensure_date(due), ensure_date(tstart), ensure_date(tend), st.session_state["current_user_id"])
                # assignments
                for on in owners:
                    uid = next(uid for uid, mem in st.session_state["team_members"].items() if mem["name"] == on)
                    assign(iid, uid)
                st.success("Item added")
                st.experimental_rerun()

    # List / edit items
    with c2:
        q = st.text_input("Search", placeholder="title or description contains…")
        filtered = items
        if q:
            ql = q.lower()
            filtered = [it for it in items if ql in it["title"].lower() or ql in (it.get("description") or "").lower()]
        st.caption(f"{len(filtered)} items")
        for it in filtered:
            with st.expander(f"{it['title']}  ·  {group_id_to_name.get(it['group_id'], '')}  ·  {it['status']}", expanded=False):
                colA, colB, colC = st.columns([2, 2, 1])
                with colA:
                    new_title = st.text_input("Title", value=it["title"], key=f"title_{it['id']}")
                    new_desc = st.text_area("Description", value=it.get("description") or "", key=f"desc_{it['id']}")
                    gsel = st.selectbox("Group", [g["name"] for g in groups],
                                        index=[g["id"] for g in groups].index(it["group_id"]) if it["group_id"] in [g["id"] for g in groups] else 0,
                                        key=f"group_{it['id']}")
                with colB:
                    ssel = st.selectbox("Status", STATUS_CHOICES, index=STATUS_CHOICES.index(it["status"]), key=f"status_{it['id']}")
                    d1, d2 = st.columns(2)
                    st1 = d1.date_input("Start", value=it["start_date"], key=f"start_{it['id']}")
                    du1 = d2.date_input("Due", value=it["due_date"], key=f"due_{it['id']}")
                    d3, d4 = st.columns(2)
                    ts1 = d3.date_input("Timeline start", value=it["timeline_start"], key=f"ts_{it['id']}")
                    te1 = d4.date_input("Timeline end", value=it["timeline_end"], key=f"te_{it['id']}")
                with colC:
                    # owners
                    current_owners = [m["name"] for m in members_for_item(it["id"])]
                    all_names = [m["name"] for m in st.session_state["team_members"].values()]
                    own_sel = st.multiselect("Owners", all_names, default=current_owners, key=f"owners_{it['id']}")
                    # dependencies
                    others = [(o["title"], o["id"]) for o in items if o["id"] != it["id"]]
                    dep_current = [d for (i, d) in st.session_state["item_dependencies"] if i == it["id"]]
                    dep_names = [t for (t, oid) in others if oid in dep_current]
                    dep_sel = st.multiselect("Dependencies", [t for (t, _) in others], default=dep_names, key=f"deps_{it['id']}")

                colS, colX = st.columns([1,1])
                with colS:
                    if st.button("Save", key=f"save_{it['id']}", type="primary"):
                        it["title"] = new_title
                        it["description"] = new_desc
                        it["status"] = ssel
                        it["group_id"] = next(g["id"] for g in groups if g["name"] == gsel)
                        it["start_date"] = ensure_date(st1)
                        it["due_date"] = ensure_date(du1)
                        it["timeline_start"] = ensure_date(ts1)
                        it["timeline_end"] = ensure_date(te1)
                        # owners update
                        current_owner_ids = {u["id"] for u in members_for_item(it["id"])}
                        wanted_owner_ids = {uid for uid, mem in st.session_state["team_members"].items() if mem["name"] in own_sel}
                        for rm in current_owner_ids - wanted_owner_ids:
                            unassign(it["id"], rm)
                        for add in wanted_owner_ids - current_owner_ids:
                            assign(it["id"], add)
                        # deps update
                        dep_clear_for_item(it["id"])
                        for tname in dep_sel:
                            oid = next(oid for (tn, oid) in others if tn == tname)
                            dep_add(it["id"], oid)
                        st.success("Saved")
                        st.experimental_rerun()
                with colX:
                    if st.button("Delete", key=f"del_{it['id']}", type="secondary"):
                        # remove item and edges
                        st.session_state["items"].pop(it["id"], None)
                        st.session_state["item_assignments"] = {(i,u) for (i,u) in st.session_state["item_assignments"] if i != it["id"]}
                        st.session_state["item_dependencies"] = {(i,d) for (i,d) in st.session_state["item_dependencies"] if i != it["id"] and d != it["id"]}
                        st.warning("Deleted")
                        st.experimental_rerun()

# ----------------------------
# KANBAN TAB
# ----------------------------
with tabs[1]:
    st.subheader("Kanban")
    cols = st.columns(len(STATUS_CHOICES))
    for idx, lane in enumerate(STATUS_CHOICES):
        with cols[idx]:
            st.markdown(f"### {lane}")
            lane_items = [it for it in items if it["status"] == lane]
            # Sort by due date asc, None last
            lane_items.sort(key=lambda x: (x["due_date"] is None, x["due_date"]))
            for it in lane_items:
                blocked = item_is_blocked(it["id"])
                owners = ", ".join([m["name"] for m in members_for_item(it["id"])]) or "—"
                dd = it["due_date"].isoformat() if it["due_date"] else "—"
                st.write(f"**{it['title']}**")
                st.caption(f"Owners: {owners} • Due: {dd}" + (" • 🚫 Blocked" if blocked else ""))
                btn_label = f"Move → {next_status(lane)}"
                disabled = blocked and next_status(lane) in ("In progress", "Done")
                if st.button(btn_label, key=f"move_{it['id']}", disabled=disabled, use_container_width=True):
                    it["status"] = next_status(lane)
                    st.experimental_rerun()
                st.divider()

# ----------------------------
# TIMELINE TAB
# ----------------------------
with tabs[2]:
    st.subheader("Timeline / Gantt")
    if not items:
        st.info("No items yet.")
    else:
        df = []
        for it in items:
            start = it["timeline_start"] or it["start_date"] or it["due_date"]
            end = it["timeline_end"] or it["due_date"] or it["start_date"]
            if not start and not end:
                start = end = date.today()
            if start and not end:
                end = start
            if end and not start:
                start = end
            df.append({
                "Task": it["title"],
                "Start": pd.to_datetime(start),
                "Finish": pd.to_datetime(end),
                "Status": it["status"],
                "Group": group_id_to_name.get(it["group_id"], ""),
                "Blocked": "Blocked" if item_is_blocked(it["id"]) else "OK"
            })
        gdf = pd.DataFrame(df)
        fig = px.timeline(gdf, x_start="Start", x_end="Finish", y="Task", color="Status", hover_data=["Group","Blocked"])
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

# ----------------------------
# WORKLOAD TAB
# ----------------------------
with tabs[3]:
    st.subheader("Workload")
    if not items:
        st.info("No items yet.")
    else:
        # parameters
        c1, c2 = st.columns(2)
        with c1:
            start = st.date_input("From", value=date.today() - timedelta(days=14))
        with c2:
            end = st.date_input("To", value=date.today() + timedelta(days=28))
        if start > end:
            st.warning("Start must be before end.")
        else:
            # compute per-person load as task-days intersecting window
            rows = []
            date_range = pd.date_range(start, end, freq="D")
            for uid, m in st.session_state["team_members"].items():
                load = 0
                for it in items:
                    if (it["id"], uid) not in st.session_state["item_assignments"]:
                        continue
                    s = it["timeline_start"] or it["start_date"] or it["due_date"]
                    e = it["timeline_end"] or it["due_date"] or it["start_date"]
                    if not s and not e:
                        s = e = date.today()
                    if s and not e:
                        e = s
                    if e and not s:
                        s = e
                    # overlap
                    s = pd.to_datetime(s).date()
                    e = pd.to_datetime(e).date()
                    over = max(date(1970,1,1), min(e, end)) - max(s, start)
                    days = 0
                    if max(s, start) <= min(e, end):
                        days = (min(e, end) - max(s, start)).days + 1
                    load += max(0, days)
                rows.append({"Person": m["name"], "Task-days": load})
            wdf = pd.DataFrame(rows).sort_values("Task-days", ascending=False)
            st.dataframe(wdf, use_container_width=True)
            bar = px.bar(wdf, x="Person", y="Task-days")
            st.plotly_chart(bar, use_container_width=True)

# ----------------------------
# MY WORK TAB
# ----------------------------
with tabs[4]:
    st.subheader("My Work")
    uid = st.session_state["current_user_id"]
    if not uid:
        st.info("Select your user in the sidebar.")
    else:
        mine = [it for it in items if (it["id"], uid) in st.session_state["item_assignments"]]
        if not mine:
            st.info("Nothing assigned to you.")
        else:
            df = pd.DataFrame([
                {
                    "Title": it["title"],
                    "Status": it["status"],
                    "Group": group_id_to_name.get(it["group_id"], ""),
                    "Start": it["start_date"],
                    "Due": it["due_date"],
                } for it in mine
            ])
            st.dataframe(df, use_container_width=True)
            due_today = [it for it in mine if it["due_date"] == date.today()]
            if due_today:
                st.success(f"Due today: {', '.join([it['title'] for it in due_today])}")

# ----------------------------
# ADMIN TAB
# ----------------------------
with tabs[5]:
    st.subheader("Admin")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.write("➕ Add group")
        gname = st.text_input("Group name", key="admin_gname")
        gpos = st.number_input("Position", value=0, step=1, key="admin_gpos")
        if st.button("Create group", key="admin_add_group"):
            add_group(current_board_id, gname or "New Group", int(gpos))
            st.experimental_rerun()

    with c2:
        st.write("↕️ Reorder groups")
        order = st.multiselect("Drag-select order (top→bottom)", [g["name"] for g in groups], default=[g["name"] for g in groups])
        if st.button("Apply order", key="admin_order"):
            name_to_gid = {g["name"]: g["id"] for g in groups}
            for idx, name in enumerate(order):
                gid = name_to_gid[name]
                st.session_state["groups"][gid]["position"] = idx
            st.success("Order updated")
            st.experimental_rerun()

    with c3:
        st.write("🧪 Seed demo items")
        if st.button("Seed a few tasks", key="admin_seed"):
            g = groups[0]["id"] if groups else add_group(current_board_id, "Backlog", 0)
            for n in range(3):
                add_item(current_board_id, g, f"Task {n+1}", status="Not started")
            st.experimental_rerun()
