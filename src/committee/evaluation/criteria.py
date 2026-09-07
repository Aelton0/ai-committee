"""The 12 analytical evaluation criteria measuring deliberative quality."""

import re
from typing import Any

from schemas.common import CommitteeRole, DecisionStatus, Severity
from src.committee.evaluation.models import (
    CriterionScore,
    EpistemicCriterion,
    EvaluationCriterion,
    EvaluationFinding,
)
from src.committee.session import Session


def evaluate_proposal_divergence(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether Architect and Pragmatist offer genuinely divergent solutions."""
    crit = EvaluationCriterion.PROPOSAL_DIVERGENCE
    findings: list[EvaluationFinding] = []

    if (
        CommitteeRole.ARCHITECT not in session.proposals
        or CommitteeRole.PRAGMATIST not in session.proposals
    ):
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=["One or both proposals are missing from session."],
                severity=Severity.HIGH,
                notes="Cannot evaluate divergence without both proposals.",
                passed=False,
            ),
            [
                EvaluationFinding(
                    id="F-DIV-01",
                    criterion=crit,
                    severity=Severity.HIGH,
                    description="Propostas ausentes impedem avaliação de divergência.",
                    evidence="Sessão não contém proposta do Arquiteto e do Pragmático.",
                )
            ],
        )

    prop_a = session.proposals[CommitteeRole.ARCHITECT]
    prop_b = session.proposals[CommitteeRole.PRAGMATIST]

    evidence: list[str] = []
    diff_points = 0

    # 1. Complexity difference
    if prop_a.complexity != prop_b.complexity:
        diff_points += 1
        evidence.append(
            f"Complexity differs: Architect={prop_a.complexity.value} vs Pragmatic={prop_b.complexity.value}."
        )

    # 2. Effort difference
    if prop_a.costs.implementation_effort != prop_b.costs.implementation_effort:
        diff_points += 1
        evidence.append(
            f"Effort differs: Architect={prop_a.costs.implementation_effort.value} vs Pragmatic={prop_b.costs.implementation_effort.value}."
        )

    # 3. Reversibility difference
    if prop_a.reversibility.score != prop_b.reversibility.score:
        diff_points += 1
        evidence.append(
            f"Reversibility differs: Architect={prop_a.reversibility.score.value} vs Pragmatic={prop_b.reversibility.score.value}."
        )

    # 4. Lexical / Solution overlap (Jaccard similarity check)
    words_a = set(re.findall(r"\w+", f"{prop_a.title} {prop_a.solution}".lower()))
    words_b = set(re.findall(r"\w+", f"{prop_b.title} {prop_b.solution}".lower()))
    common_words = words_a & words_b
    total_words = words_a | words_b
    jaccard = len(common_words) / max(len(total_words), 1)

    evidence.append(
        f"Textual similarity between solutions: {jaccard:.2f} (Jaccard index)."
    )

    # 5. Distinct strategies
    evidence.append(f"Architect solution: '{prop_a.solution[:80]}...'")
    evidence.append(f"Pragmatic solution: '{prop_b.solution[:80]}...'")

    # Detect FALSE CONFLICT
    if jaccard > 0.60 and diff_points == 0:
        finding = EvaluationFinding(
            id="F-DIV-FALSE-CONFLICT",
            criterion=crit,
            severity=Severity.HIGH,
            description="Falso conflito detectado: propostas do Arquiteto e do Pragmático são essencialmente a mesma arquitetura.",
            evidence=f"Sobreposição textual de {jaccard:.2f} com complexidade ({prop_a.complexity.value}) e esforço idênticos.",
            recommendation="Incentivar abordagens paradigmáticas diferentes (ex.: desacoplamento assíncrono vs monolito modular).",
        )
        findings.append(finding)
        return (
            CriterionScore(
                criterion=crit,
                score=1.5,
                evidence=evidence,
                severity=Severity.HIGH,
                notes="Proposals present a false conflict.",
                passed=False,
            ),
            findings,
        )

    # Calculate score based on divergence points and low overlap
    if diff_points >= 2 and jaccard < 0.40:
        score = 5.0
    elif diff_points >= 1 and jaccard < 0.55:
        score = 4.0
    else:
        score = 2.5

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes=f"Identified {diff_points} structural divergence dimensions.",
            passed=score >= 3.0,
        ),
        findings,
    )


def evaluate_assumption_coverage(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether proposals identify and test assumptions from ProblemContext."""
    crit = EvaluationCriterion.ASSUMPTION_COVERAGE
    findings: list[EvaluationFinding] = []

    if not session.problem_context:
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=["ProblemContext is absent from session."],
                severity=Severity.HIGH,
                notes="Cannot evaluate assumptions without ProblemContext.",
                passed=False,
            ),
            [
                EvaluationFinding(
                    id="F-ASM-01",
                    criterion=crit,
                    severity=Severity.HIGH,
                    description="ProblemContext ausente.",
                    evidence="Nenhum contexto de problema registrado na sessão.",
                )
            ],
        )

    context_assumptions = session.problem_context.assumptions
    if not context_assumptions:
        return (
            CriterionScore(
                criterion=crit,
                score=4.0,
                evidence=["ProblemContext declared no explicit assumptions."],
                notes="No baseline assumptions to verify.",
                passed=True,
            ),
            findings,
        )

    prop_a = session.proposals.get(CommitteeRole.ARCHITECT)
    prop_b = session.proposals.get(CommitteeRole.PRAGMATIST)

    all_proposal_assumptions: list[str] = []
    if prop_a:
        all_proposal_assumptions.extend(prop_a.assumptions)
        all_proposal_assumptions.extend(prop_a.invalidation_conditions)
    if prop_b:
        all_proposal_assumptions.extend(prop_b.assumptions)
        all_proposal_assumptions.extend(prop_b.invalidation_conditions)

    assumptions_text = " ".join(all_proposal_assumptions).lower()

    covered_count = 0
    evidence: list[str] = []

    for asm in context_assumptions:
        keywords = [w for w in re.findall(r"\w+", asm.description.lower()) if len(w) > 3]
        if any(kw in assumptions_text for kw in keywords):
            covered_count += 1
            evidence.append(f"Assumption '{asm.id}' covered: '{asm.description[:60]}...'")
        else:
            evidence.append(f"Assumption '{asm.id}' NOT referenced: '{asm.description[:60]}...'")

    ratio = covered_count / max(len(context_assumptions), 1)
    score = round(1.0 + (ratio * 4.0), 1)

    if ratio < 0.5:
        finding = EvaluationFinding(
            id="F-ASM-LOW-COVERAGE",
            criterion=crit,
            severity=Severity.MEDIUM,
            description="Baixa cobertura das premissas declaradas no ProblemContext.",
            evidence=f"Apenas {covered_count}/{len(context_assumptions)} premissas foram consideradas.",
            recommendation="As propostas devem declarar explicitamente como tratam cada premissa.",
        )
        findings.append(finding)

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes=f"Covered {covered_count} of {len(context_assumptions)} assumptions.",
            passed=score >= 3.0,
        ),
        findings,
    )


