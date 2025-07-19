#benefit check form
import os
import json
from pydantic import BaseModel, EmailStr, Field, constr, model_validator
from typing import List, Literal, Annotated, Optional
from datetime import date, datetime
from uuid import UUID, uuid4
from decimal import Decimal

# ---------------------------------
# Type Definition
# ---------------------------------

YesNoType = Literal["Yes", "No"]
InsuranceStatusType = Literal["Primary", "Secondary", "Tertiary", "Inactive"]
AlphanumericStr = Annotated[str, Field(max_length=10, pattern="^[a-zA-Z0-9_]+$")]
DocumentStatusType = Literal["Not Started", "Completed", "Archived"]
TaxNumberType = Literal["PCP", "Specialist", "Mental Health Provider", "ABA Provider"]
BenefitRunType = Literal["Calendar Year", "Plan Year", "Rolling Year"]
BenefitApplyType = Literal["Individual", "Family", "Both"]
POSType = Literal["Telehealth POS 02", "School POS 03", "Office POS 11", "Home POS 12", "Community POS 99"]  # Telehealth, School, Office, Home, Community

# ---------------------------------
# Model : ClientInformation
# ---------------------------------

class ClientInformation(BaseModel):
    """
    Model has client information

    Attributes:
        intake_client_id (str): Client's intake ID.
        child_first_name (str): Child's first name.
        child_last_name (str): Child's last name.
        birth_date (date): Child's birth date.
        benefit_verification_forms (List[str]): List of benefit verification forms.
    """
    intake_client_id: str
    child_first_name: str
    child_last_name: str
    birth_date: date
    benefit_verification_forms: List[str] = Field(default_factory=list)

# ---------------------------------
# Model : InsuranceInformation
# ---------------------------------

class InsuranceInformation(BaseModel):
    """
    Model has insurance information

    Attributes:
        plan_name (str): Insurance plan name.
        coverage_start_date (date): Coverage start date.
        coverage_end_date (date): Coverage end date.
        plan_address (str): Plan address.
        zirmed_payor_id (str): ZirMed Payor ID
        subscriber_first_name (str): Subscriber's first name.
        subscriber_last_name (str): Subscriber's last name.
        subscriber_dob (date): Subscriber's date of birth.
        subscriber_id (str): Subscriber ID.
    """
    plan_name: str
    coverage_start_date: date
    coverage_end_date: date
    plan_address: str
    zirmed_payor_id: str
    subscriber_first_name: str
    subscriber_last_name: str
    subscriber_dob: date
    subscriber_id: str

# ---------------------------------
# Model : DocumentInformation
# ---------------------------------

class DocumentInformation(BaseModel):
    """
    Model has document information

    Attributes:
        document_status (DocumentStatusType): Status of the document.
        date_completed (Optional[date]): Date when document was completed.
        completed_by (Optional[str]): Person who completed the document.
        follow_up_notes (Optional[str]): Follow up notes.
        next_follow_up_date (Optional[date]): Next follow up date.
    """
    document_status: DocumentStatusType
    date_completed: Optional[date] = None
    completed_by: Optional[str] = None
    follow_up_notes: Optional[str] = None
    next_follow_up_date: Optional[date] = None

# ---------------------------------
# Model : IndividualFamilyBenefitInformation
# ---------------------------------

