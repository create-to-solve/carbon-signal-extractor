SIGNAL_TYPES = {
    "rule_change": (
        "A normative rule, standard, regulation, or procedure has been "
        "officially adopted, amended, or revoked by an authoritative body."
    ),
    "decision_issued": (
        "A formal decision has been issued by COP, CMA, a supervisory body, "
        "a national regulator, or an equivalent authority. Distinct from "
        "rule_change in that it may be procedural, institutional, or "
        "directional rather than a change to a written rule."
    ),
    "consultation_open": (
        "A public comment period, stakeholder consultation, or call for input "
        "has been announced or is currently open. Strong leading indicator of "
        "an upcoming rule_change or decision_issued."
    ),
    "methodology_update": (
        "A carbon crediting methodology, protocol, or quantification approach "
        "has been approved, rejected, revised, suspended, or placed under "
        "review. Includes ICVCM CCP assessments of specific programs."
    ),
    "integrity_decision": (
        "A quality, claims, or integrity determination that affects the "
        "usability or credibility of carbon credits in the market. Includes "
        "VCMI Claims Code updates, ICVCM CCP-Eligible/Approved status changes, "
        "and registry-level quality label changes."
    ),
    "market_signal": (
        "Information about carbon credit pricing, trading volumes, registry "
        "issuance/retirement statistics, or market structure developments "
        "that affect supply, demand, or price discovery."
    ),
    "india_regulatory": (
        "A regulatory action, notification, clarification, or deadline "
        "specific to India's carbon market — BEE, CERC, MoEFCC, Ministry of "
        "Power, PIB, or the Indian Carbon Market / CCTS framework."
    ),
    "publication": (
        "A new report, guidance document, factsheet, working paper, or "
        "informational resource has been released. Use this when the signal "
        "is primarily about the existence of a new document rather than a "
        "rule or decision embedded within it."
    ),
}

TYPE_PRIORITY = [
    "rule_change",
    "decision_issued",
    "consultation_open",
    "integrity_decision",
    "methodology_update",
    "india_regulatory",
    "market_signal",
    "publication",
]