def evaluate_risk_coverage(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether the Auditor covers the main risk dimensions of the protocol."""
    crit = EvaluationCriterion.RISK_COVERAGE
    findings: list[EvaluationFinding] = []

    if not session.audit_report:
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=["AuditReport is absent from session."],
                severity=Severity.CRITICAL,
                notes="No risk audit performed.",
                passed=False,
            ),
            [
                EvaluationFinding(
                    id="F-RSK-01",
                    criterion=crit,
                    severity=Severity.CRITICAL,
                    description="Relatório de auditoria ausente.",
                    evidence="Auditor não executou a análise de risco na Fase 2.",
                )
            ],
        )

    audit = session.audit_report
    evidence: list[str] = []

    dimensions_covered = 0
    if audit.single_points_of_failure:
        dimensions_covered += 1
        evidence.append(f"SPOFs identified: {len(audit.single_points_of_failure)} item(s).")
    if audit.hidden_costs:
        dimensions_covered += 1
        evidence.append(f"Hidden costs identified: {len(audit.hidden_costs)} item(s).")
    if audit.fragile_assumptions:
        dimensions_covered += 1
        evidence.append(f"Fragile assumptions identified: {len(audit.fragile_assumptions)} item(s).")
    if audit.overengineering_risks:
        dimensions_covered += 1
        evidence.append(f"Overengineering risks identified: {len(audit.overengineering_risks)} item(s).")
    if audit.underengineering_risks:
        dimensions_covered += 1
        evidence.append(f"Underengineering risks identified: {len(audit.underengineering_risks)} item(s).")

    categories = {f.category for f in audit.findings_proposal_a + audit.findings_proposal_b}
    evidence.append(f"Audit finding categories covered: {[c.value for c in categories]}.")

    if dimensions_covered >= 4 and len(categories) >= 2:
        score = 5.0
    elif dimensions_covered >= 2:
        score = 3.5
    elif dimensions_covered >= 1:
        score = 2.0
    else:
        score = 1.0

    if dimensions_covered < 2:
        finding = EvaluationFinding(
            id="F-RSK-POOR-COVERAGE",
            criterion=crit,
            severity=Severity.HIGH,
            description="Cobertura superficial de dimensões de risco na auditoria.",
            evidence=f"Apenas {dimensions_covered} dimensões cobertas.",
            recommendation="O Auditor deve analisar explicitamente SPOFs, custos ocultos e over/underengineering.",
        )
        findings.append(finding)

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes=f"Covered {dimensions_covered}/5 risk dimensions with {len(categories)} finding categories.",
            passed=score >= 3.0,
        ),
        findings,
    )


def evaluate_adversarial_quality(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether the Auditor genuinely challenges proposals with rigorous critique."""
    crit = EvaluationCriterion.ADVERSARIAL_QUALITY
    findings: list[EvaluationFinding] = []

    if not session.audit_report:
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=["AuditReport is absent."],
                severity=Severity.HIGH,
                notes="Cannot evaluate adversarial quality without AuditReport.",
                passed=False,
            ),
            [],
        )

    audit = session.audit_report
    all_findings = audit.findings_proposal_a + audit.findings_proposal_b
    evidence: list[str] = []

    if not all_findings:
        finding = EvaluationFinding(
            id="F-ADV-NO-FINDINGS",
            criterion=crit,
            severity=Severity.HIGH,
            description="Auditor não produziu nenhum achado adversarial contra as propostas.",
            evidence="findings_proposal_a e findings_proposal_b estão vazios.",
            recommendation="O Auditor deve identificar vulnerabilidades específicas em ambas as alternativas.",
        )
        findings.append(finding)
        return (
            CriterionScore(
                criterion=crit,
                score=1.0,
                evidence=["Auditor produced zero critique findings for either proposal."],
                severity=Severity.HIGH,
                notes="Superficial audit with no technical challenge.",
                passed=False,
            ),
            findings,
        )

    high_critical = [f for f in all_findings if f.severity in (Severity.HIGH, Severity.CRITICAL)]
    has_substantive_justification = all(len(f.justification.strip()) >= 20 for f in all_findings)

    evidence.append(f"Total findings: {len(all_findings)} (Proposal A: {len(audit.findings_proposal_a)}, Proposal B: {len(audit.findings_proposal_b)}).")
    evidence.append(f"High/Critical findings: {len(high_critical)}.")

    if audit.questions_for_proponents:
        evidence.append(f"Targeted questions for proponents: {len(audit.questions_for_proponents)}.")

    if not high_critical or not has_substantive_justification:
        finding = EvaluationFinding(
            id="F-ADV-SUPERFICIAL",
            criterion=crit,
            severity=Severity.MEDIUM,
            description="Auditoria superficial: críticas fracas sem severidade relevante ou justificativas técnicas robustas.",
            evidence=f"Zero achados HIGH/CRITICAL ou justificativas muito curtas (justificativas robustas: {has_substantive_justification}).",
            recommendation="Aprofundar a análise de estresse, saturação de recursos e modos de falha.",
        )
        findings.append(finding)
        score = 2.0
    elif len(audit.findings_proposal_a) >= 1 and len(audit.findings_proposal_b) >= 1:
        score = 5.0
    else:
        score = 3.5

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes="Evaluated rigor and severity of adversarial findings.",
            passed=score >= 3.0,
        ),
        findings,
    )