class IndividualFamilyBenefitInformation(BaseModel):
    """
    Model has individual/family benefit information

    Attributes:
        in_network_with_plan (YesNoType): Whether in network with plan.
        tax_identification_number_processed_as (TaxNumberType): Tax ID processing type.
        individual_deductible (Decimal): Individual deductible amount.
        individual_deductible_met (Decimal): Individual deductible met amount.
        family_deductible (Decimal): Family deductible amount.
        family_deductible_met (Decimal): Family deductible met amount.
        individual_opm (Decimal): Individual out-of-pocket maximum.
        individual_opm_met (Decimal): Individual OPM met amount.
        family_opm (Decimal): Family out-of-pocket maximum.
        family_opm_met (Decimal): Family OPM met amount.
        accumulations_run_on (BenefitRunType): When accumulations run.
        services_covered_100_percent (YesNoType): Whether services are covered 100%.
        individual_or_family_benefit_apply (BenefitApplyType): Which benefit applies.
        benefit_type_field (str): Type of benefit.
        coinsurance_percentage (Decimal): Coinsurance percentage.
        copay_per_visit (Decimal): Copay per visit amount.
        copays_apply_to_opm (YesNoType): Whether copays apply to OPM.
        deductible_apply_to_opm (YesNoType): Whether deductible applies to OPM.
        deductible_before_coinsurance_copay (YesNoType): Whether deductible must be met before coinsurance/copay.
    """
    in_network_with_plan: YesNoType
    tax_identification_number_processed_as: TaxNumberType
    individual_deductible: Decimal = Field(decimal_places=0, ge=0, le=99999)
    individual_deductible_met: Decimal = Field(decimal_places=0, ge=0)
    family_deductible: Decimal = Field(decimal_places=0, ge=0, le=99999)
    family_deductible_met: Decimal = Field(decimal_places=0, ge=0)
    individual_opm: Decimal = Field(decimal_places=0, ge=0, le=99999)
    individual_opm_met: Decimal = Field(decimal_places=0, ge=0)
    family_opm: Decimal = Field(decimal_places=0, ge=0, le=99999)
    family_opm_met: Decimal = Field(decimal_places=0, ge=0)
    accumulations_run_on: BenefitRunType
    services_covered_100_percent: YesNoType
    individual_or_family_benefit_apply: BenefitApplyType
    benefit_type_field: str
    coinsurance_percentage: Decimal = Field(decimal_places=0)
    copay_per_visit: Decimal = Field(decimal_places=0)
    copays_apply_to_opm: YesNoType
    deductible_apply_to_opm: YesNoType
    deductible_before_coinsurance_copay: YesNoType

# ---------------------------------
# Model : PlaceOfServiceBenefits
# ---------------------------------

class PlaceOfServiceBenefits(BaseModel):
    """
    Model has place of service benefits

    Attributes:
        telehealth_pos_02 (YesNoType): Telehealth POS 02 coverage.
        school_pos_03 (YesNoType): School POS 03 coverage.
        office_pos_11 (YesNoType): Office POS 11 coverage.
        home_pos_12 (YesNoType): Home POS 12 coverage.
        community_pos_99 (YesNoType): Community POS 99 coverage.
    """
    telehealth_pos_02: YesNoType
    school_pos_03: YesNoType
    office_pos_11: YesNoType
    home_pos_12: YesNoType
    community_pos_99: YesNoType

# ---------------------------------
# Model : BenefitDetails
# ---------------------------------

class BenefitDetails(BaseModel):
    """
    Model has benefit details

    Attributes:
        prior_auth_required_evaluation (YesNoType): Prior auth required for evaluation.
        prior_auth_required_therapy (YesNoType): Prior auth required for therapy.
        prior_auth_submission_details (Optional[str]): Prior auth submission details.
        max_cap_exists (YesNoType): Whether there's a max cap.
        max_cap_amount (Optional[Decimal]): Maximum cap amount.
        visit_limit_per_year (Optional[int]): Visit limit per year.
        pre_existing_conditions_exclusions (YesNoType): Pre-existing conditions or exclusions.
        pre_existing_details (Optional[str]): Details of pre-existing conditions.
    """
    prior_auth_required_evaluation: YesNoType
    prior_auth_required_therapy: YesNoType
    prior_auth_submission_details: Optional[str] = None
    max_cap_exists: YesNoType
    max_cap_amount: Optional[Decimal] = Field(default=None, decimal_places=2)
    visit_limit_per_year: Optional[int] = None
    pre_existing_conditions_exclusions: YesNoType
    pre_existing_details: Optional[str] = None

# ---------------------------------
# Model : CoordinationOfBenefits
# ---------------------------------

