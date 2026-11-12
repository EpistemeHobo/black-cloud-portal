"""Fixed lists shared by the API, the database and the frontend (via /api/meta).

Keys and stored values stay in English, so data and rules never depend on the
display language. What users see comes from the labels here and from
CHOICE_LABELS, which are in Thai.
"""

STEPS = {
    1: "ทำความเข้าใจปัญหา",
    2: "วางแผนและออกแบบ",
    3: "เขียนโค้ด",
    4: "ทดสอบ",
    5: "เผยแพร่ใช้งาน",
    6: "ดูแลและบำรุงรักษา",
    7: "ปรับปรุงและพัฒนาต่อ",
}

SYSTEM_TYPES = [
    "Web app", "Internal tool", "Platform", "SaaS",
    "Database", "Pipeline", "Script", "Infrastructure",
]

LIFECYCLE_STATES = ["Active", "Maintenance-only", "Deprecated", "Retired"]

ROLES = {
    "business_owner": "เจ้าของฝั่งธุรกิจ",
    "technical_owner": "เจ้าของฝั่งเทคนิค",
    "backup_owner": "ผู้ดูแลสำรอง",
    "developer": "นักพัฒนา",
    "support_contact": "ผู้ติดต่อฝ่ายสนับสนุน",
    "previous_owner": "เจ้าของเดิม",
}
# Roles whose holders may edit the system.
EDITOR_ROLES = {"business_owner", "technical_owner", "backup_owner", "developer"}
# Roles whose holders may open the system's secrets vault and see its leak alerts:
# the people who build it and the backup owner who takes it over. Not admins,
# auditors, support contacts or previous owners (docs/decisions/0009-secrets.md).
SECRET_ROLES = {"business_owner", "technical_owner", "backup_owner", "developer"}
# Roles that count towards the bus factor: people who can fix it.
BUS_FACTOR_ROLES = {"technical_owner", "backup_owner", "developer"}

LINK_KINDS = {
    "production_url": "URL ใช้งานจริง",
    "source_repo": "ที่เก็บซอร์สโค้ด",
    "logs": "Log ของระบบ",
    "dashboard": "แดชบอร์ดเฝ้าระวัง",
    "secrets": "ที่เก็บรหัสลับและค่าตั้งค่า",
    "brief": "สรุปโครงการ",
    "architecture": "สถาปัตยกรรม",
    "decision": "บันทึกการตัดสินใจ",
    "readme": "README",
    "test_plan": "แผนการทดสอบ",
    "runbook": "คู่มือการดูแลระบบ (Runbook)",
    "changelog": "บันทึกการเปลี่ยนแปลง",
    "other": "อื่น ๆ",
}

# The seven handover questions, in reading order (docs/handover-guide.md).
# can_be_empty: the writer may mark the question as having nothing to list.
GUIDE_QUESTIONS = [
    {"key": "what", "title": "ระบบนี้คืออะไร และถ้าล่มจะกระทบอะไร", "can_be_empty": False},
    {"key": "where", "title": "ของทุกอย่างอยู่ที่ไหน", "can_be_empty": False},
    {"key": "how", "title": "รัน ติดตั้ง และย้อนกลับอย่างไร", "can_be_empty": False},
    {"key": "watch", "title": "ต้องระวังอะไรบ้าง", "can_be_empty": True},
    {"key": "deps", "title": "พึ่งพาอะไร และใครใช้ระบบนี้", "can_be_empty": True},
    {"key": "who", "title": "ถามใครได้บ้าง", "can_be_empty": False},
    {"key": "progress", "title": "มีอะไรค้างอยู่บ้าง", "can_be_empty": True},
]
GUIDE_KEYS = {q["key"] for q in GUIDE_QUESTIONS}
EMPTYABLE_QUESTIONS = {q["key"] for q in GUIDE_QUESTIONS if q["can_be_empty"]}

# Markdown files attached to guide questions: accepted extensions and largest size.
DOC_EXTENSIONS = (".md", ".markdown")
DOC_MAX_CHARS = 200_000

WATCH_OUT_KINDS = {"trap": "ข้อควรระวัง", "chore": "งานที่ต้องทำเป็นประจำ"}
CHORE_FREQUENCIES = {"weekly": "ทุกสัปดาห์", "monthly": "ทุกเดือน", "yearly": "ทุกปี", "other": "อื่น ๆ"}
OPEN_ITEM_KINDS = {"work": "งานที่ยังไม่เสร็จ", "promise": "สิ่งที่สัญญาไว้", "decision": "เรื่องที่ยังไม่ได้ตัดสินใจ"}

CHECKLIST_STATUSES = {
    "done": "เสร็จแล้ว",
    "partly": "เสร็จบางส่วน",
    "missing": "ยังไม่มี",
    "not_applicable": "ไม่เกี่ยวข้อง",
}
# Statuses that count as finished in progress figures.
FINISHED_STATUSES = {"done", "not_applicable"}