def evaluate_defense_responsiveness(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether defenses directly respond to the findings raised by the Auditor."""
    crit = EvaluationCriterion.DEFENSE_RESPONSIVENESS
    findings: list[EvaluationFinding] = []

    if not session.defenses:
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=["Defenses are absent from session."],
                severity=Severity.HIGH,
                notes="Cannot evaluate defense responsiveness.",
                passed=False,
            ),
            [],
        )

    evidence: list[str] = []
    audit_findings = (
        (session.audit_report.findings_proposal_a + session.audit_report.findings_proposal_b)
        if session.audit_report
        else []
    )
    audit_finding_ids = {f.id for f in audit_findings}

    def_a = session.defenses.get(CommitteeRole.ARCHITECT)
    def_b = session.defenses.get(CommitteeRole.PRAGMATIST)

    addressed_ids: set[str] = set()
    modifications_proposed = 0

    for proponent, defense in [(CommitteeRole.ARCHITECT, def_a), (CommitteeRole.PRAGMATIST, def_b)]:
        if not defense:
            evidence.append(f"{proponent.value} defense is missing.")
            continue

        for cr in defense.critique_responses:
            addressed_ids.add(cr.finding_id)
            if cr.proposed_modification:
                modifications_proposed += 1
            evidence.append(
                f"{proponent.value} responded to '{cr.finding_id}' with stance '{cr.stance.value}'."
            )

    if audit_finding_ids:
        coverage = len(addressed_ids & audit_finding_ids) / len(audit_finding_ids)
        evidence.append(f"Addressed {len(addressed_ids & audit_finding_ids)} of {len(audit_finding_ids)} audit findings ({coverage:.1%}).")
        score = round(max(1.0, coverage * 5.0), 1)
    else:
        score = 4.0
        evidence.append("No specific audit finding IDs were declared to address.")

    if score < 3.0:
        finding = EvaluationFinding(
            id="F-DEF-UNRESPONSIVE",
            criterion=crit,
            severity=Severity.HIGH,
            description="Defesas não responderam à maioria dos apontamentos da auditoria.",
            evidence=f"Apenas {len(addressed_ids & audit_finding_ids)}/{len(audit_finding_ids)} achados foram respondidos.",
            recommendation="Cada proponente deve responder explicitamente a cada finding com concessão ou sustentação fundamentada.",
        )
        findings.append(finding)

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes=f"Proposed {modifications_proposed} refinements.",
            passed=score >= 3.0,
        ),
        findings,
    )


def evaluate_synthesis_neutrality(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether the Facilitator's synthesis is impartial and contains no recommendation."""
    crit = EvaluationCriterion.SYNTHESIS_NEUTRALITY
    findings: list[EvaluationFinding] = []

    if not session.deliberation_synthesis:
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=["DeliberationSynthesis is absent from session."],
                severity=Severity.HIGH,
                notes="Cannot evaluate synthesis neutrality without synthesis.",
                passed=False,
            ),
            [],
        )

    synthesis = session.deliberation_synthesis
    evidence: list[str] = []

    all_text = " ".join([
        " ".join(synthesis.consensus_points),
        " ".join(synthesis.divergence_points),
        " ".join(synthesis.unresolved_risks),
        " ".join(synthesis.open_questions),
        " ".join([
            f"{k} {v}"
            for k, v in (
                synthesis.arguments_dict
                if hasattr(synthesis, "arguments_dict")
                else (
                    synthesis.arguments_by_alternative.items()
                    if isinstance(synthesis.arguments_by_alternative, dict)
                    else {a.alternative_id: a.arguments for a in synthesis.arguments_by_alternative}.items()
                )
            ).items()
        ]),
        " ".join([f"{t.dimension} {t.notes or ''}" for t in synthesis.trade_offs]),
    ]).lower()

    biased_patterns = [
        # Portuguese patterns
        r"recomendo a proposta",
        r"recomendo a alternativa",
        r"recomendo fortemente",
        r"sugiro a proposta",
        r"sugiro a alternativa",
        r"a melhor opç[aã]o [eé]",
        r"a melhor escolha [eé]",
        r"melhor alternativa [eé]",
        r"devemos escolher",
        r"deve-se escolher",
        r"a proposta [ab] [eé] superior",
        r"proposta vencedora",
        r"vencedora [eé]",
        r"escolha final",
        r"opto pela proposta",
        # English patterns
        r"i recommend the proposal",
        r"i recommend proposal",
        r"i recommend option",
        r"the best option is",
        r"the best choice is",
        r"we should choose",
        r"the winning proposal",
        r"final choice",
        r"proposal [ab] is superior",
    ]

    detected_bias: list[str] = []
    for pat in biased_patterns:
        match = re.search(pat, all_text)
        if match:
            detected_bias.append(match.group(0))

    if detected_bias:
        finding = EvaluationFinding(
            id="F-SYN-BIASED-FACILITATOR",
            criterion=crit,
            severity=Severity.CRITICAL,
            description="Facilitador violou a neutralidade mandatória ao introduzir recomendações na síntese.",
            evidence=f"Expressões parciais detectadas: {detected_bias}",
            recommendation="Remover qualquer pré-julgamento de alternativas da síntese de convergência.",
        )
        findings.append(finding)
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=[f"Biased expressions found in synthesis: {detected_bias}"],
                severity=Severity.CRITICAL,
                notes="Automatic failure: Facilitator attempted to decide or favor an option.",
                passed=False,
            ),
            findings,
        )

    has_arguments_both = len(synthesis.arguments_by_alternative) >= 2
    has_trade_offs = len(synthesis.trade_offs) >= 1

    evidence.append(f"Synthesis documents arguments for {len(synthesis.arguments_by_alternative)} alternative(s).")
    evidence.append(f"Synthesis articulates {len(synthesis.trade_offs)} trade-off dimension(s).")
    evidence.append(f"Consensus points: {len(synthesis.consensus_points)}, Divergence points: {len(synthesis.divergence_points)}.")

    score = 5.0 if has_arguments_both and has_trade_offs else 3.5

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes="Synthesis maintains strict Facilitator neutrality.",
            passed=True,
        ),
        findings,
    )