class CoordinationOfBenefits(BaseModel):
    """
    Model has coordination of benefits information

    Attributes:
        client_has_other_insurances (YesNoType): Whether client has other insurances.
        other_insurance_information (Optional[str]): Other insurance information.
        payor_status (InsuranceStatusType): Primary, secondary, or tertiary payor.
        cob_completion_date (Optional[date]): Date of COB completion.
        benefits_match_portal_inquiry (YesNoType): Whether benefits match portal inquiry.
        mismatch_reason (Optional[str]): Reason for mismatch if any.
    """
    client_has_other_insurances: YesNoType
    other_insurance_information: Optional[str] = None
    payor_status: InsuranceStatusType
    cob_completion_date: Optional[date] = None
    benefits_match_portal_inquiry: YesNoType
    mismatch_reason: Optional[str] = None

# ---------------------------------
# Model : PayorContactInformation
# ---------------------------------

class PayorContactInformation(BaseModel):
    """
    Model has payor contact information

    Attributes:
        payor_rep_name (str): Payor representative name.
        call_reference_number (str): Call reference number.
        date_of_call (date): Date of call.
    """
    payor_rep_name: str
    call_reference_number: str
    date_of_call: date

# ---------------------------------
# Model : OtherBenefitDetails
# ---------------------------------

class OtherBenefitDetails(BaseModel):
    """
    Model has other benefit details

    Attributes:
        benefit_details (str): Additional benefit details.
    """
    benefit_details: str

# ---------------------------------
# Model : BenefitCheckSummaryInformation
# ---------------------------------

class BenefitCheckSummaryInformation(BaseModel):
    """
    Model has benefit check summary information

    Attributes:
        send_benefit_check_summary (YesNoType): Whether to send benefit check summary.
        popup_benefit_check_summary (YesNoType): Whether to show popup benefit check summary.
        document_status (DocumentStatusType): Document status (workspace only).
        follow_up_notes (Optional[str]): Follow up notes.
        next_follow_up_date (Optional[date]): Next follow up date.
    """
    send_benefit_check_summary: YesNoType
    popup_benefit_check_summary: YesNoType
    document_status: DocumentStatusType
    follow_up_notes: Optional[str] = None
    next_follow_up_date: Optional[date] = None


# ---------------------------------
# Complete Benefit Check Form Model
# ---------------------------------

class BenefitCheckForm(BaseModel):
    """
    Complete benefit check form model combining all sections
    """
    client_information: ClientInformation
    insurance_information: InsuranceInformation
    document_information: DocumentInformation
    individual_family_benefit_information: IndividualFamilyBenefitInformation
    place_of_service_benefits: PlaceOfServiceBenefits
    benefit_details: BenefitDetails
    coordination_of_benefits: CoordinationOfBenefits
    payor_contact_information: PayorContactInformation
    other_benefit_details: OtherBenefitDetails
    benefit_check_summary_information: BenefitCheckSummaryInformation

# ---------------------------------
# Synthetic Data Generation
# ---------------------------------

