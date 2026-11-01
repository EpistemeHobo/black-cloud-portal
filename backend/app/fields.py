"""Catalog info: a system's inventory details, grouped as the frontend shows them.

Auditors fill these in; developers are never asked to (docs/handover-guide.md).
The handover guide's own text fields are GUIDE_FIELDS at the end.

Follows the App & System Inventory form. Fields that became their own records
(owners, links, dependencies, owning unit) are not here. Every key must be a
column on models.System; a test checks this. Labels and help are in Thai; the
stored choice values stay in English (their Thai labels are in enums.CHOICE_LABELS).
"""

UNKNOWN = "Unknown"

# type: text | paragraph | choice | multi | date | number
# restricted: shown only to the system's editors and admins.
SECTIONS = [
    {
        "key": "about",
        "title": "ข้อมูลทั่วไป",
        "fields": [
            {"key": "aliases", "label": "ชื่ออื่น", "type": "text", "help": "ชื่อเล่นหรือชื่อย่อที่คนใช้เรียกจริง"},
            {"key": "developed_by", "label": "ผู้พัฒนา", "type": "choice",
             "choices": ["In-house", "Vendor", "Student", "Contractor", "Open-source", UNKNOWN]},
            {"key": "go_live_date", "label": "วันที่เริ่มใช้งานจริง", "type": "date"},
            {"key": "planned_retirement_date", "label": "วันที่วางแผนปลดระวาง", "type": "date"},
        ],
    },
    {
        "key": "users",
        "title": "ผู้ใช้และความสำคัญ",
        "fields": [
            {"key": "user_groups", "label": "กลุ่มผู้ใช้", "type": "text", "help": "ใครใช้งาน เช่น นักวิจัย เจ้าหน้าที่ธุรการ หน่วยงานพันธมิตร"},
            {"key": "user_count_estimate", "label": "จำนวนผู้ใช้โดยประมาณ", "type": "choice",
             "choices": ["1–10", "10–50", "50–200", "200+", UNKNOWN]},
            {"key": "internal_or_external", "label": "ใช้ภายในหรือภายนอก", "type": "choice",
             "choices": ["Internal only", "Public", "Partner-facing"]},
            {"key": "criticality", "label": "ความสำคัญ", "type": "choice",
             "choices": ["Critical", "High", "Medium", "Low", UNKNOWN]},
            {"key": "max_tolerable_downtime", "label": "เวลาหยุดทำงานสูงสุดที่ยอมรับได้", "type": "text", "help": "เช่น 4 ชั่วโมง, 1 วัน, 1 สัปดาห์"},
        ],
    },
    {
        "key": "technical",
        "title": "การสร้างและการติดตั้งใช้งาน",
        "fields": [
            {"key": "tech_stack", "label": "เทคโนโลยีที่ใช้", "type": "paragraph", "help": "ภาษาและเฟรมเวิร์ก พร้อมเวอร์ชันถ้าทราบ"},
            {"key": "hosting", "label": "ที่ติดตั้งระบบ", "type": "multi",
             "choices": ["HPC", "On-prem server", "On-prem Kubernetes", "Cloud", "SaaS", "Desktop"]},
            {"key": "server_or_location", "label": "เซิร์ฟเวอร์หรือตำแหน่ง", "type": "text", "restricted": True, "help": "ชื่อโฮสต์ VM เนมสเปซ หรือชื่อแอปบนคลาวด์"},
            {"key": "environments", "label": "สภาพแวดล้อม", "type": "multi", "choices": ["Dev", "Staging", "Prod"]},
            {"key": "ci_cd", "label": "CI/CD", "type": "choice", "choices": ["Yes", "No", "Partial", UNKNOWN]},
            {"key": "deployment_method", "label": "วิธีติดตั้งใช้งาน", "type": "choice",
             "choices": ["Manual", "Script", "Pipeline", "Container", UNKNOWN]},
            {"key": "database", "label": "ฐานข้อมูล", "type": "text", "help": "ประเภท เช่น PostgreSQL"},
            {"key": "integrations_apis", "label": "การเชื่อมต่อและ API", "type": "paragraph", "help": "API ภายนอก ฟีดข้อมูล และระบบอื่นที่แลกเปลี่ยนข้อมูลด้วย"},
        ],
    },
    {
        "key": "data",
        "title": "ข้อมูลและความปลอดภัย",
        "fields": [
            {"key": "data_types", "label": "ประเภทข้อมูล", "type": "multi",
             "choices": ["Personal", "Health or patient", "Genomic", "Financial", "Research", "Public"]},
            {"key": "data_classification", "label": "ระดับชั้นความลับของข้อมูล", "type": "choice",
             "choices": ["Public", "Internal", "Confidential", "Restricted", UNKNOWN]},
            {"key": "authentication", "label": "การยืนยันตัวตน", "type": "multi",
             "choices": ["SSO", "Local accounts", "Shared password", "None"]},
            {"key": "access_control", "label": "การควบคุมสิทธิ์เข้าถึง", "type": "paragraph", "help": "กำหนดสิทธิ์ตามบทบาทหรือไม่ ใครอนุมัติผู้ใช้ใหม่"},
            {"key": "data_storage_location", "label": "ที่จัดเก็บข้อมูล", "type": "text", "restricted": True},
            {"key": "data_leaves_org", "label": "ข้อมูลออกนอกองค์กรหรือไม่", "type": "text", "help": "ใช่หรือไม่ ถ้าใช่ ส่งไปที่ใด"},
            {"key": "backup", "label": "การสำรองข้อมูล", "type": "choice", "choices": ["Yes", "No", "Partial", UNKNOWN]},
            {"key": "backup_frequency_and_location", "label": "ความถี่และที่เก็บข้อมูลสำรอง", "type": "text", "restricted": True},
            {"key": "last_restore_test", "label": "ทดสอบกู้คืนข้อมูลครั้งล่าสุด", "type": "date"},
            {"key": "last_security_review", "label": "ตรวจสอบความปลอดภัยครั้งล่าสุด", "type": "date"},
            {"key": "known_vulnerabilities_or_risks", "label": "ช่องโหว่หรือความเสี่ยงที่ทราบ", "type": "paragraph", "restricted": True},
            {"key": "compliance_requirements", "label": "ข้อกำหนดที่ต้องปฏิบัติตาม", "type": "text", "help": "เช่น PDPA การรับรองจริยธรรมการวิจัย เงื่อนไขสัญญา"},
        ],
    },
    {
        "key": "cost",
        "title": "ค่าใช้จ่ายและสัญญา",
        "fields": [
            {"key": "license_type", "label": "ประเภทสัญญาอนุญาต", "type": "choice",
             "choices": ["Open-source", "Proprietary (in-house)", "Subscription", "Perpetual", "Free tier", UNKNOWN]},
            {"key": "annual_cost", "label": "ค่าใช้จ่ายต่อปี", "type": "text", "help": "จำนวนเงินและสกุลเงิน เช่น 120,000 บาท"},
            {"key": "contract_renewal_date", "label": "วันต่ออายุสัญญา", "type": "date"},
            {"key": "funding_source", "label": "แหล่งงบประมาณ", "type": "text", "help": "รหัสทุนหรือรหัสโครงการ"},
        ],
    },
    {
        "key": "state",
        "title": "สถานะปัจจุบัน",
        "fields": [
            {"key": "version", "label": "เวอร์ชัน", "type": "text"},
            {"key": "last_major_update", "label": "อัปเดตใหญ่ครั้งล่าสุด", "type": "date"},
        ],
    },
]

FIELDS = {f["key"]: f for s in SECTIONS for f in s["fields"]}
RESTRICTED_FIELDS = {k for k, f in FIELDS.items() if f.get("restricted")}

# Guide text fields, edited by the system's owners and developers.
GUIDE_FIELDS = {
    "description": {"label": "ระบบนี้ทำอะไร", "max": 2000},
    "if_down": {"label": "ถ้าระบบล่ม", "max": 2000},
    "run_steps": {"label": "รันบนเครื่องตัวเอง", "max": 5000},
    "deploy_steps": {"label": "ติดตั้งขึ้นระบบจริง", "max": 5000},
    "rollback_steps": {"label": "ย้อนกลับเมื่อมีปัญหา", "max": 5000},
}