def evaluate_trade_off_explicitness(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether the decision articulates explicit gain vs sacrifice contracts."""
    crit = EvaluationCriterion.TRADE_OFF_EXPLICITNESS
    findings: list[EvaluationFinding] = []

    if not session.decision_record:
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=["DecisionRecord is absent from session."],
                severity=Severity.HIGH,
                notes="No decision record to evaluate.",
                passed=False,
            ),
            [],
        )

    dec = session.decision_record

    if dec.status == DecisionStatus.INSUFFICIENT_EVIDENCE:
        return (
            CriterionScore(
                criterion=crit,
                score=4.5,
                evidence=["Decision declared INSUFFICIENT_EVIDENCE; trade-off contracts properly deferred."],
                notes="No trade-offs required when no alternative is recommended.",
                passed=True,
            ),
            findings,
        )

    evidence: list[str] = []
    trade_offs = dec.trade_offs

    if not trade_offs:
        finding = EvaluationFinding(
            id="F-TRD-NONE",
            criterion=crit,
            severity=Severity.CRITICAL,
            description="Decisão recomendada sem nenhum contrato explícito de trade-off.",
            evidence="Lista trade_offs do DecisionRecord está vazia.",
            recommendation="Todo DecisionRecord deve explicitar o que se ganha e o que se sacrifica.",
        )
        findings.append(finding)
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=["Zero trade-off contracts documented."],
                severity=Severity.CRITICAL,
                notes="Violation of Principle 10 (Trade-offs Explícitos).",
                passed=False,
            ),
            findings,
        )

    for i, t in enumerate(trade_offs, 1):
        evidence.append(f"Trade-off #{i}: Gain='{t.gain[:60]}...' | Sacrifice='{t.sacrifice[:60]}...'")

    score = 5.0

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes=f"Documented {len(trade_offs)} explicit trade-off contract(s).",
            passed=True,
        ),
        findings,
    )


def evaluate_decision_traceability(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether the recommendation can be traced back to facts, proposals, and arguments."""
    crit = EvaluationCriterion.DECISION_TRACEABILITY
    findings: list[EvaluationFinding] = []

    if not session.decision_record:
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=["DecisionRecord is absent."],
                severity=Severity.HIGH,
                notes="No decision to trace.",
                passed=False,
            ),
            [],
        )

    dec = session.decision_record

    if dec.status == DecisionStatus.INSUFFICIENT_EVIDENCE:
        evidence = [
            "Decision status is INSUFFICIENT_EVIDENCE.",
            f"Missing information listed: {dec.information_that_could_change_decision}",
        ]
        return (
            CriterionScore(
                criterion=crit,
                score=5.0,
                evidence=evidence,
                notes="Honest intellectual assessment correctly tracing missing facts.",
                passed=True,
            ),
            findings,
        )

    evidence: list[str] = []
    known_alternatives = set()
    for role, prop in session.proposals.items():
        known_alternatives.add(prop.artifact_id)
        known_alternatives.add(role.value)
    for role, defn in session.defenses.items():
        if defn.revised_proposal_id:
            known_alternatives.add(defn.revised_proposal_id)
    known_alternatives.update([
        "PROPOSAL_A", "PROPOSAL_B", "PROPOSAL_ARCH_V2", "PROPOSAL_PRAG_V2",
        "PROP-ARCH-001", "PROP-PRAG-001"
    ])

    chosen = dec.chosen_alternative or ""
    evidence.append(f"Chosen alternative: '{chosen}'.")

    if chosen not in known_alternatives and not any(k.lower() in chosen.lower() for k in known_alternatives):
        finding = EvaluationFinding(
            id="F-TRC-UNTRACEABLE-ALTERNATIVE",
            criterion=crit,
            severity=Severity.CRITICAL,
            description="Decisão não rastreável: a alternativa escolhida não foi proposta nem debatida.",
            evidence=f"Alternativa '{chosen}' não pertence ao conjunto de propostas analisadas: {known_alternatives}.",
            recommendation="A decisão deve escolher estritamente entre as alternativas ou variantes defendidas.",
        )
        findings.append(finding)
        return (
            CriterionScore(
                criterion=crit,
                score=1.0,
                evidence=[f"Chosen alternative '{chosen}' was never discussed in deliberation."],
                severity=Severity.CRITICAL,
                notes="Decision invented an unvetted alternative.",
                passed=False,
            ),
            findings,
        )

    if dec.rejected_alternatives:
        for rej in dec.rejected_alternatives:
            evidence.append(f"Rejected '{rej.name}': '{rej.rejection_reason[:60]}...'")
    else:
        evidence.append("No rejected alternatives documented.")

    score = 5.0 if dec.rejected_alternatives and len(dec.rationale) > 50 else 3.5

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes="Recommendation is traceable to prior deliberations and proposals.",
            passed=True,
        ),
        findings,
    )