CHECKLIST_LEVELS = ["required", "recommended"]

REVIEW_PLACES = ["Team meeting", "In the portal", "Other"]

# Technical debt (docs/technical_debt.md has the same fields for the portal's own).
DEBT_RISKS = ["High", "Medium", "Low"]
DEBT_STATUSES = {
    "open": "ยังไม่ได้แก้",
    "in_progress": "กำลังแก้",
    "paid_off": "แก้แล้ว",
    "wont_fix": "ตัดสินใจไม่แก้",
}
DEBT_CLOSED = {"paid_off", "wont_fix"}

# The secrets vault: which environment a secret is for.
SECRET_ENVIRONMENTS = ["All", "Dev", "Staging", "Prod"]

# How an owner closes a leak alert (like GitHub's secret scanning).
ALERT_RESOLUTIONS = {
    "revoked": "เปลี่ยนหรือยกเลิกรหัสนั้นแล้ว",
    "moved_to_vault": "ย้ายไปเก็บในตู้เซฟและลบออกจากข้อความแล้ว",
    "false_positive": "ไม่ใช่รหัสลับ (ตรวจผิด)",
    "used_in_tests": "เป็นค่าทดสอบ ไม่ใช่รหัสจริง",
    "wont_fix": "ยอมรับความเสี่ยง",
}
# Resolutions that say the text is not a secret: it is shown to everyone again.
NOT_SECRET_RESOLUTIONS = {"false_positive", "used_in_tests"}
ALERT_SEVERITIES = {"critical": "วิกฤต", "high": "สูง", "medium": "ปานกลาง"}

# Thai display labels for stored English values: system types, lifecycle
# states, review places, checklist levels and the choices in fields.py.
# A value missing here is shown as it is.
CHOICE_LABELS = {
    # System types
    "Web app": "เว็บแอป",
    "Internal tool": "เครื่องมือภายใน",
    "Platform": "แพลตฟอร์ม",
    "SaaS": "SaaS",
    "Database": "ฐานข้อมูล",
    "Pipeline": "ไปป์ไลน์",
    "Script": "สคริปต์",
    "Infrastructure": "โครงสร้างพื้นฐาน",
    # Lifecycle states
    "Active": "ใช้งานอยู่",
    "Maintenance-only": "บำรุงรักษาอย่างเดียว",
    "Deprecated": "กำลังเลิกใช้",
    "Retired": "ปลดระวางแล้ว",
    # Review places
    "Team meeting": "ประชุมทีม",
    "In the portal": "ในพอร์ทัล",
    "Other": "อื่น ๆ",
    # Checklist levels
    "required": "จำเป็น",
    "recommended": "แนะนำ",
    # Vault environments
    "All": "ทุกสภาพแวดล้อม",
    # Field choices (fields.py)
    "Unknown": "ไม่ทราบ",
    "In-house": "พัฒนาเอง",
    "Vendor": "บริษัทผู้ขาย",
    "Student": "นักศึกษา",
    "Contractor": "ผู้รับจ้าง",
    "Open-source": "โอเพนซอร์ส",
    "Internal only": "ภายในเท่านั้น",
    "Public": "สาธารณะ",
    "Partner-facing": "สำหรับหน่วยงานพันธมิตร",
    "Critical": "วิกฤต",
    "High": "สูง",
    "Medium": "ปานกลาง",
    "Low": "ต่ำ",
    "On-prem server": "เซิร์ฟเวอร์ภายในองค์กร",
    "On-prem Kubernetes": "Kubernetes ภายในองค์กร",
    "Cloud": "คลาวด์",
    "Desktop": "เดสก์ท็อป",
    "Yes": "มี",
    "No": "ไม่มี",
    "Partial": "บางส่วน",
    "Manual": "ทำด้วยมือ",
    "Container": "คอนเทนเนอร์",
    "Personal": "ข้อมูลส่วนบุคคล",
    "Health or patient": "ข้อมูลสุขภาพหรือผู้ป่วย",
    "Genomic": "ข้อมูลจีโนม",
    "Financial": "ข้อมูลการเงิน",
    "Research": "ข้อมูลงานวิจัย",
    "Internal": "ภายใน",
    "Confidential": "ลับ",
    "Restricted": "ลับมาก",
    "Local accounts": "บัญชีภายในระบบ",
    "Shared password": "รหัสผ่านใช้ร่วมกัน",
    "None": "ไม่มี",
    "Proprietary (in-house)": "กรรมสิทธิ์ของหน่วยงาน (พัฒนาเอง)",
    "Subscription": "สมัครสมาชิกรายปี/รายเดือน",
    "Perpetual": "ซื้อขาด",
    "Free tier": "รุ่นใช้ฟรี",
}
