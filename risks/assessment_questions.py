ASSESSMENT_VERSION = "1.0"

RESPONSE_CHOICES = (
    ("in_place", "Yes, in place"),
    ("partly", "Partly"),
    ("not_in_place", "Not yet"),
    ("not_sure", "Not sure"),
)

ASSESSMENT_SECTIONS = (
    {
        "title": "Money and financial records",
        "description": "Check how well you can understand and plan your business finances.",
        "questions": (
            ("financial_records", "I keep accurate records of sales, costs, and money owed."),
            ("cashflow_forecast", "I know what bills are due and whether cash will cover the next month."),
            ("separate_finances", "I keep business and personal money separate."),
            ("debt_repayment", "I understand the cost and repayment dates of business borrowing."),
        ),
    },
    {
        "title": "Customers and sales",
        "description": "Consider what customers need and where sales depend on a small number of people or channels.",
        "questions": (
            ("customer_needs", "I understand who my customers are and what they value."),
            ("customer_concentration", "I know how much the business depends on its largest customer."),
            ("sales_tracking", "I track sales and respond to customer feedback."),
        ),
    },
    {
        "title": "Suppliers and daily operations",
        "description": "Think about the people, supplies, equipment, quality, and safety needed to serve customers.",
        "questions": (
            ("supplier_alternatives", "I have an alternative for an important supplier or input."),
            ("quality_safety", "I use basic quality and safety practices for my products or services."),
            ("equipment_maintenance", "Important tools and equipment are maintained and usable."),
            ("staff_backup", "Essential tasks are understood by someone other than one key person."),
        ),
    },
    {
        "title": "Permits and obligations",
        "description": "Consider local permits, licences, taxes, and records relevant to your business.",
        "questions": (
            ("permits_licences", "I know and keep up with required permits and licences."),
            ("tax_records", "I set aside money and keep records for tax and statutory obligations."),
        ),
    },
    {
        "title": "Payments and business information",
        "description": "Review how you protect digital payments and recover important business records.",
        "questions": (
            ("payment_security", "I protect payment accounts, PINs, and business devices."),
            ("record_backups", "I can recover important business records if they are lost."),
        ),
    },
    {
        "title": "Disruption and recovery",
        "description": "Think about how the business would respond to an interruption or a significant loss.",
        "questions": (
            ("continuity_plan", "I know what I would do if a disruption forced a temporary closure."),
            ("insurance_cover", "I have considered insurance for key business losses."),
        ),
    },
)

ASSESSMENT_QUESTION_KEYS = tuple(
    question_key
    for section in ASSESSMENT_SECTIONS
    for question_key, _ in section["questions"]
)