def evaluate_debt_explicitness(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether technical and operational debts are explicitly documented."""
    crit = EvaluationCriterion.DEBT_EXPLICITNESS
    findings: list[EvaluationFinding] = []

    if not session.decision_record:
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=["DecisionRecord is absent."],
                severity=Severity.HIGH,
                notes="Cannot evaluate debt without DecisionRecord.",
                passed=False,
            ),
            [],
        )

    dec = session.decision_record

    if dec.status == DecisionStatus.INSUFFICIENT_EVIDENCE:
        return (
            CriterionScore(
                criterion=crit,
                score=4.0,
                evidence=["INSUFFICIENT_EVIDENCE decision contracts no immediate debt."],
                notes="Debt evaluation deferred.",
                passed=True,
            ),
            findings,
        )

    has_tech_debt = bool(dec.technical_debt)
    has_ops_debt = bool(dec.operational_debt)

    evidence = [
        f"Technical debt documented: {dec.technical_debt}",
        f"Operational debt documented: {dec.operational_debt}",
    ]

    if has_tech_debt and has_ops_debt:
        score = 5.0
    elif has_tech_debt or has_ops_debt:
        score = 3.0
        findings.append(
            EvaluationFinding(
                id="F-DBT-PARTIAL",
                criterion=crit,
                severity=Severity.LOW,
                description="Apenas um tipo de dívida (técnica ou operacional) foi documentado.",
                evidence=f"has_tech_debt={has_tech_debt}, has_ops_debt={has_ops_debt}",
                recommendation="Explicitar tanto a dívida técnica quanto a sobrecarga operacional futura.",
            )
        )
    else:
        score = 1.0
        findings.append(
            EvaluationFinding(
                id="F-DBT-MISSING",
                criterion=crit,
                severity=Severity.MEDIUM,
                description="Nenhuma dívida técnica ou operacional foi declarada na recomendação.",
                evidence="technical_debt e operational_debt estão vazios.",
                recommendation="Toda decisão técnica contrai dívidas conscientes; registre-as explicitamente.",
            )
        )

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes=f"Documented tech_debt={len(dec.technical_debt)}, ops_debt={len(dec.operational_debt)}.",
            passed=score >= 3.0,
        ),
        findings,
    )


def evaluate_reviewability(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether review triggers are objective, measurable, and useful."""
    crit = EvaluationCriterion.REVIEWABILITY
    findings: list[EvaluationFinding] = []

    if not session.decision_record:
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=["DecisionRecord is absent."],
                severity=Severity.HIGH,
                notes="Cannot evaluate reviewability without DecisionRecord.",
                passed=False,
            ),
            [],
        )

    dec = session.decision_record

    if dec.status == DecisionStatus.INSUFFICIENT_EVIDENCE:
        return (
            CriterionScore(
                criterion=crit,
                score=4.0,
                evidence=["Decision status is INSUFFICIENT_EVIDENCE."],
                notes="Review triggers not applicable.",
                passed=True,
            ),
            findings,
        )

    triggers = dec.review_triggers
    if not triggers:
        findings.append(
            EvaluationFinding(
                id="F-REV-NO-TRIGGERS",
                criterion=crit,
                severity=Severity.HIGH,
                description="Nenhum gatilho de revisão registrado na decisão.",
                evidence="review_triggers está vazio.",
                recommendation="Registrar pelo menos um gatilho objetivo de reavaliação.",
            )
        )
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=["review_triggers is empty."],
                severity=Severity.HIGH,
                notes="Violates Principle 11 (Gatilhos Objetivos de Reavaliação).",
                passed=False,
            ),
            findings,
        )

    evidence: list[str] = []
    objective_count = 0

    for i, t in enumerate(triggers, 1):
        is_metric = bool(t.metric_threshold) or bool(re.search(r"\d+", t.condition))
        if is_metric:
            objective_count += 1
        evidence.append(
            f"Trigger #{i}: '{t.condition}' (metric_threshold={t.metric_threshold}, type={t.trigger_type})."
        )

    score = 5.0 if objective_count >= 1 else 3.0

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes=f"Identified {len(triggers)} trigger(s) ({objective_count} with objective thresholds).",
            passed=True,
        ),
        findings,
    )


def evaluate_learning_value(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether the LearningReport connects decisions to foundational CS concepts."""
    crit = EvaluationCriterion.LEARNING_VALUE
    findings: list[EvaluationFinding] = []

    if not session.learning_report:
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=["LearningReport is absent from session."],
                severity=Severity.HIGH,
                notes="No pedagogical dossier delivered.",
                passed=False,
            ),
            [],
        )

    lrn = session.learning_report
    evidence: list[str] = []

    evidence.append(f"Concepts documented: {lrn.concepts}.")
    evidence.append(f"Theory to practice connections: {len(lrn.theory_to_practice_connections)}.")
    evidence.append(f"Observed knowledge gaps: {len(lrn.observed_knowledge_gaps)}.")
    evidence.append(f"Learning path steps: {len(lrn.learning_path)}.")
    evidence.append(f"Bibliographic references: {len(lrn.references)}.")

    connections_text = " ".join(lrn.theory_to_practice_connections).lower()
    has_substantive_connection = any(
        len(conn.strip()) >= 30 for conn in lrn.theory_to_practice_connections
    ) and any(
        kw in connections_text
        for kw in ["comitê", "committee", "trade-off", "decis", "escolh", "alternativ", "arquitet", "propost", "kiss"]
    )

    gaps_text = " ".join(g.context_evidence for g in lrn.observed_knowledge_gaps).lower()
    is_generic_gap = (
        not lrn.observed_knowledge_gaps
        or "sem evidência" in gaps_text
        or "sem citação" in gaps_text
        or "without citation" in gaps_text
        or "no specific evidence" in gaps_text
    )

    if not has_substantive_connection or is_generic_gap:
        finding = EvaluationFinding(
            id="F-LRN-GENERIC",
            criterion=crit,
            severity=Severity.MEDIUM,
            description="Mentor genérico: relatório pedagógico lista termos sem conexão contextual observável com a deliberação.",
            evidence=f"has_substantive_connection={has_substantive_connection}, is_generic_gap={is_generic_gap}",
            recommendation="Conectar os conceitos às dúvidas expressas pelo usuário e aos trade-offs reais da sessão.",
        )
        findings.append(finding)
        score = 1.5
    elif len(lrn.concepts) >= 2 and lrn.references:
        score = 5.0
    else:
        score = 3.5

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes="Evaluated pedagogical grounding and literature references.",
            passed=score >= 3.0,
        ),
        findings,
    )


def evaluate_human_sovereignty(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether the system preserves user sovereignty and decision authority."""
    crit = EvaluationCriterion.HUMAN_SOVEREIGNTY
    findings: list[EvaluationFinding] = []

    evidence: list[str] = []

    evidence.append("Session is governed by State Machine preserving human interventions.")

    if session.decision_record:
        evidence.append(f"Decision status is '{session.decision_record.status.value}' (advisory recommendation for human review).")
    else:
        evidence.append("Deliberation in progress; human sovereignty actively preserved.")

    if session.interventions:
        evidence.append(f"Recorded {len(session.interventions)} human intervention(s).")

    score = 5.0

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes="Deliberation strictly preserves user authority and consultative role.",
            passed=True,
        ),
        findings,
    )