def generate_synthetic_benefit_check_data():
    """Generate synthetic data for benefit check form"""
    
    # Client Information
    client_info = ClientInformation(
        intake_client_id="CLT-2024-001573",
        child_first_name="Emma",
        child_last_name="Johnson",
        birth_date=date(2018, 3, 15),
        benefit_verification_forms=["BVF-001", "BVF-002", "Initial-Assessment"]
    )
    
    # Insurance Information
    insurance_info = InsuranceInformation(
        plan_name="Blue Cross Blue Shield Premium Plus",
        coverage_start_date=date(2024, 1, 1),
        coverage_end_date=date(2024, 12, 31),
        plan_address="1234 Healthcare Ave, Suite 100, Chicago, IL 60601",
        zirmed_payor_id="ZM-BCBS-12345",
        subscriber_first_name="Michael",
        subscriber_last_name="Johnson",
        subscriber_dob=date(1985, 7, 22),
        subscriber_id="BCBS789456123"
    )
    
    # Document Information
    document_info = DocumentInformation(
        document_status="Completed",
        date_completed=date(2024, 6, 15),
        completed_by="Sarah Martinez, Benefits Coordinator",
        follow_up_notes="All verification completed successfully. No issues identified.",
        next_follow_up_date=date(2024, 12, 1)
    )
    
    # Individual/Family Benefit Information
    benefit_info = IndividualFamilyBenefitInformation(
        in_network_with_plan="Yes",
        tax_identification_number_processed_as="PCP",
        individual_deductible=Decimal("1500.00"),
        individual_deductible_met=Decimal("450.00"),
        family_deductible=Decimal("3000.00"),
        family_deductible_met=Decimal("1200.00"),
        individual_opm=Decimal("6000.00"),
        individual_opm_met=Decimal("890.00"),
        family_opm=Decimal("12000.00"),
        family_opm_met=Decimal("2150.00"),
        accumulations_run_on="Calendar Year",
        services_covered_100_percent="No",
        individual_or_family_benefit_apply="Both",
        benefit_type_field="Behavioral Health - Outpatient",
        coinsurance_percentage=Decimal("20.00"),
        copay_per_visit=Decimal("25.00"),
        copays_apply_to_opm="Yes",
        deductible_apply_to_opm="Yes",
        deductible_before_coinsurance_copay="Yes"
    )
    
    # Place of Service Benefits
    pos_benefits = PlaceOfServiceBenefits(
        telehealth_pos_02="Yes",
        school_pos_03="Yes",
        office_pos_11="Yes",
        home_pos_12="Yes",
        community_pos_99="No"
    )
    
    # Benefit Details
    benefit_details = BenefitDetails(
        prior_auth_required_evaluation="No",
        prior_auth_required_therapy="Yes",
        prior_auth_submission_details="Prior authorization required after 6 sessions. Submit via provider portal with treatment plan and progress notes.",
        max_cap_exists="Yes",
        max_cap_amount=Decimal("5000.00"),
        visit_limit_per_year=50,
        pre_existing_conditions_exclusions="No",
        pre_existing_details="No exclusions apply for behavioral health services"
    )
    
    # Coordination of Benefits
    cob_info = CoordinationOfBenefits(
        client_has_other_insurances="Yes",
        other_insurance_information="Secondary: Aetna Better Health (Medicaid) - ID: AET456789",
        payor_status="Primary",
        cob_completion_date=date(2024, 6, 10),
        benefits_match_portal_inquiry="Yes",
        mismatch_reason=None
    )
    
    # Payor Contact Information
    payor_contact = PayorContactInformation(
        payor_rep_name="Jessica Chen",
        call_reference_number="REF-BCBS-20240615-001",
        date_of_call=date(2024, 6, 15)
    )
    
    # Other Benefit Details
    other_details = OtherBenefitDetails(
        benefit_details="Plan covers Applied Behavior Analysis (ABA) therapy. Family therapy sessions covered at same rate. Crisis intervention services available 24/7 with no prior authorization required."
    )
    
    # Benefit Check Summary Information
    summary_info = BenefitCheckSummaryInformation(
        send_benefit_check_summary="Yes",
        popup_benefit_check_summary="Yes",
        document_status="Completed",
        follow_up_notes="Benefits verified and active. Client ready to begin services.",
        next_follow_up_date=date(2024, 12, 1)
    )
    
    # Complete Form
    complete_form = BenefitCheckForm(
        client_information=client_info,
        insurance_information=insurance_info,
        document_information=document_info,
        individual_family_benefit_information=benefit_info,
        place_of_service_benefits=pos_benefits,
        benefit_details=benefit_details,
        coordination_of_benefits=cob_info,
        payor_contact_information=payor_contact,
        other_benefit_details=other_details,
        benefit_check_summary_information=summary_info
    )
    
    return complete_form

# Generate the synthetic data
if __name__ == "__main__":
    synthetic_data = generate_synthetic_benefit_check_data()
    
    # Convert to JSON for easy viewing
    json_data = synthetic_data.model_dump_json(indent=2, default=str)
    
    print("=== SYNTHETIC BENEFIT CHECK DATA ===")
    print(json_data)
    
    # Also save to file
    with open('synthetic_benefit_check_data.json', 'w') as f:
        f.write(json_data)
    
    print("\n=== DATA SAVED TO: synthetic_benefit_check_data.json ===")