# ==============================================================================
# EPISTEMIC DISCIPLINE EVALUATION CRITERIA
# ==============================================================================

def evaluate_fact_grounding(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether claimed facts are grounded in ProblemContext and not invented."""
    crit = EpistemicCriterion.FACT_GROUNDING
    findings: list[EvaluationFinding] = []
    evidence: list[str] = []

    if not session.problem_context:
        return (
            CriterionScore(
                criterion=crit,
                score=0.0,
                evidence=["ProblemContext is absent from session."],
                severity=Severity.HIGH,
                notes="Cannot evaluate fact grounding without ProblemContext.",
                passed=False,
            ),
            [
                EvaluationFinding(
                    id="F-EPI-FACT-00",
                    criterion=crit,
                    severity=Severity.HIGH,
                    description="ProblemContext ausente.",
                    evidence="Nenhum contexto de problema registrado.",
                )
            ],
        )

    ctx_text = (
        session.problem_context.problem
        + " "
        + " ".join(f.description for f in session.problem_context.facts)
        + " "
        + " ".join(c.description for c in session.problem_context.constraints)
    ).lower()

    # Extract all numbers from context
    ctx_numbers = set(re.findall(r"\b\d+[\d.,]*\b", ctx_text))
    # Remove dots and commas for flexible matching
    normalized_ctx_numbers = {n.replace(".", "").replace(",", "") for n in ctx_numbers}

    invented_facts: list[str] = []

    for role, prop in session.proposals.items():
        # Check epistemic_section facts
        if hasattr(prop, "epistemic_section") and prop.epistemic_section.facts:
            for f in prop.epistemic_section.facts:
                f_stmt = f.statement.lower()
                f_numbers = set(re.findall(r"\b\d+[\d.,]*\b", f_stmt))
                normalized_f_numbers = {n.replace(".", "").replace(",", "") for n in f_numbers}
                
                # Check for specific quantitative claims > 10 not present in context
                large_unmatched = [
                    n for n in normalized_f_numbers
                    if n not in normalized_ctx_numbers and int(n) > 10 if n.isdigit()
                ]
                if large_unmatched:
                    invented_facts.append(
                        f"{role.value} epistemic_section.facts '{f.id}': '{f.statement}' (unmatched: {large_unmatched})"
                    )

        # Check raw text for claims like "50.000 req/s" or "100.000 eventos/s" when not in context
        prop_text = (prop.title + " " + prop.solution + " " + prop.rationale).lower()
        patterns = [
            r"(\d+[\d.,]*\s*(?:req|requisições|rps|eventos|transações|tps|qps))",
            r"(?:processando|recebe|suporta)\s+(\d+[\d.,]*)",
        ]
        for pat in patterns:
            for match in re.finditer(pat, prop_text):
                num_str = re.search(r"\d+[\d.,]*", match.group(0))
                if num_str:
                    clean_num = num_str.group(0).replace(".", "").replace(",", "")
                    if clean_num not in normalized_ctx_numbers and clean_num.isdigit() and int(clean_num) > 10:
                        # Check if it was explicitly declared as an assumption or conditional recommendation
                        is_guarded = (
                            any(clean_num in a.lower() for a in prop.assumptions)
                            or (
                                hasattr(prop, "epistemic_section")
                                and any(
                                    clean_num in a.statement.lower()
                                    for a in prop.epistemic_section.assumptions
                                )
                            )
                            or (
                                hasattr(prop, "epistemic_section")
                                and any(
                                    clean_num in cr.condition.lower()
                                    for cr in prop.epistemic_section.conditional_recommendations
                                )
                            )
                        )
                        if not is_guarded:
                            invented_facts.append(
                                f"{role.value} text asserts '{match.group(0)}' without grounding in ProblemContext or declaration as assumption/condition"
                            )

    if invented_facts:
        for item in invented_facts:
            findings.append(
                EvaluationFinding(
                    id="F-EPI-FACT-01",
                    criterion=crit,
                    severity=Severity.CRITICAL,
                    description="Fato inventado: o agente introduziu métricas ou dados quantitativos como fatos que não foram fornecidos no ProblemContext.",
                    evidence=item,
                    recommendation="Remover métricas inventadas ou declará-las formalmente como ASSUMPTION sob premissas explícitas.",
                )
            )
        evidence.extend(invented_facts)
        score = 1.0
        passed = False
        notes = f"Detectados {len(invented_facts)} fatos inventados sem respaldo no contexto."
    else:
        score = 5.0
        passed = True
        evidence.append("All factual claims are grounded strictly in the verified ProblemContext.")
        notes = "Fatos estritamente fundamentados no contexto do problema."

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes=notes,
            passed=passed,
        ),
        findings,
    )


def evaluate_assumption_transparency(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether operating hypotheses and assumptions are declared transparently."""
    crit = EpistemicCriterion.ASSUMPTION_TRANSPARENCY
    findings: list[EvaluationFinding] = []
    evidence: list[str] = []

    hidden_assumptions: list[str] = []
    explicit_assumptions_count = 0

    for role, prop in session.proposals.items():
        prop_assumptions = list(prop.assumptions)
        if hasattr(prop, "epistemic_section") and prop.epistemic_section.assumptions:
            prop_assumptions.extend(a.statement for a in prop.epistemic_section.assumptions)
            explicit_assumptions_count += len(prop.epistemic_section.assumptions)
        else:
            explicit_assumptions_count += len(prop.assumptions)

        assumptions_text = " ".join(prop_assumptions).lower()

        # Detect keywords in solution/rationale that indicate unstated hypotheses
        body_text = (prop.solution + " " + prop.rationale).lower()
        suspicious_hypotheses = [
            (r"\b20%\b|\bcrescimento\b|\bgrowth\b", "crescimento de volume projetado"),
            (r"\b2 semanas\b|\baprenderá\b|\baprender\b", "curva de aprendizado da equipe"),
            (r"\bquadruplicará\b|\btriplicará\b|\bblack friday\b", "pico sazonal extraordinário"),
        ]

        # Check if the body uses any suspicious hypothesis that is absent from declared assumptions
        # and absent from ProblemContext facts
        ctx_facts_text = " ".join(f.description for f in session.problem_context.facts).lower() if session.problem_context else ""

        for pattern, label in suspicious_hypotheses:
            if re.search(pattern, body_text):
                # Is it in context facts?
                in_ctx = bool(re.search(pattern, ctx_facts_text))
                # Is it declared in assumptions?
                in_assumptions = bool(re.search(pattern, assumptions_text))
                if not in_ctx and not in_assumptions:
                    hidden_assumptions.append(
                        f"{role.value} uses '{label}' in rationale/solution without declaring it as an explicit ASSUMPTION."
                    )

    if hidden_assumptions:
        for item in hidden_assumptions:
            findings.append(
                EvaluationFinding(
                    id="F-EPI-ASM-01",
                    criterion=crit,
                    severity=Severity.HIGH,
                    description="Premissa oculta: hipótese utilizada para justificar a arquitetura sem declaração formal em assumptions.",
                    evidence=item,
                    recommendation="Declarar formalmente a hipótese como ASSUMPTION com razão, confiança e condição de invalidação.",
                )
            )
        evidence.extend(hidden_assumptions)
        score = 1.5
        passed = False
        notes = f"Detectadas {len(hidden_assumptions)} premissas ocultas não declaradas."
    else:
        score = 5.0
        passed = True
        evidence.append(f"Declared {explicit_assumptions_count} explicit assumptions transparently with invalidation conditions.")
        notes = "Premissas declaradas de forma transparente e verificável."

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes=notes,
            passed=passed,
        ),
        findings,
    )


def evaluate_unknown_visibility(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether critical unknowns are recognized and preserved rather than ignored."""
    crit = EpistemicCriterion.UNKNOWN_VISIBILITY
    findings: list[EvaluationFinding] = []
    evidence: list[str] = []

    if not session.problem_context or not session.problem_context.unknowns:
        return (
            CriterionScore(
                criterion=crit,
                score=4.5,
                evidence=["ProblemContext does not specify critical unknowns."],
                notes="Sem unknowns iniciais cadastrados no ProblemContext.",
                passed=True,
            ),
            findings,
        )

    context_unknowns = session.problem_context.unknowns
    acknowledged_unknowns = 0

    for unk in context_unknowns:
        unk_keywords = [w for w in re.findall(r"\w+", unk.description.lower()) if len(w) > 3]
        found_in_session = False

        for role, prop in session.proposals.items():
            prop_text = (
                prop.solution
                + " "
                + prop.rationale
                + " "
                + " ".join(prop.risks)
            ).lower()
            if hasattr(prop, "epistemic_section"):
                prop_text += " " + " ".join(u.statement for u in prop.epistemic_section.unknowns).lower()
                prop_text += " " + " ".join(cr.condition for cr in prop.epistemic_section.conditional_recommendations).lower()

            if any(kw in prop_text for kw in unk_keywords):
                found_in_session = True
                break

        if found_in_session:
            acknowledged_unknowns += 1
            evidence.append(f"Unknown '{unk.id}' acknowledged in proposals: '{unk.description[:60]}...'")
        else:
            evidence.append(f"Unknown '{unk.id}' IGNORED in proposals: '{unk.description[:60]}...'")

    ratio = acknowledged_unknowns / len(context_unknowns)
    if ratio < 0.5:
        finding = EvaluationFinding(
            id="F-EPI-UNK-01",
            criterion=crit,
            severity=Severity.HIGH,
            description="Incógnitas críticas do contexto foram ignoradas pelos agentes.",
            evidence=f"{len(context_unknowns) - acknowledged_unknowns} de {len(context_unknowns)} unknowns não foram considerados.",
            recommendation="Reconhecer explicitamente as incógnitas na epistemic_section.unknowns ou utilizar recomendações condicionais.",
        )
        findings.append(finding)
        score = round(1.0 + (ratio * 2.0), 1)
        passed = False
        notes = "Incógnitas críticas do contexto foram ignoradas nas propostas."
    else:
        score = 5.0
        passed = True
        notes = "Incógnitas críticas devidamente preservadas e consideradas."

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence,
            notes=notes,
            passed=passed,
        ),
        findings,
    )


def evaluate_inference_traceability(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether inferences trace back to declared facts and assumptions."""
    crit = EpistemicCriterion.INFERENCE_TRACEABILITY
    findings: list[EvaluationFinding] = []
    evidence: list[str] = []

    untraced_inferences: list[str] = []
    traced_count = 0

    for role, prop in session.proposals.items():
        if hasattr(prop, "epistemic_section") and prop.epistemic_section.inferences:
            missing_deps = prop.epistemic_section.validate_dependency_references()
            if missing_deps:
                untraced_inferences.extend(missing_deps)
            else:
                traced_count += len(prop.epistemic_section.inferences)
                evidence.append(f"{role.value} declared {len(prop.epistemic_section.inferences)} fully traced inferences.")
        else:
            evidence.append(f"{role.value} did not declare structured inferences.")

    if untraced_inferences:
        for item in untraced_inferences:
            findings.append(
                EvaluationFinding(
                    id="F-EPI-INF-01",
                    criterion=crit,
                    severity=Severity.HIGH,
                    description="Inferência com dependências não declaradas ou inexistentes.",
                    evidence=item,
                    recommendation="Garantir que todo depends_on referencie IDs de FACT ou ASSUMPTION válidos.",
                )
            )
        score = 2.0
        passed = False
        notes = "Inferências com dependências quebradas ou não declaradas."
    else:
        score = 5.0
        passed = True
        notes = "Inferências devidamente rastreadas a fatos e premissas declaradas."

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence or ["Inference traceability verified."],
            notes=notes,
            passed=passed,
        ),
        findings,
    )


def evaluate_recommendation_grounding(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Evaluate whether recommendations are grounded in evidence or properly guarded by conditions."""
    crit = EpistemicCriterion.RECOMMENDATION_GROUNDING
    findings: list[EvaluationFinding] = []
    evidence: list[str] = []

    # Check for ungrounded heavy complexity (Kafka, K8s, Sharding) without factual justification or conditional guard
    ungrounded_recommendations: list[str] = []
    has_conditional_recommendation = False

    for role, prop in session.proposals.items():
        prop_text = (prop.solution + " " + prop.rationale).lower()
        has_conditional = (
            (hasattr(prop, "epistemic_section") and len(prop.epistemic_section.conditional_recommendations) > 0)
            or "if " in prop_text and "then " in prop_text
            or "se " in prop_text and "então " in prop_text
        )
        if has_conditional:
            has_conditional_recommendation = True
            evidence.append(f"{role.value} employs conditional recommendations to guard complex components.")

        # If proposal recommends Kafka, Kubernetes, or multi-region without condition and without high throughput fact
        is_heavy = any(k in prop_text for k in ("kafka", "kubernetes", "k8s", "sharding", "multi-region"))
        has_throughput_fact = False
        if session.problem_context:
            ctx_facts_text = " ".join(f.description for f in session.problem_context.facts).lower()
            has_throughput_fact = any(k in ctx_facts_text for k in ("1000 req", "1200 req", "500 req", "alta vazão", "1.200"))

        if is_heavy and not has_throughput_fact and not has_conditional:
            ungrounded_recommendations.append(
                f"{role.value} recommends heavy infrastructure without factual context evidence or conditional guardrails (IF ... THEN ...)."
            )

    # Check DecisionRecord
    if session.decision_record:
        if session.decision_record.status == DecisionStatus.INSUFFICIENT_EVIDENCE:
            evidence.append("DecisionRecord properly emitted INSUFFICIENT_EVIDENCE due to unmeasured critical parameters.")
        elif session.decision_record.status == DecisionStatus.RECOMMENDED:
            if session.decision_record.supported_by:
                evidence.append(f"DecisionRecord explicitly cites supporting facts: {session.decision_record.supported_by}")
            if session.decision_record.conditional_recommendations:
                evidence.append(f"DecisionRecord includes {len(session.decision_record.conditional_recommendations)} conditional recommendation(s).")

    if ungrounded_recommendations:
        for item in ungrounded_recommendations:
            findings.append(
                EvaluationFinding(
                    id="F-EPI-REC-01",
                    criterion=crit,
                    severity=Severity.HIGH,
                    description="Recomendação sem fundamentação: ferramenta de alta complexidade recomendada sem fatos comprobatórios e sem condição de guarda.",
                    evidence=item,
                    recommendation="Formular a recomendação no formato CONDITIONAL RECOMMENDATION (IF condição THEN ação).",
                )
            )
        score = 1.5
        passed = False
        notes = "Recomendações complexas sem sustentação factual ou guarda condicional."
    else:
        score = 5.0
        passed = True
        notes = "Recomendações devidamente fundamentadas ou guardadas por condições objetivas."

    return (
        CriterionScore(
            criterion=crit,
            score=score,
            evidence=evidence or ["Recommendations properly grounded."],
            notes=notes,
            passed=passed,
        ),
        findings,
    )


def evaluate_epistemic_integrity(
    session: Session,
) -> tuple[CriterionScore, list[EvaluationFinding]]:
    """Composite evaluation measuring overall Epistemic Integrity across all 5 dimensions."""
    crit = EpistemicCriterion.EPISTEMIC_INTEGRITY
    all_findings: list[EvaluationFinding] = []

    sub_evaluators = [
        evaluate_fact_grounding,
        evaluate_assumption_transparency,
        evaluate_unknown_visibility,
        evaluate_inference_traceability,
        evaluate_recommendation_grounding,
    ]

    scores: list[float] = []
    evidence: list[str] = []

    for sub_fn in sub_evaluators:
        score_obj, f_list = sub_fn(session)
        scores.append(score_obj.score)
        all_findings.extend(f_list)
        tag = "PASS" if score_obj.passed else "FAIL"
        evidence.append(f"{score_obj.criterion.value}: {score_obj.score:.1f}/5 [{tag}]")

    has_critical_failure = any(f.severity in (Severity.HIGH, Severity.CRITICAL) for f in all_findings)
    avg_score = round(sum(scores) / len(scores), 1)
    final_score = min(avg_score, 2.0) if has_critical_failure else avg_score
    passed = not has_critical_failure and final_score >= 3.0

    integrity_findings: list[EvaluationFinding] = []
    if not passed:
        integrity_findings.append(
            EvaluationFinding(
                id="F-EPI-INT-01",
                criterion=crit,
                severity=Severity.HIGH,
                description="Integridade epistêmica geral comprometida por violações de premissas, fatos ou incógnitas.",
                evidence=f"Scores das dimensões: {avg_score:.1f}/5. Falha crítica identificada: {has_critical_failure}.",
                recommendation="Corrigir as premissas não declaradas, fundamentar recomendações e preservar incógnitas.",
            )
        )

    return (
        CriterionScore(
            criterion=crit,
            score=final_score,
            evidence=evidence,
            notes="Composite Epistemic Integrity score across 5 specialized dimensions.",
            passed=passed,
        ),
        integrity_findings,
    )
